"""
Tribal Wars Mobile Automation Engine - TaskScheduler
Motor assíncrono de agendamento de tarefas baseado em asyncio.PriorityQueue,
com suporte a preempção, atrasos com distribuição normal/gaussiana,
micro-jitters e pausa de emergência na interceção de proteções anti-bot.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

from engine.core.exceptions import (
    BotProtectionError,
    RateLimitError,
    SessionExpiredError,
    TribalWarsException,
)
from engine.core.models import Task, TaskPriority
from engine.utils.timing import get_human_delay

logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    Agendador de tarefas concorrente e prioritário para Tribal Wars.
    Garante que ações de alta prioridade (ex.: Alarmes, Defesas) tenham
    precedência imediata sobre tarefas de rotina (Farm, Scavenge, Construção).
    """

    def __init__(self, name: str = "MainScheduler"):
        self.name = name
        self.queue: asyncio.PriorityQueue[Task] = asyncio.PriorityQueue()
        self._running: bool = False
        self._paused: bool = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Começa não pausado (set = desimpedido)
        self._wake_event = asyncio.Event()

        self._worker_task: Optional[asyncio.Task] = None
        self._bot_protect_handlers: List[Callable[[BotProtectionError], Coroutine]] = []
        self._session_expired_handlers: List[Callable[[SessionExpiredError], Coroutine]] = []
        self._task_complete_handlers: List[Callable[[Task, Any], Coroutine]] = []

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def pending_count(self) -> int:
        return self.queue.qsize()

    @property
    def queue_size(self) -> int:
        return self.queue.qsize()


    def on_bot_protection(self, handler: Callable[[BotProtectionError], Coroutine]) -> None:
        """Regista um callback assíncrono executado quando um captcha/bot protect é detetado."""
        self._bot_protect_handlers.append(handler)

    def on_session_expired(self, handler: Callable[[SessionExpiredError], Coroutine]) -> None:
        """Regista um callback assíncrono executado quando a sessão expira."""
        self._session_expired_handlers.append(handler)

    def on_task_completed(self, handler: Callable[[Task, Any], Coroutine]) -> None:
        """Regista um callback assíncrono executado após o sucesso de uma tarefa."""
        self._task_complete_handlers.append(handler)

    def add_task(self, task: Task) -> None:
        """Adiciona uma tarefa à fila de prioridades e notifica o worker."""
        self.queue.put_nowait(task)
        self._wake_event.set()
        logger.debug(
            f"[{self.name}] Tarefa '{task.name}' adicionada com prioridade {task.priority} "
            f"(delay restante: {task.time_until_due():.2f}s)"
        )

    def schedule(
        self,
        name: str,
        priority: TaskPriority,
        action: Callable[..., Coroutine[Any, Any, Any]],
        *args,
        delay_seconds: float = 0.0,
        task_id: str = "",
        max_retries: int = 3,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Task:
        """
        Agenda uma ação assíncrona com um atraso determinístico simples.
        """
        scheduled_at = time.monotonic() + max(0.0, delay_seconds)
        task = Task(
            priority=int(priority),
            scheduled_at=scheduled_at,
            name=name,
            id=task_id or f"{name}_{time.time_ns()}",
            action=action,
            args=args,
            kwargs=kwargs,
            max_retries=max_retries,
            metadata=metadata or {},
        )
        self.add_task(task)
        return task

    def schedule_human_like(
        self,
        name: str,
        priority: TaskPriority,
        action: Callable[..., Coroutine[Any, Any, Any]],
        *args,
        base_seconds: float,
        std_dev: float,
        min_seconds: float,
        max_seconds: float,
        task_id: str = "",
        max_retries: int = 3,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Task:
        """
        Agenda uma tarefa com delay baseado em distribuição normal (gaussiana),
        simulando o comportamento de um jogador humano real.
        """
        human_delay = get_human_delay(base_seconds, std_dev, min_seconds, max_seconds)
        return self.schedule(
            name,
            priority,
            action,
            *args,
            delay_seconds=human_delay,
            task_id=task_id,
            max_retries=max_retries,
            metadata=metadata,
            **kwargs,
        )

    def pause(self) -> None:
        """Pausa imediatamente a execução de novas tarefas da fila."""
        if not self._paused:
            self._paused = True
            self._pause_event.clear()
            logger.warning(f"[{self.name}] Motor de agendamento PAUSADO.")

    def resume(self) -> None:
        """Retoma a execução de tarefas pausadas."""
        if self._paused:
            self._paused = False
            self._pause_event.set()
            logger.info(f"[{self.name}] Motor de agendamento RETOMADO.")

    def start(self) -> None:
        """Inicia o loop assíncrono do worker de tarefas."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop(), name=f"Worker-{self.name}")
        logger.info(f"[{self.name}] Motor de agendamento iniciado.")

    async def stop(self) -> None:
        """Encerra o worker de forma graciosa."""
        if not self._running:
            return
        self._running = False
        self.resume()
        self._wake_event.set()

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

        logger.info(f"[{self.name}] Motor de agendamento encerrado.")

    async def _worker_loop(self) -> None:
        """Loop contínuo de processamento e despacho de tarefas por prioridade."""
        while self._running:
            try:
                # 1. Aguarda caso o agendador tenha sido pausado (ex.: detetado captcha)
                await self._pause_event.wait()

                # 2. Retira a tarefa de maior prioridade
                task: Task = await self.queue.get()

                # 3. Verifica se a tarefa precisa esperar pelo seu timestamp de execução
                while task.time_until_due() > 0:
                    wait_time = task.time_until_due()
                    self._wake_event.clear()
                    try:
                        # Permite preempção se uma tarefa ainda mais prioritária entrar na fila
                        await asyncio.wait_for(self._wake_event.wait(), timeout=min(wait_time, 0.5))
                        # Se fomos acordados, verifica se há uma tarefa mais urgente na fila
                        if not self.queue.empty():
                            # Se a próxima tarefa tem maior prioridade que a atual, devolve a atual e troca
                            next_task = self.queue.get_nowait()
                            if next_task < task:
                                self.queue.put_nowait(task)
                                task = next_task
                            else:
                                self.queue.put_nowait(next_task)
                    except asyncio.TimeoutError:
                        pass

                    # Se foi pausado durante a espera
                    if not self._pause_event.is_set():
                        await self._pause_event.wait()

                # 4. Executa a ação da tarefa
                await self._execute_task(task)
                self.queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.name}] Erro inesperado no worker loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _execute_task(self, task: Task) -> None:
        """Executa a coroutine associada à tarefa e gere exceções e retentativas."""
        logger.info(f"[{self.name}] A executar tarefa: '{task.name}' (id: {task.id})")
        if task.action is None:
            logger.warning(f"Tarefa '{task.name}' não possui ação associada.")
            return

        try:
            result = await task.action(*task.args, **task.kwargs)
            for handler in self._task_complete_handlers:
                asyncio.create_task(handler(task, result))

        except BotProtectionError as bot_err:
            logger.critical(
                f"[{self.name}] Pausando Scheduler devido a deteção de Captcha Anti-Bot!"
            )
            self.pause()
            # Devolve a tarefa à fila para execução posterior quando o captcha for resolvido
            self.add_task(task)
            for handler in self._bot_protect_handlers:
                asyncio.create_task(handler(bot_err))

        except SessionExpiredError as session_err:
            logger.critical(f"[{self.name}] Sessão expirada. Pausando agendador.")
            self.pause()
            self.add_task(task)
            for handler in self._session_expired_handlers:
                asyncio.create_task(handler(session_err))

        except RateLimitError as rate_err:
            logger.warning(
                f"[{self.name}] Rate limit (HTTP 429). Aguardando {rate_err.retry_after}s..."
            )
            task.scheduled_at = time.monotonic() + rate_err.retry_after
            self.add_task(task)

        except Exception as exc:
            task.retry_count += 1
            if task.retry_count <= task.max_retries:
                # Backoff exponencial com jitter
                backoff = (2 ** task.retry_count) * get_human_delay(1.5, 0.4, 1.0, 3.0)
                logger.warning(
                    f"[{self.name}] Erro na tarefa '{task.name}' ({exc}). "
                    f"Tentativa {task.retry_count}/{task.max_retries}. Reagendando em {backoff:.2f}s."
                )
                task.scheduled_at = time.monotonic() + backoff
                self.add_task(task)
            else:
                logger.error(
                    f"[{self.name}] Tarefa '{task.name}' falhou permanentemente após "
                    f"{task.max_retries} tentativas: {exc}"
                )
