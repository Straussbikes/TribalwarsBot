"""
TribalWarsBot - Account Session Manager & Concurrency Mutex
Implementa o singleton AccountSessionManager que impõe a regra de exclusão mútua:
Apenas UM game_username pode estar em execução/memória ativa de cada vez.
Garante paragem graciosa (cancellation token), desalocação de recursos e troca atómica de contas.
"""

from __future__ import annotations

import asyncio
from enum import Enum
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("TribalWarsBot.AccountSessionManager")


class AccountSessionConflictError(Exception):
    """Lançado quando uma ação ou sessão de rede tenta executar sob credenciais de uma conta não ativa."""
    pass


class AccountSessionState(str, Enum):
    IDLE = "IDLE"
    SWITCHING = "SWITCHING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"


class AccountSessionManager:
    """
    Singleton que gere a posse da sessão de jogo em memória.
    Apenas um único 'game_username' pode ter workers e sessões ativas simultaneamente.
    """

    _instance: Optional[AccountSessionManager] = None
    _init_lock = asyncio.Lock()

    def __new__(cls) -> AccountSessionManager:
        if cls._instance is None:
            cls._instance = super(AccountSessionManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._lock = asyncio.Lock()
        self.state: AccountSessionState = AccountSessionState.IDLE
        self.active_user_id: Optional[str] = None
        self.active_account_id: Optional[str] = None
        self.active_game_username: Optional[str] = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._stop_event.set()  # Começa sinalizado como parado
        self.session_start_time: Optional[float] = None
        from engine.core.world_worker_orchestrator import WorldWorkerOrchestrator
        self.orchestrator: WorldWorkerOrchestrator = WorldWorkerOrchestrator()
        self._initialized = True
        logger.info("[AccountSessionManager] Singleton inicializado com exclusão mútua ativada.")

    @classmethod
    def get_instance(cls) -> AccountSessionManager:
        if cls._instance is None:
            cls._instance = AccountSessionManager()
        return cls._instance

    @classmethod
    def reset_instance_for_testing(cls) -> None:
        """Método auxiliar exclusivo para testes unitários isolados."""
        cls._instance = None

    def get_cancellation_token(self) -> asyncio.Event:
        """Retorna o evento/token de cancelamento da sessão ativa."""
        return self._stop_event

    def is_cancellation_requested(self) -> bool:
        """Verifica se foi solicitada a paragem dos workers da conta atual."""
        return self._stop_event.is_set()

    def assert_account_active(self, game_username: str) -> None:
        """
        Validação estrita: Impede que qualquer worker, browser context ou requisição
        de rede seja executada por um game_username diferente daquele atualmente ativo em lock.
        """
        target = game_username.strip().lower()
        active = (self.active_game_username or "").strip().lower()
        if not active or target != active:
            raise AccountSessionConflictError(
                f"Acesso negado: O utilizador de jogo '{game_username}' não detém o lock ativo. "
                f"Conta em execução: '{self.active_game_username or 'Nenhuma'}'."
            )

    async def switch_account(
        self,
        app_user_id: str,
        game_username: str,
        account_id: Optional[str] = None,
        timeout: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Troca atómica e graciosa de conta de jogo:
        1. Emite sinal de paragem graciosa a todas as tarefas ativas do username atual.
        2. Aguarda a finalização dos workers e desaloca recursos de rede/cookies em memória.
        3. Adquire o lock para o novo game_username e carrega os respetivos mundos.
        """
        clean_username = game_username.strip()

        async with self._lock:
            # Se já for a mesma conta ativa, apenas valida o estado
            if (
                self.active_user_id == app_user_id
                and self.active_game_username
                and self.active_game_username.lower() == clean_username.lower()
                and self.state == AccountSessionState.RUNNING
            ):
                logger.info(f"[AccountSessionManager] Conta '{clean_username}' já se encontra ativa.")
                return self.get_status()

            logger.info(
                f"[AccountSessionManager] 🔄 A iniciar transição de conta: "
                f"'{self.active_game_username or 'Nenhuma'}' -> '{clean_username}'..."
            )
            self.state = AccountSessionState.SWITCHING

            # 1. Paragem graciosa da conta anterior se existir
            if self.active_game_username:
                await self._stop_current_session_internal(timeout=timeout)

            # 2. Configura a nova posse exclusiva
            self.active_user_id = app_user_id
            self.active_account_id = account_id
            self.active_game_username = clean_username
            self.session_start_time = time.time()
            self._stop_event = asyncio.Event()  # Limpo = a correr, sem cancelamento
            self.state = AccountSessionState.RUNNING

            # 3. Inicializa/atualiza o WorldWorkerOrchestrator para a nova conta
            if self.orchestrator:
                await self.orchestrator.on_account_switched(
                    app_user_id=app_user_id,
                    game_username=clean_username,
                    account_id=account_id,
                    cancellation_token=self._stop_event,
                )

            logger.info(
                f"[AccountSessionManager] ✅ Lock adquirido com sucesso para o utilizador de jogo: '{clean_username}'."
            )
            return self.get_status()

    async def stop_current_session(self, timeout: float = 5.0) -> None:
        """Para a sessão ativa e liberta o lock de execução."""
        async with self._lock:
            await self._stop_current_session_internal(timeout=timeout)

    async def _stop_current_session_internal(self, timeout: float = 5.0) -> None:
        if not self.active_game_username and self.state == AccountSessionState.IDLE:
            return

        prev_user = self.active_game_username
        self.state = AccountSessionState.STOPPING
        logger.info(f"[AccountSessionManager] ⏹ A emitir sinal de cancelamento a todos os workers de '{prev_user}'...")

        # Sinaliza o cancellation token
        self._stop_event.set()

        # Para os workers do orchestrator
        if self.orchestrator:
            try:
                await asyncio.wait_for(self.orchestrator.stop_all_workers(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    f"[AccountSessionManager] ⚠️ Timeout ao aguardar finalização suave dos workers de '{prev_user}'. Forçando limpeza."
                )
            except Exception as e:
                logger.error(f"[AccountSessionManager] Erro ao parar workers de '{prev_user}': {e}")

        # Desaloca recursos em memória
        self.active_user_id = None
        self.active_account_id = None
        self.active_game_username = None
        self.session_start_time = None
        self.state = AccountSessionState.IDLE
        logger.info(f"[AccountSessionManager] 🧹 Sessão de '{prev_user}' terminada e recursos desalocados.")

    def get_status(self) -> Dict[str, Any]:
        """Retorna o estado operacional do gestor de sessão."""
        uptime = (time.time() - self.session_start_time) if self.session_start_time else 0.0
        return {
            "state": self.state.value,
            "active_user_id": self.active_user_id,
            "active_account_id": self.active_account_id,
            "active_game_username": self.active_game_username,
            "is_running": self.state == AccountSessionState.RUNNING,
            "session_uptime_seconds": round(uptime, 1),
            "cancellation_requested": self.is_cancellation_requested(),
        }
