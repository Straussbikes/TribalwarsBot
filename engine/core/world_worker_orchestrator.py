"""
TribalWarsBot - World Worker Orchestrator
Orquestrador de tarefas em background para múltiplos mundos simultâneos sob o mesmo game_username.
Garante isolamento estrito de instâncias de rede, agendadores independentes, tratamento
isolado de rate limits e execução contínua para as aldeias da tabela 'villages'.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

from engine.actions.farm import FarmManager
from engine.actions.main_building import MainBuildingManager
from engine.actions.market import MarketManager
from engine.actions.quest import QuestManager
from engine.actions.recruitment import RecruitmentManager
from engine.actions.village_coordinator import MultiVillageCoordinator
from engine.config.settings import BotConfig, load_config
from engine.core.account import TribalAccount
from engine.core.exceptions import RateLimitError
from engine.core.models import TaskPriority
from engine.core.scheduler import TaskScheduler
from engine.storage.cloud_db import CloudDatabase, GameAccountRepository, GameWorldRepository, VillageRepository, get_cloud_db

logger = logging.getLogger("TribalWarsBot.WorldWorkerOrchestrator")


class WorldWorker:
    """
    Worker isolado responsável pela automação contínua de um mundo específico.
    Executa com a sua própria sessão HTTP, agendador e gestores de aldeia.
    """

    def __init__(
        self,
        world_code: str,
        account: TribalAccount,
        config: BotConfig,
        cancellation_token: asyncio.Event,
        db: Optional[CloudDatabase] = None,
        is_active: bool = True,
        broadcast_callback: Optional[Any] = None,
    ):
        self.world_code = world_code.strip().lower()
        self.account = account
        self.config = config
        self.cancellation_token = cancellation_token
        self.db = db or get_cloud_db()
        self.is_active = is_active
        self.scheduler = TaskScheduler()

        # Gestores de ecrã/ações isolados para esta instância
        self.main_building_manager = MainBuildingManager()
        self.recruitment_manager = RecruitmentManager()
        self.farm_manager = FarmManager(broadcast_callback=broadcast_callback)
        if broadcast_callback and not getattr(self.account, "_broadcast_sync", None):
            self.account._broadcast_sync = broadcast_callback
        self.quest_manager = QuestManager()
        self.market_manager = MarketManager()
        self.coordinator = MultiVillageCoordinator(
            main_building_manager=self.main_building_manager,
            recruitment_manager=self.recruitment_manager,
            farm_manager=self.farm_manager,
            market_manager=self.market_manager,
        )

        # Estado de Rate Limiting isolado por mundo
        self.is_rate_limited = False
        self.rate_limit_until: float = 0.0
        self.created_at = time.time()
        self._running = False

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.created_at

    def handle_rate_limit(self, retry_after: float = 30.0) -> None:
        """
        Congela temporariamente apenas este worker de mundo sem afetar os restantes mundos.
        """
        self.is_rate_limited = True
        self.rate_limit_until = time.time() + retry_after
        logger.warning(
            f"[{self.world_code}] ⏳ Rate limit detetado. Worker pausado por {retry_after:.1f}s. "
            f"Restantes mundos continuam a executar normalmente."
        )

    async def start(self) -> None:
        """Inicia o scheduler e as rotinas automáticas do mundo."""
        if self._running:
            return
        self._running = True
        self.scheduler.start()
        self._setup_routines()
        logger.info(f"[{self.world_code}] 🚀 Worker de mundo iniciado com agendador isolado.")

    async def stop(self, timeout: float = 3.0) -> None:
        """Para o worker graciosamente e fecha a sessão HTTP."""
        if not self._running:
            return
        self._running = False
        await self.scheduler.stop()
        try:
            await asyncio.wait_for(self.account.close_session(), timeout=timeout)
        except Exception as e:
            logger.debug(f"[{self.world_code}] Aviso ao fechar sessão HTTP: {e}")
        logger.info(f"[{self.world_code}] ⏹ Worker de mundo finalizado com sucesso.")

    def _setup_routines(self) -> None:
        """Configura as rotinas periódicas do mundo baseadas nas aldeias registadas."""
        world = self.world_code
        acc = self.account
        sched = self.scheduler
        cfg = self.config

        # 1. Polling Periódico e Sincronização de Recursos
        async def poll_resources_task():
            if self.cancellation_token.is_set():
                return
            if self.is_rate_limited and time.time() < self.rate_limit_until:
                return
            self.is_rate_limited = False

            try:
                village_data = await acc.refresh_state()
                if village_data and self.db:
                    # Sincroniza aldeia na tabela 'villages' do Cloud SQL
                    gw_repo = GameWorldRepository(self.db)
                    v_repo = VillageRepository(self.db)
                    
                    # Procura o game_world_id
                    gworlds = await gw_repo.list_by_account(acc.account_id or "default")
                    gw = next((w for w in gworlds if w.world_code == world), None)
                    if gw:
                        await v_repo.upsert_village(
                            game_world_id=gw.id,
                            village_game_id=village_data.id,
                            village_name=village_data.name,
                            coord_x=village_data.x,
                            coord_y=village_data.y,
                        )
            except RateLimitError as rle:
                self.handle_rate_limit(rle.retry_after)
            except Exception as e:
                logger.debug(f"[{world}] Aviso suave ao atualizar recursos: {e}")
            finally:
                if sched.is_running and not self.cancellation_token.is_set() and self.is_active:
                    sched.schedule_human_like(
                        name=f"PollRecursos [{world}]",
                        priority=TaskPriority.REFRESH,
                        action=poll_resources_task,
                        base_seconds=60.0,
                        std_dev=8.0,
                        min_seconds=30.0,
                        max_seconds=120.0,
                    )

        # 2. Rotina de Construção por Aldeia
        async def building_cycle_task():
            if self.cancellation_token.is_set() or not self.is_active:
                return
            if self.is_rate_limited and time.time() < self.rate_limit_until:
                return

            try:
                if cfg.building.enabled and acc.current_village_id:
                    # Obtém modelo atribuído à aldeia
                    v_id = acc.current_village_id
                    plan = cfg.get_active_build_plan(village_id=str(v_id))
                    await self.main_building_manager.run_building_cycle(
                        account=acc,
                        plan=plan,
                        max_queue=cfg.building.max_queue,
                        village_id=v_id,
                    )
            except RateLimitError as rle:
                self.handle_rate_limit(rle.retry_after)
            except Exception as e:
                logger.debug(f"[{world}] Aviso no ciclo de construção: {e}")
            finally:
                if sched.is_running and not self.cancellation_token.is_set() and self.is_active:
                    sched.schedule_human_like(
                        name=f"AutoBuild [{world}]",
                        priority=TaskPriority.BUILD,
                        action=building_cycle_task,
                        base_seconds=cfg.building.interval_seconds,
                        std_dev=cfg.building.interval_seconds * 0.15,
                        min_seconds=30.0,
                        max_seconds=cfg.building.interval_seconds * 2.0,
                    )

        # 3. Rotina de Farm
        async def farm_cycle_task():
            if self.cancellation_token.is_set() or not self.is_active:
                return
            if self.is_rate_limited and time.time() < self.rate_limit_until:
                return

            try:
                if cfg.farm.enabled and acc.current_village_id:
                    await self.farm_manager.run_comprehensive_radius_farm_cycle(
                        account=acc,
                        radius=cfg.farm.max_distance,
                        default_template=cfg.farm.default_template,
                        custom_targets=cfg.farm.custom_targets,
                        custom_troops=cfg.farm.custom_troops,
                        village_id=acc.current_village_id,
                    )
            except RateLimitError as rle:
                self.handle_rate_limit(rle.retry_after)
            except Exception as e:
                logger.debug(f"[{world}] Aviso no ciclo de farm: {e}")
            finally:
                if sched.is_running and not self.cancellation_token.is_set() and self.is_active:
                    min_sec = float(getattr(cfg.farm, "min_interval_seconds", 45))
                    max_sec = float(getattr(cfg.farm, "max_interval_seconds", 90))
                    base_sec = (min_sec + max_sec) / 2.0
                    sched.schedule_human_like(
                        name=f"AutoFarm [{world}]",
                        priority=TaskPriority.FARM,
                        action=farm_cycle_task,
                        base_seconds=base_sec,
                        std_dev=max(5.0, (max_sec - min_sec) * 0.2),
                        min_seconds=min_sec,
                        max_seconds=max_sec,
                    )

        # 4. Rotina de Recrutamento
        async def recruit_cycle_task():
            if self.cancellation_token.is_set() or not self.is_active:
                return
            if self.is_rate_limited and time.time() < self.rate_limit_until:
                return

            try:
                if cfg.recruitment.enabled and acc.current_village_id:
                    targets = cfg.get_village_recruitment_targets(village_id=str(acc.current_village_id))
                    await self.recruitment_manager.run_recruitment_cycle(
                        account=acc,
                        targets=targets,
                        batch_sizes=cfg.recruitment.batch_sizes,
                        min_free_pop=cfg.recruitment.min_free_pop,
                        village_id=acc.current_village_id,
                    )
            except RateLimitError as rle:
                self.handle_rate_limit(rle.retry_after)
            except Exception as e:
                logger.debug(f"[{world}] Aviso no ciclo de recrutamento: {e}")
            finally:
                if sched.is_running and not self.cancellation_token.is_set() and self.is_active:
                    interval_sec = cfg.recruitment.interval_minutes * 60.0
                    sched.schedule_human_like(
                        name=f"AutoRecruit [{world}]",
                        priority=TaskPriority.RECRUIT,
                        action=recruit_cycle_task,
                        base_seconds=interval_sec,
                        std_dev=interval_sec * 0.15,
                        min_seconds=60.0,
                        max_seconds=interval_sec * 2.0,
                    )

        # Agenda as tarefas iniciais com ligeiro stagger para evitar concorrência no arranque
        sched.schedule(name=f"PollRecursos [{world}]", priority=TaskPriority.REFRESH, action=poll_resources_task, delay_seconds=2.0)
        if cfg.building.enabled:
            sched.schedule(name=f"AutoBuild [{world}]", priority=TaskPriority.BUILD, action=building_cycle_task, delay_seconds=6.0)
        if cfg.farm.enabled:
            sched.schedule(name=f"AutoFarm [{world}]", priority=TaskPriority.FARM, action=farm_cycle_task, delay_seconds=10.0)
        if cfg.recruitment.enabled:
            sched.schedule(name=f"AutoRecruit [{world}]", priority=TaskPriority.RECRUIT, action=recruit_cycle_task, delay_seconds=16.0)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa o status do worker."""
        curr_v = self.account.current_village
        return {
            "world": self.world_code,
            "is_active": self.is_active,
            "is_running": self._running,
            "is_rate_limited": self.is_rate_limited,
            "rate_limit_seconds_left": max(0.0, round(self.rate_limit_until - time.time(), 1)),
            "queue_size": self.scheduler.queue_size,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "villages_count": len(self.account.villages),
            "current_village": {
                "id": curr_v.id,
                "name": curr_v.name,
                "coordinates": curr_v.coordinates,
            } if curr_v else None,
        }


