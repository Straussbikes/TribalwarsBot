"""
Tribal Wars Mobile Automation Engine - Multi-World Orchestrator
Gestor centralizado de múltiplas instâncias de mundos em execução concorrente e paralela
com isolamento atómico de sessões HTTP, cookies, agendadores e proxies.
"""

from dataclasses import dataclass, field
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

from engine.actions.main_building import MainBuildingManager
from engine.actions.quest import QuestManager
from engine.actions.recruitment import RecruitmentManager
from engine.actions.village_coordinator import MultiVillageCoordinator
from engine.config.settings import BotConfig, load_config
from engine.core.account import TribalAccount
from engine.core.exceptions import BotProtectionError
from engine.core.models import TaskPriority
from engine.core.scheduler import TaskScheduler

logger = logging.getLogger(__name__)


@dataclass
class WorldInstance:
    """Instância isolada de execução para um mundo específico do Tribal Wars."""

    world: str
    account: TribalAccount
    scheduler: TaskScheduler
    config: BotConfig
    coordinator: MultiVillageCoordinator
    is_active: bool = True
    created_at: float = field(default_factory=time.time)

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.created_at

    def to_dict(self) -> Dict[str, Any]:
        """Serializa o resumo da instância do mundo."""
        curr_v = self.account.current_village
        player = self.account.player
        return {
            "world": self.world,
            "domain": self.config.domain,
            "is_active": self.is_active,
            "is_running": self.scheduler.is_running,
            "is_paused": self.scheduler.is_paused,
            "queue_size": self.scheduler.queue_size,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "player_name": player.name if player else None,
            "villages_count": len(self.account.villages),
            "current_village": {
                "id": curr_v.id,
                "name": curr_v.name,
                "coordinates": curr_v.coordinates,
            } if curr_v else None,
            "has_sid": bool(self.account.sid),
            "proxy": self.config.proxy,
        }


def setup_world_routines(instance: WorldInstance) -> None:
    """
    Agenda as rotinas automáticas (recursos, construção, farm, recrutamento, missões)
    no TaskScheduler isolado da instância do mundo para execução concorrente.
    """
    world = instance.world
    account = instance.account
    scheduler = instance.scheduler
    config = instance.config

    if not account or not account.sid:
        return

    # 1. Polling de Recursos e Tropas da Aldeia Ativa
    async def poll_resources():
        try:
            village = await account.refresh_state()
            res = village.resources
            try:
                place_mgr = PlaceManager()
                await place_mgr.get_state(account, village_id=village.id)
            except Exception as e:
                logger.debug(f"[{world}] Falha suave ao obter estado da Praça: {e}")

            troops_summary = ", ".join(f"{k}:{v}" for k, v in (village.troops or {}).items() if v > 0)
            logger.info(
                f"[{world}] Aldeia: '{village.name}' ({village.coordinates}) | "
                f"Madeira: {res.wood} | Argila: {res.stone} | "
                f"Ferro: {res.iron} | Armazém: {res.storage_max} | Pop Livre: {res.free_pop}"
                f"{f' | Tropas: {troops_summary}' if troops_summary else ''}"
            )
        except Exception as e:
            logger.debug(f"[{world}] Falha suave ao atualizar recursos: {e}")
        finally:
            if scheduler.is_running and not scheduler.is_paused:
                scheduler.schedule_human_like(
                    name=f"Poll Recursos [{world}]",
                    priority=TaskPriority.REFRESH,
                    action=poll_resources,
                    base_seconds=60.0,
                    std_dev=10.0,
                    min_seconds=45.0,
                    max_seconds=90.0,
                )

    scheduler.schedule(
        name=f"Poll Recursos Inicial [{world}]",
        priority=TaskPriority.REFRESH,
        action=poll_resources,
        delay_seconds=2.0,
    )

    # 2. Auto-Build (Construção Automática)
    build_plan = config.get_active_build_plan()
    main_manager = MainBuildingManager(default_max_queue=config.building.max_queue)
    main_manager.schedule_auto_build(
        scheduler=scheduler,
        account=account,
        plan=build_plan,
        max_queue=config.building.max_queue,
        interval_seconds=config.building.interval_seconds,
        bot_config=config,
    )

    # 3. Recrutamento Militar (se ativado)
    if config.recruitment.enabled:
        recruit_manager = RecruitmentManager()
        recruit_manager.schedule_auto_recruit(
            scheduler=scheduler,
            account=account,
            recruit_config=config.recruitment,
        )

    # 5. Missões e Bónus Diário (se ativado)
    if config.quest.enabled:
        quest_manager = QuestManager()

        async def quest_cycle_task():
            try:
                res = await quest_manager.run_cycle(
                    account=account,
                    village_id=account.current_village_id,
                    config=config.quest,
                )
                if res.get("quests_claimed", 0) > 0:
                    logger.info(f"[{world}] {res['quests_claimed']} missões resgatadas com sucesso.")
                if res.get("daily_bonus_opened"):
                    logger.info(f"[{world}] Baú diário gratuito aberto com sucesso.")
            except Exception as e:
                logger.debug(f"[{world}] Ciclo de missões: {e}")
            finally:
                if scheduler.is_running and not scheduler.is_paused:
                    scheduler.schedule_human_like(
                        name=f"QuestCycle [{world}]",
                        priority=TaskPriority.QUEST,
                        action=quest_cycle_task,
                        base_delay=config.quest.interval_minutes * 60.0,
                        jitter_sigma=30.0,
                    )

        scheduler.schedule(
            name=f"QuestCycleInicial [{world}]",
            priority=TaskPriority.QUEST,
            action=quest_cycle_task,
            delay_seconds=15.0,
        )

    # 6. Keep-Alive da Sessão
    if config.auth.keep_alive:
        async def keep_alive_task():
            try:
                if account and account.sid:
                    await account.refresh_state()
            except Exception as e:
                logger.debug(f"[{world}] Falha no keep-alive da sessão: {e}")
            finally:
                if scheduler.is_running and not scheduler.is_paused:
                    scheduler.schedule_human_like(
                        name=f"SessionKeepAlive [{world}]",
                        priority=TaskPriority.BACKGROUND,
                        action=keep_alive_task,
                        base_delay=config.auth.keep_alive_interval_minutes * 60.0,
                        jitter_sigma=30.0,
                    )

        scheduler.schedule(
            name=f"SessionKeepAliveInicial [{world}]",
            priority=TaskPriority.BACKGROUND,
            action=keep_alive_task,
            delay_seconds=30.0,
        )


class MultiWorldManager:
    """
    Orquestrador global de múltiplos mundos concorrentes.
    Garante que cada mundo opere com a sua própria pilha de rede, agendador e contexto.
    """

    def __init__(
        self,
        on_captcha_alert: Optional[Callable[[str, str], Coroutine[Any, Any, None]]] = None,
    ):
        self.instances: Dict[str, WorldInstance] = {}
        self.active_world: Optional[str] = None
        self._on_captcha_alert = on_captcha_alert

    def get_instance(self, world: Optional[str] = None) -> Optional[WorldInstance]:
        """Retorna a instância do mundo solicitado ou a instância atualmente ativa."""
        if world and world in self.instances:
            return self.instances[world]
        if self.active_world and self.active_world in self.instances:
            return self.instances[self.active_world]
        if self.instances:
            return next(iter(self.instances.values()))
        return None

    async def register_world(
        self,
        world: str,
        sid: str,
        domain: str = "tribalwars.com.pt",
        proxy: Optional[str] = None,
        config: Optional[BotConfig] = None,
        auto_start: bool = True,
    ) -> WorldInstance:
        """
        Regista e inicializa uma nova instância de mundo com ciclo de vida isolado.
        """
        world_key = world.strip().lower()

        # Se já existir, atualiza credenciais
        if world_key in self.instances:
            existing = self.instances[world_key]
            if sid:
                existing.config.sid = sid
                existing.account.sid = sid
                await existing.account.init_session()
            if proxy is not None:
                existing.config.proxy = proxy
                existing.account.proxy = proxy
            return existing

        world_cfg = config or load_config()
        world_cfg.world = world_key
        world_cfg.domain = domain
        world_cfg.sid = sid
        world_cfg.proxy = proxy

        account = TribalAccount(
            world=world_key,
            sid=sid,
            domain=domain,
            proxy=proxy,
        )

        scheduler = TaskScheduler(f"Scheduler-{world_key}")
        coordinator = MultiVillageCoordinator()

        # Configura handlers de segurança
        async def _bot_detected(err: BotProtectionError):
            logger.critical(f"[{world_key}] ALERTA ANTI-BOT INTERCEPTADO NO MUNDO {world_key.upper()}!")
            if self._on_captcha_alert:
                await self._on_captcha_alert(world_key, err.message)

        scheduler.on_bot_protection(_bot_detected)

        instance = WorldInstance(
            world=world_key,
            account=account,
            scheduler=scheduler,
            config=world_cfg,
            coordinator=coordinator,
            is_active=True,
        )

        self.instances[world_key] = instance
        if not self.active_world:
            self.active_world = world_key

        if auto_start and sid:
            try:
                await account.init_session()
                setup_world_routines(instance)
                scheduler.start()
                logger.info(f"[{world_key}] Instância multi-mundo inicializada, rotinas agendadas e agendador ativo.")
            except Exception as e:
                logger.warning(f"[{world_key}] Aviso na conexão inicial do mundo: {e}")

        return instance

    async def unregister_world(self, world: str) -> bool:
        """Encerra e remove a instância de um mundo."""
        world_key = world.strip().lower()
        if world_key not in self.instances:
            return False

        inst = self.instances.pop(world_key)
        try:
            await inst.scheduler.stop()
        except Exception as e:
            logger.debug(f"[{world_key}] Aviso ao parar scheduler: {e}")

        if getattr(inst.account, "_session", None):
            try:
                await inst.account._session.close()
            except Exception as e:
                logger.debug(f"[{world_key}] Aviso ao fechar sessão HTTP: {e}")

        if self.active_world == world_key:
            self.active_world = next(iter(self.instances.keys())) if self.instances else None

        logger.info(f"[{world_key}] Instância do mundo encerrada e desregistada.")
        return True

    def pause_world(self, world: str) -> bool:
        """Pausa o agendador de um mundo específico."""
        inst = self.get_instance(world)
        if inst:
            inst.scheduler.pause()
            logger.info(f"[{inst.world}] Agendador pausado.")
            return True
        return False

    def resume_world(self, world: str) -> bool:
        """Retoma o agendador de um mundo específico."""
        inst = self.get_instance(world)
        if inst:
            inst.scheduler.resume()
            logger.info(f"[{inst.world}] Agendador retomado.")
            return True
        return False

    def set_active_world(self, world: str) -> bool:
        """Altera o mundo atualmente em foco para o dashboard do frontend."""
        world_key = world.strip().lower()
        if world_key in self.instances:
            self.active_world = world_key
            logger.info(f"Mundo ativo alterado para '{world_key}'.")
            return True
        return False

    def list_worlds(self) -> List[Dict[str, Any]]:
        """Retorna a lista formatada de todos os mundos registados."""
        return [
            {
                **inst.to_dict(),
                "is_focused": (inst.world == self.active_world),
            }
            for inst in self.instances.values()
        ]