class WorldWorkerOrchestrator:
    """
    Orquestrador que gere o ciclo de vida e a execução paralela de todos os mundos
    associados ao 'game_username' atualmente ativo no AccountSessionManager.
    """

    def __init__(self, db: Optional[CloudDatabase] = None, broadcast_callback: Optional[Any] = None):
        self.db = db or get_cloud_db()
        self.workers: Dict[str, WorldWorker] = {}
        self.active_game_username: Optional[str] = None
        self.active_account_id: Optional[str] = None
        self.cancellation_token: Optional[asyncio.Event] = None
        self.active_focus_world: Optional[str] = None
        self.broadcast_callback: Optional[Any] = broadcast_callback

    async def on_account_switched(
        self,
        app_user_id: str,
        game_username: str,
        account_id: Optional[str] = None,
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> None:
        """
        Chamado pelo AccountSessionManager quando ocorre a troca atómica de conta:
        Carrega os mundos associados à nova conta do Cloud SQL e arranca os respetivos workers.
        """
        # Para workers existentes se houver
        await self.stop_all_workers()

        self.active_game_username = game_username
        self.active_account_id = account_id
        self.cancellation_token = cancellation_token or asyncio.Event()

        # Carrega mundos da base de dados se account_id estiver disponível
        if account_id and self.db:
            await self.load_and_start_worlds(account_id)

    async def load_and_start_worlds(self, account_id: str) -> None:
        """Consulta o Cloud SQL pelos mundos registados para esta conta e inicializa os workers."""
        gw_repo = GameWorldRepository(self.db)
        acc_repo = GameAccountRepository(self.db)

        acc = await acc_repo.get_by_id(account_id)
        if not acc:
            logger.warning(f"[WorldWorkerOrchestrator] Conta ID '{account_id}' não encontrada.")
            return

        creds = acc_repo.decrypt_credentials(acc)
        sid = creds.get("sid", "")
        domain = creds.get("domain", "tribalwars.com.pt")
        proxy = creds.get("proxy")

        worlds = await gw_repo.list_by_account(account_id)
        for w in worlds:
            await self.register_and_start_worker(
                world_code=w.world_code,
                sid=sid,
                domain=domain,
                proxy=proxy,
                is_active=w.is_active,
                account_id=account_id,
            )

    async def register_and_start_worker(
        self,
        world_code: str,
        sid: str = "",
        domain: str = "tribalwars.com.pt",
        proxy: Optional[str] = None,
        is_active: bool = True,
        account_id: Optional[str] = None,
    ) -> WorldWorker:
        w_code = world_code.strip().lower()

        # Se já existir, atualiza estado
        if w_code in self.workers:
            worker = self.workers[w_code]
            worker.is_active = is_active
            if sid:
                worker.account.sid = sid
            return worker

        cfg = load_config()
        cfg.world = w_code
        cfg.domain = domain
        cfg.sid = sid
        cfg.proxy = proxy

        account = TribalAccount(
            world=w_code,
            sid=sid,
            domain=domain,
            proxy=proxy,
        )
        if account_id or self.active_account_id:
            account.account_id = account_id or self.active_account_id

        token = self.cancellation_token or asyncio.Event()
        worker = WorldWorker(
            world_code=w_code,
            account=account,
            config=cfg,
            cancellation_token=token,
            db=self.db,
            is_active=is_active,
            broadcast_callback=self.broadcast_callback,
        )

        self.workers[w_code] = worker
        if not self.active_focus_world:
            self.active_focus_world = w_code

        if is_active:
            await worker.start()

        logger.info(f"[WorldWorkerOrchestrator] Worker registado para o mundo '{w_code}' (is_active={is_active}).")
        return worker

    async def toggle_world_worker(self, world_code: str, is_active: bool) -> bool:
        """Ativa ou pausa o worker de um mundo específico em tempo de execução."""
        w_code = world_code.strip().lower()
        worker = self.workers.get(w_code)
        if not worker:
            return False

        worker.is_active = is_active
        if is_active and not worker._running:
            await worker.start()
        elif not is_active and worker._running:
            await worker.stop()

        # Atualiza na base de dados se account_id estiver definido
        if self.active_account_id and self.db:
            gw_repo = GameWorldRepository(self.db)
            await gw_repo.toggle_active(
                game_account_id=self.active_account_id,
                world_code=w_code,
                is_active=is_active,
            )

        logger.info(f"[WorldWorkerOrchestrator] Estado do mundo '{w_code}' alterado para is_active={is_active}.")
        return True

    async def stop_all_workers(self, timeout: float = 3.0) -> None:
        """Para todos os workers ativos concorrentemente."""
        if not self.workers:
            return

        logger.info(f"[WorldWorkerOrchestrator] A parar {len(self.workers)} workers de mundos...")
        stop_tasks = [w.stop(timeout=timeout) for w in self.workers.values()]
        await asyncio.gather(*stop_tasks, return_exceptions=True)
        self.workers.clear()
        self.active_focus_world = None

    def get_worker(self, world_code: Optional[str] = None) -> Optional[WorldWorker]:
        if world_code:
            return self.workers.get(world_code.strip().lower())
        if self.active_focus_world and self.active_focus_world in self.workers:
            return self.workers[self.active_focus_world]
        if self.workers:
            return next(iter(self.workers.values()))
        return None

    def get_status(self) -> Dict[str, Any]:
        return {
            "active_game_username": self.active_game_username,
            "active_account_id": self.active_account_id,
            "active_focus_world": self.active_focus_world,
            "total_workers": len(self.workers),
            "workers": {w_k: w.to_dict() for w_k, w in self.workers.items()},
        }
