"""
Tribal Wars Mobile Automation Engine - Orquestrador de Contexto do Sidecar
Mantém o estado unificado, distribui eventos para WebSockets e fornece acesso às ações.
"""

import asyncio
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import WebSocket

from engine.actions.combat_sync import ClockSynchronizer
from engine.actions.combat_tactics import (
    CombatManager,
    NobleTrainPlan,
    BacktimePlan,
    SnipePlan,
    TacticalOperation,
    TacticalOperationType,
    TacticalOperationStatus,
)
from engine.actions.defense import DefenseManager, DodgeOperation, IncomingAttack
from engine.actions.economic_arbitrage import EconomicArbitrageManager
from engine.actions.farm import FarmManager
from engine.actions.inactivity_tracker import InactivityFilterConfig, InactivityTracker
from engine.actions.main_building import MainBuildingManager
from engine.actions.map import MapData, MapManager
from engine.actions.market import MarketManager
from engine.actions.place import PlaceManager, UnitsCount
from engine.actions.quest import QuestManager
from engine.actions.recruitment import RecruitmentManager
from engine.actions.scavenge import ScavengeManager
from engine.actions.smith import SmithManager
from engine.actions.snob import SnobManager
from engine.actions.inventory import InventoryManager
from engine.actions.village_coordinator import MultiVillageCoordinator
from engine.actions.world_data import WorldDataWorker
from engine.config.settings import BotConfig
from engine.core.account import TribalAccount
from engine.core.models import TaskPriority
from engine.core.multi_world import MultiWorldManager, WorldInstance
from engine.core.profile_manager import AccountProfile, ProfileManager
from engine.core.scheduler import TaskScheduler
from engine.core.stats import StatsTracker
from engine.storage.world_database import WorldDatabase


logger = logging.getLogger(__name__)


class EngineContext:
    """
    Contexto global do Sidecar. Agrupa o agendador, a conta, os gestores de ações,
    a configuração ativa e o canal de distribuição de eventos via WebSocket.
    """

    def __init__(
        self,
        scheduler: Optional[TaskScheduler] = None,
        config: Optional[BotConfig] = None,
        account: Optional[TribalAccount] = None,
        config_path: Optional[Path] = None,
        db: Optional[Any] = None,
    ):
        self.scheduler = scheduler or TaskScheduler()
        self.config = config or BotConfig()
        self.account = account
        self.config_path = config_path or Path("config.json")

        # Gestores de ecrãs/ações da Fase 2 e Fase 3
        self.main_building_manager = MainBuildingManager()
        self.place_manager = PlaceManager()
        self.farm_manager = FarmManager()
        self.recruitment_manager = RecruitmentManager(place_manager=self.place_manager)
        self.quest_manager = QuestManager()
        self.market_manager = MarketManager()
        self._map_cache: Dict[str, Tuple[float, Any]] = {}
        self.map_manager = MapManager()
        self.arbitrage_manager = EconomicArbitrageManager(
            main_building_manager=self.main_building_manager,
            recruitment_manager=self.recruitment_manager,
            place_manager=self.place_manager,
        )
        self.village_coordinator = MultiVillageCoordinator(
            main_building_manager=self.main_building_manager,
            recruitment_manager=self.recruitment_manager,
            farm_manager=self.farm_manager,
            market_manager=self.market_manager,
        )
        # Gestor de Defesa e Alarme de Ataques (Item 2.8)
        self.defense_manager = DefenseManager(
            place_manager=self.place_manager,
            map_manager=self.map_manager,
        )
        self._setup_defense_callbacks()

        # Sincronizador de Relógio e Gestor de Combate Milissegundo (Item 2.9)
        self.clock_sync = ClockSynchronizer()
        self.combat_manager = CombatManager(
            place_manager=self.place_manager,
            clock_sync=self.clock_sync,
        )

        # Gestores de Coleta, Academia e Inventário (Fase 4)
        self.scavenge_manager = ScavengeManager()
        self.snob_manager = SnobManager()
        self.inventory_manager = InventoryManager()

        # Gestor de Perfis e Base de Dados SQLite (Single-Active Session)
        self.profile_manager = ProfileManager(db=db) if db else ProfileManager()
        self._account_lock = asyncio.Lock()
        self.active_profile_id: Optional[str] = None

        # Cloud SQL PostgreSQL & AccountSessionManager (Singleton de Mutex e Concorrência Multi-Mundo)
        from engine.storage.cloud_db import get_cloud_db, AppUserRepository, GameAccountRepository, GameWorldRepository, VillageRepository
        from engine.core.account_session_manager import AccountSessionManager
        self.cloud_db = get_cloud_db()
        self.session_manager = AccountSessionManager.get_instance()
        if self.session_manager.orchestrator:
            self.session_manager.orchestrator.db = self.cloud_db
        self.user_repo = AppUserRepository(self.cloud_db)
        self.game_account_repo = GameAccountRepository(self.cloud_db)
        self.game_world_repo = GameWorldRepository(self.cloud_db)
        self.village_repo = VillageRepository(self.cloud_db)
        self.build_template_repo = self.cloud_db.build_template_repo
        self.current_app_user: Optional[Any] = None

        # Orquestrador Multi-Mundo Concorrente
        self.world_manager = MultiWorldManager(on_captcha_alert=self.notify_captcha_detected)
        if self.account:
            self.world_manager.instances[self.config.world] = WorldInstance(
                world=self.config.world,
                account=self.account,
                scheduler=self.scheduler,
                config=self.config,
                coordinator=self.village_coordinator,
                is_active=True,
            )
            self.world_manager.active_world = self.config.world

        # Cache de mapa
        self._map_cache: Dict[str, Tuple[float, MapData]] = {}

        # Clientes WebSocket ativos
        self.active_websockets: Set[WebSocket] = set()

        # Rastreadores de estatísticas e eficiência
        self.stats_trackers: Dict[str, StatsTracker] = {}
        self.stats_tracker = StatsTracker(world=self.config.world)
        self.stats_trackers[self.config.world] = self.stats_tracker
        if self.account:
            self.account.stats_tracker = self.stats_tracker
            self.account._broadcast_sync = self.broadcast_sync

        # Gestor de Dados do Mundo e Radar de Inativos
        self.world_database = WorldDatabase()
        self.world_data_worker = WorldDataWorker(db=self.world_database)
        self.inactivity_tracker = InactivityTracker(db=self.world_database)

        # Agendamento periódico contínuo de recolha de dados de mundo (background timeline)
        if self.scheduler and self.config.world:
            try:
                self.world_data_worker.schedule_periodic_sync(
                    scheduler=self.scheduler,
                    world=self.config.world,
                    domain=self.config.domain,
                    interval_hours=3.0,
                )
            except Exception as e:
                logger.debug(f"Aviso ao agendar sync periódico de mundo: {e}")

        # Estado e estatísticas
        self.start_time = time.time()
        self.last_captcha_alert: Optional[Dict[str, Any]] = None

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    # --- Gestão de Conexões WebSocket ---

    async def register_websocket(self, websocket: WebSocket) -> None:
        """Regista uma nova conexão WebSocket e envia o estado inicial."""
        self.active_websockets.add(websocket)
        logger.info(f"Cliente WebSocket conectado. Total ativos: {len(self.active_websockets)}")
        # Envia estado inicial de imediato
        await self.send_to_websocket(websocket, {
            "type": "INITIAL_STATE",
            "data": self.get_status_dict(),
        })

    def unregister_websocket(self, websocket: WebSocket) -> None:
        """Remove a conexão WebSocket fechada."""
        self.active_websockets.discard(websocket)
        logger.info(f"Cliente WebSocket desconectado. Total ativos: {len(self.active_websockets)}")

    async def send_to_websocket(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """Envia uma mensagem JSON para um cliente WebSocket específico de forma segura."""
        try:
            await websocket.send_json(message)
        except Exception:
            self.active_websockets.discard(websocket)

    async def broadcast(self, message_type: str, data: Dict[str, Any]) -> None:
        """Transmite uma mensagem para todos os clientes WebSocket conectados."""
        if not self.active_websockets:
            return

        payload = {
            "type": message_type,
            "timestamp": time.time(),
            "data": data,
        }

        dead_sockets: List[WebSocket] = []
        for ws in list(self.active_websockets):
            try:
                await ws.send_json(payload)
            except Exception:
                dead_sockets.append(ws)

        for ws in dead_sockets:
            self.active_websockets.discard(ws)

    def broadcast_sync(self, message_type: str, data: Dict[str, Any]) -> None:
        """Wrapper síncrono seguro para disparar broadcasts a partir de threads ou handlers síncronos."""
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                asyncio.create_task(self.broadcast(message_type, data))
        except RuntimeError:
            pass

    # --- Alertas e Eventos Específicos ---

    async def notify_captcha_detected(self, world: str, html_snippet: str = "") -> None:
        """Notifica o frontend de que um desafio anti-bot requer atenção do utilizador."""
        url = f"https://{world}.{self.config.domain}/game.php?screen=bot_protect"
        alert_data = {
            "world": world,
            "detected_at": time.time(),
            "url": url,
            "snippet": html_snippet[:600] if html_snippet else "",
        }
        self.last_captcha_alert = alert_data
        logger.critical("=" * 65)
        logger.critical(f"🚨 [ALERTA ANTI-BOT] Desafio Captcha detetado no mundo {world.upper()}!")
        logger.critical(f"👉 URL: {url}")
        logger.critical("👉 O motor foi pausado automaticamente para proteger a conta.")
        logger.critical("=" * 65)

        if hasattr(self, "on_captcha_alert") and callable(self.on_captcha_alert):
            try:
                self.on_captcha_alert(world, url)
            except Exception as e:
                logger.debug(f"Erro ao acionar on_captcha_alert: {e}")

        await self.broadcast("CAPTCHA_ALERT", alert_data)
        logger.critical(f"Alerta de Captcha transmitido para {len(self.active_websockets)} clientes WebSocket.")

    # --- Ações de Controlo do Motor ---

    def pause_scheduler(self) -> Dict[str, Any]:
        """Pausa o agendamento de tarefas."""
        self.scheduler.pause()
        self.broadcast_sync("SCHEDULER_STATE", {"is_running": False, "is_paused": True})
        return {"status": "paused", "message": "Motor de agendamento pausado."}

    def resume_scheduler(self) -> Dict[str, Any]:
        """Retoma o agendamento de tarefas."""
        self.scheduler.resume()
        self.last_captcha_alert = None
        self.broadcast_sync("SCHEDULER_STATE", {"is_running": True, "is_paused": False})
        return {"status": "resumed", "message": "Motor de agendamento retomado."}

    async def trigger_build_cycle(self) -> Dict[str, Any]:
        """Dispara manualmente um ciclo de verificação e evolução do Edifício Principal."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada."}

        v_id = self.account.current_village_id or 0
        task_id = f"ManualBuild-Village-{v_id}_{time.time_ns()}"

        async def _run():
            plan = self.config.get_active_build_plan(village_id=str(v_id))
            res = await self.main_building_manager.run_build_cycle(
                account=self.account,
                plan=plan,
                max_queue=self.config.building.max_queue,
                village_id=v_id,
            )
            if res:
                tracker = self.get_stats_tracker()
                tracker.record_building(
                    building=res,
                    village_id=v_id,
                )
                self.broadcast_sync("STATS_UPDATED", tracker.get_summary())

            # Atualiza recursos, edifícios e fila de construção via screen=main e tropas via screen=place
            await self.account.refresh_state()
            await self.account.refresh_village_details(v_id)
            self.broadcast_sync("VILLAGE_UPDATED", self.get_status_dict())
            building_state = await self.get_building_state(v_id)
            self.broadcast_sync("BUILDING_UPDATED", building_state)
            return res

        self.scheduler.schedule(
            name=f"ManualBuild-Village-{v_id}",
            priority=TaskPriority.BUILD,
            action=_run,
            delay_seconds=0.0,
            task_id=task_id,
        )
        return {"status": "scheduled", "task_id": task_id}

    async def trigger_farm_wave(self) -> Dict[str, Any]:
        """Força a execução imediata de uma onda de micro-farming."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada."}

        target_village = self.account.current_village_id or "active"
        task_id = f"ManualFarm-Village-{target_village}_{time.time_ns()}"

        async def _run():
            if self.config.farm.mode.lower() == "am_farm":
                await self.farm_manager.run_am_farm_wave(
                    account=self.account,
                    template=self.config.farm.template,
                    max_distance=self.config.farm.max_distance,
                    skip_losses=self.config.farm.skip_losses,
                    skip_wall=self.config.farm.skip_wall,
                )
            else:
                targets = [f"{x}|{y}" for x, y in self.config.farm.custom_targets]
                await self.farm_manager.run_place_farm_wave(
                    account=self.account,
                    targets=targets,
                    troops_to_send=self.config.farm.custom_troops,
                )

        self.scheduler.schedule(
            name=f"ManualFarm-Village-{target_village}",
            priority=TaskPriority.FARM,
            action=_run,
            delay_seconds=0.1,
            task_id=task_id,
        )
        return {"status": "scheduled", "task_id": task_id}

    async def trigger_recruit_cycle(self) -> Dict[str, Any]:
        """Força a execução imediata de um ciclo de recrutamento militar."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada."}

        v_id = self.account.current_village_id or 0
        target_village = v_id or "active"
        task_id = f"ManualRecruit-Village-{target_village}_{time.time_ns()}"

        async def _run():
            targets = self.config.get_village_recruitment_targets(village_id=str(v_id))
            res = await self.recruitment_manager.run_recruitment_cycle(
                account=self.account,
                targets=targets,
                batch_sizes=self.config.recruitment.batch_sizes,
                min_free_pop=self.config.recruitment.min_free_pop,
                village_id=v_id,
                max_queue_elements=getattr(self.config.recruitment, "max_queue_elements", 3),
            )
            # Atualiza estado da aldeia e emite eventos WebSocket para a interface
            await self.account.refresh_state()
            if v_id:
                await self.account.refresh_village_details(v_id)
            self.broadcast_sync("VILLAGE_UPDATED", self.get_status_dict())
            rec_state = await self.get_recruitment_state(v_id)
            self.broadcast_sync("RECRUITMENT_CYCLE_EXECUTED", rec_state)
            self.broadcast_sync("RECRUITMENT_UPDATED", rec_state)
            self.broadcast_sync("STATS_UPDATED", {"reason": "manual_recruit", "recruited": res})
            return res

        self.scheduler.schedule(
            name=f"ManualRecruit-Village-{target_village}",
            priority=TaskPriority.RECRUIT,
            action=_run,
            delay_seconds=0.1,
            task_id=task_id,
        )
        return {"status": "scheduled", "task_id": task_id}

    async def trigger_quest_cycle(self) -> Dict[str, Any]:
        """Força a execução imediata de um ciclo de missões e bónus diário (sem uso de itens)."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada."}

        target_village = self.account.current_village_id or "active"
        task_id = f"ManualQuest-Village-{target_village}_{time.time_ns()}"

        async def _run():
            res = await self.quest_manager.run_cycle(
                account=self.account,
                village_id=self.account.current_village_id,
                config=self.config.quest,
            )
            await self.broadcast("QUEST_CYCLE_COMPLETED", res)

        self.scheduler.schedule(
            name=f"ManualQuest-Village-{target_village}",
            priority=TaskPriority.QUEST,
            action=_run,
            delay_seconds=0.1,
            task_id=task_id,
        )
        return {"status": "scheduled", "task_id": task_id}

    async def trigger_map_farm_wave(self, radius: Optional[float] = None) -> Dict[str, Any]:
        """Dispara uma onda imediata de farming baseada no Scanner de Bárbaras do mapa."""
        if not self.account or not self.account.sid:
            return {"status": "error", "message": "Conta não conectada ou sem 'sid'."}

        target_village = self.account.current_village_id or "active"
        task_id = f"MapFarm-Village-{target_village}_{time.time_ns()}"

        async def _run():
            from engine.actions.place import UnitsCount
            raw_troops = getattr(self.config.farm, "custom_troops", {"spear": 5, "spy": 1})
            troops = UnitsCount.from_dict(raw_troops) if isinstance(raw_troops, dict) else UnitsCount(spear=5, spy=1)
            scan_radius = radius or getattr(self.config.farm, "map_scan_radius", 15.0)

            sent = await self.map_manager.run_map_farm_wave(
                account=self.account,
                farm_manager=self.farm_manager,
                troops=troops,
                radius=scan_radius,
                village_id=self.account.current_village_id,
            )
            await self.broadcast("MAP_FARM_COMPLETED", {"sent": sent, "radius": scan_radius})

        self.scheduler.schedule(
            name=f"MapFarm-Village-{target_village}",
            priority=TaskPriority.FARM,
            action=_run,
            delay_seconds=0.1,
            task_id=task_id,
        )
        return {"status": "scheduled", "task_id": task_id}

    async def trigger_renew_session(self) -> Dict[str, Any]:
        """Dispara a renovação do cookie 'sid' via WebView2 nativo."""
        if getattr(self, "on_renew_session", None):
            self.on_renew_session()
            return {"status": "success", "message": "A navegar para o ecrã de login do Tribal Wars..."}

        from engine.core.auth_manager import TribalAuthManager
        auth_mgr = TribalAuthManager(self.config_path)

        if not self.account:
            from engine.core.account import TribalAccount
            self.account = TribalAccount(
                world=self.config.world,
                sid=self.config.sid,
                domain=self.config.domain,
                proxy=self.config.proxy,
            )

        success = await auth_mgr.auto_renew_session(self.account, self.config)
        if success:
            self.config.sid = self.account.sid
            self.broadcast_sync("SESSION_RENEWED", {"world": self.account.world, "sid": self.account.sid[:12] + "..."})
            return {"status": "success", "message": "Sessão renovada e gravada com sucesso!"}
        return {"status": "error", "message": "Não foi possível capturar o cookie de sessão 'sid'."}


    def update_config_and_save(self, new_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Atualiza as configurações do bot em memória e grava as alterações agregadas à conta ativa no SQLite (data/accounts.db).
        """
        try:
            # 1. Obtém a configuração atual como dicionário
            current_raw = self.get_config_dict()

            # Atualiza recursivamente campos permitidos com fusão profunda (deep merge)
            def _deep_merge(target: dict, source: dict) -> None:
                for k, v in source.items():
                    if isinstance(v, dict) and isinstance(target.get(k), dict):
                        _deep_merge(target[k], v)
                    else:
                        target[k] = v

            _deep_merge(current_raw, new_data)

            # 2. Reconstrói BotConfig em memória
            from engine.config.settings import parse_config_dict
            self.config = parse_config_dict(current_raw)

            # 3. Se houver uma conta ativa, persiste diretamente no SQLite (data/accounts.db)
            if self.active_profile_id:
                self.profile_manager.save_account_config(self.active_profile_id, current_raw)
                logger.info(f"Configurações persistidas no SQLite para a conta ativa '{self.active_profile_id}'.")

            self.broadcast_sync("CONFIG_UPDATED", {"config": self.get_config_dict()})
            return {"status": "success", "message": "Configuração atualizada e persistida na base de dados SQLite."}
        except Exception as e:
            logger.error(f"Erro ao salvar configuração: {e}")
            return {"status": "error", "message": str(e)}

    # --- Dicionários de Estado Formatados ---

    def get_status_dict(self) -> Dict[str, Any]:
        """Retorna uma visão completa do estado atual para o frontend."""
        village_data = None
        player_data = None
        resources_dict = None
        troops_dict = {}

        if self.account:
            curr_v = self.account.current_village
            if curr_v:
                resources_dict = {
                    "wood": curr_v.resources.wood,
                    "stone": curr_v.resources.stone,
                    "iron": curr_v.resources.iron,
                    "storage_max": curr_v.resources.storage_max,
                    "pop": curr_v.resources.pop,
                    "pop_max": curr_v.resources.pop_max,
                    "free_pop": curr_v.resources.free_pop,
                }
                troops_raw = getattr(curr_v, "troops", None)
                troops_dict = troops_raw.to_dict() if hasattr(troops_raw, "to_dict") else (troops_raw or {})
                village_data = {
                    "id": curr_v.id,
                    "name": curr_v.name,
                    "coordinates": curr_v.coordinates,
                    "points": curr_v.points,
                    "resources": resources_dict,
                    "troops": troops_dict,
                }

            if self.account.player:
                p = self.account.player
                player_data = {
                    "id": p.id,
                    "name": p.name,
                    "points": p.points,
                    "villages_count": p.villages_count,
                }

        # Lista detalhada de aldeias com categoria e fallback
        villages_list = []
        total_resources_dict = {
            "wood": 0, "stone": 0, "iron": 0,
            "storage_max": 0, "pop": 0, "pop_max": 0, "free_pop": 0,
        }
        total_troops_dict = {}

        if self.account:
            vill_objs = [
                v for v in self.account.villages.values()
                if v.id > 0 and not (v.x == 0 and v.y == 0 and v.name.lower() in ("farm", "fazenda"))
            ]
            if not vill_objs and self.account.current_village and self.account.current_village.id > 0:
                vill_objs = [self.account.current_village]
            for v in vill_objs:
                v_dict = v.to_dict()
                cat = self.village_coordinator.get_village_category(self.account, self.config, v.id)
                cat_val = cat.value if hasattr(cat, "value") else str(cat)
                v_dict["category"] = cat_val
                villages_list.append(v_dict)

                if v.resources:
                    total_resources_dict["wood"] += v.resources.wood
                    total_resources_dict["stone"] += v.resources.stone
                    total_resources_dict["iron"] += v.resources.iron
                    total_resources_dict["storage_max"] += v.resources.storage_max
                    total_resources_dict["pop"] += v.resources.pop
                    total_resources_dict["pop_max"] += v.resources.pop_max
                    total_resources_dict["free_pop"] += v.resources.free_pop
                raw_v_troops = getattr(v, "troops", None)
                v_troops = raw_v_troops.to_dict() if hasattr(raw_v_troops, "to_dict") else (raw_v_troops or {})
                if isinstance(v_troops, dict):
                    for u_name, u_qty in v_troops.items():
                        total_troops_dict[u_name] = total_troops_dict.get(u_name, 0) + (u_qty or 0)

        # Se só temos 1 aldeia ou os totais forem 0, usa os recursos da aldeia atual
        if total_resources_dict["storage_max"] == 0 and resources_dict:
            total_resources_dict = resources_dict.copy()
        if not total_troops_dict and troops_dict:
            total_troops_dict = troops_dict.copy()

        # Balanceamento de recursos entre aldeias
        balance_summary = None
        if self.account and len(self.account.villages) > 0:
            balance_summary = self.village_coordinator.calculate_resource_balance(self.account)

        return {
            "engine": {
                "uptime_seconds": round(self.uptime_seconds, 1),
                "is_running": self.scheduler.is_running if self.scheduler else False,
                "is_paused": self.scheduler.is_paused if self.scheduler else False,
                "queue_size": self.scheduler.queue_size if self.scheduler else 0,
            },
            "active_profile_id": self.active_profile_id,
            "accounts": self.profile_manager.list_profiles(),
            "active_world": self.world_manager.active_world or self.config.world,
            "worlds": self.world_manager.list_worlds(),
            "account": {
                "world": self.config.world,
                "domain": self.config.domain,
                "has_sid": bool(self.account and self.account.sid),
                "proxy": self.config.proxy,
                "player": player_data,
                "village": village_data,
                "villages": villages_list,
            },
            "resource_balance": balance_summary,
            "resources": resources_dict,
            "troops": troops_dict,
            "total_resources": total_resources_dict,
            "total_troops": total_troops_dict,
            "modules": {
                "building": {
                    "enabled": self.config.building.enabled,
                    "template": self.config.building.template,
                    "max_queue": self.config.building.max_queue,
                    "interval_seconds": self.config.building.interval_seconds,
                },
                "farm": {
                    "enabled": self.config.farm.enabled,
                    "mode": self.config.farm.mode,
                    "template": self.config.farm.template,
                    "interval_minutes": self.config.farm.interval_minutes,
                },
                "recruitment": {
                    "enabled": self.config.recruitment.enabled,
                    "interval_minutes": self.config.recruitment.interval_minutes,
                    "min_free_pop": self.config.recruitment.min_free_pop,
                    "targets": self.config.recruitment.targets,
                    "batch_sizes": self.config.recruitment.batch_sizes,
                },
                "quest": {
                    "enabled": self.config.quest.enabled,
                    "auto_claim_quests": self.config.quest.auto_claim_quests,
                    "auto_daily_bonus": self.config.quest.auto_daily_bonus,
                    "safe_storage_margin": self.config.quest.safe_storage_margin,
                    "interval_minutes": self.config.quest.interval_minutes,
                },
                "market": {
                    "enabled": getattr(self.config.market, "enabled", False),
                    "auto_balance_enabled": getattr(self.config.market, "auto_balance", True),
                    "auto_balance": getattr(self.config.market, "auto_balance", True),
                    "interval_minutes": getattr(self.config.market, "interval_minutes", 30.0),
                },
                "defense": {
                    "enabled": getattr(self.config.defense, "enabled", True),
                    "auto_dodge_enabled": getattr(self.config.defense, "auto_dodge_enabled", False),
                    "dodge_lead_time_seconds": getattr(self.config.defense, "dodge_lead_time_seconds", 30),
                    "dodge_cancel_delay_seconds": getattr(self.config.defense, "dodge_cancel_delay_seconds", 5),
                    "escape_coords": getattr(self.config.defense, "escape_coords", None),
                    "auto_dodge_all_units": getattr(self.config.defense, "auto_dodge_all_units", True),
                    "alarm_sound_enabled": getattr(self.config.defense, "alarm_sound_enabled", True),
                    "check_interval_seconds": getattr(self.config.defense, "check_interval_seconds", 20.0),
                    "incomings_count": self.defense_manager.last_incomings_count,
                    "active_incomings": [inc.to_dict() for inc in self.defense_manager.active_incomings.values()],
                    "active_dodges": [d.to_dict() for d in self.defense_manager.active_dodges.values()],
                },
                "combat": {
                    "clock_stats": self.clock_sync.get_stats().to_dict(),
                    "operations": self.combat_manager.get_operations(),
                    "config": {
                        "noble_train_gap_ms": getattr(getattr(self.config, "combat", None), "noble_train_gap_ms", 100),
                        "failsafe_enabled": getattr(getattr(self.config, "combat", None), "failsafe_enabled", True),
                        "failsafe_max_spread_ms": getattr(getattr(self.config, "combat", None), "failsafe_max_spread_ms", 400),
                        "default_noble_escort": getattr(getattr(self.config, "combat", None), "default_noble_escort", {"axe": 50, "light": 20}),
                        "snipe_tolerance_ms": getattr(getattr(self.config, "combat", None), "snipe_tolerance_ms", 150),
                    },
                },
                "scavenge": {
                    "enabled": getattr(getattr(self.config, "scavenge", None), "enabled", False),
                    "auto_unlock": getattr(getattr(self.config, "scavenge", None), "auto_unlock", True),
                    "eligible_units": getattr(getattr(self.config, "scavenge", None), "eligible_units", ["spear", "sword", "axe", "archer", "light"]),
                    "min_reserved_units": getattr(getattr(self.config, "scavenge", None), "min_reserved_units", {"spear": 10, "sword": 10}),
                    "check_interval_seconds": getattr(getattr(self.config, "scavenge", None), "check_interval_seconds", 300.0),
                },
                "snob": {
                    "auto_mint_enabled": getattr(getattr(self.config, "snob", None), "auto_mint_enabled", False),
                    "storage_threshold_percent": getattr(getattr(self.config, "snob", None), "storage_threshold_percent", 85.0),
                    "auto_recruit_nobles": getattr(getattr(self.config, "snob", None), "auto_recruit_nobles", False),
                },
            },
            "stats": self.get_stats_tracker().get_summary(),
            "captcha_alert": self.last_captcha_alert,
        }

    async def refresh_village_data(self) -> Dict[str, Any]:
        """Atualiza ativamente recursos, tropas, edifícios e estado da aldeia ativa."""
        if not self.account or not self.account.sid:
            return {"status": "error", "message": "Conta não conectada ou sem 'sid'."}
        try:
            # 1. Atualiza recursos, edifícios e fila de construção via screen=main
            await self.account.refresh_state()
            # 2. Atualiza tropas disponíveis via screen=place
            await self.account.refresh_village_details()
            # 3. Persiste o estado atualizado das aldeias na Cloud SQL
            try:
                await self.sync_account_villages_to_cloud()
            except Exception as se:
                logger.debug(f"Aviso ao sincronizar aldeias com Cloud SQL: {se}")
            status_dict = self.get_status_dict()
            await self.broadcast("VILLAGE_UPDATED", status_dict)
            await self.broadcast("STATUS_UPDATE", status_dict)
            return {"status": "success", "data": status_dict}
        except Exception as e:
            logger.error(f"Erro ao atualizar dados da aldeia: {e}")
            return {"status": "error", "message": str(e)}

    async def claim_all_quests_safe(self) -> Dict[str, Any]:
        """Resgata todas as missões concluídas com validação de armazém/população."""
        if not self.account or not self.account.sid:
            return {"status": "error", "message": "Conta não conectada ou sem 'sid'."}
        try:
            res = await self.quest_manager.claim_all_valid_quests(
                account=self.account,
                safe_mode=True,
                safe_margin=self.config.quest.safe_storage_margin,
            )
            # Atualiza recursos após os resgates
            try:
                await self.account.refresh_state()
            except Exception as e:
                logger.debug(f"Aviso ao atualizar estado pós-missões: {e}")
            status_dict = self.get_status_dict()
            await self.broadcast("QUESTS_CLAIMED", res)
            await self.broadcast("VILLAGE_UPDATED", status_dict)
            return {
                "status": "success",
                "claimed_count": res.get("claimed", 0),
                "skipped_count": res.get("skipped", 0),
                "data": status_dict,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_config_dict(self) -> Dict[str, Any]:
        """Retorna as configurações em formato serializável."""
        return {
            "world": self.config.world,
            "domain": self.config.domain,
            "sid": self.config.sid[:12] + "..." if self.config.sid else "",
            "auth": {
                "username": self.config.auth.username,
                "has_password": bool(self.config.auth.password),
                "auto_login": self.config.auth.auto_login,
                "keep_alive": self.config.auth.keep_alive,
                "keep_alive_interval_minutes": self.config.auth.keep_alive_interval_minutes,
            },
            "building": {
                "enabled": self.config.building.enabled,
                "template": self.config.building.template,
                "max_queue": self.config.building.max_queue,
                "interval_seconds": self.config.building.interval_seconds,
                "custom_plan": self.config.building.custom_plan,
            },
            "farm": {
                "enabled": self.config.farm.enabled,
                "mode": self.config.farm.mode,
                "template": self.config.farm.template,
                "max_distance": self.config.farm.max_distance,
                "skip_losses": self.config.farm.skip_losses,
                "skip_wall": self.config.farm.skip_wall,
                "interval_minutes": self.config.farm.interval_minutes,
                "custom_targets": self.config.farm.custom_targets,
                "custom_troops": self.config.farm.custom_troops,
            },
            "recruitment": {
                "enabled": self.config.recruitment.enabled,
                "interval_minutes": self.config.recruitment.interval_minutes,
                "min_free_pop": self.config.recruitment.min_free_pop,
                "targets": self.config.recruitment.targets,
                "batch_sizes": self.config.recruitment.batch_sizes,
            },
            "quest": {
                "enabled": self.config.quest.enabled,
                "auto_claim_quests": self.config.quest.auto_claim_quests,
                "auto_daily_bonus": self.config.quest.auto_daily_bonus,
                "safe_storage_margin": self.config.quest.safe_storage_margin,
                "interval_minutes": self.config.quest.interval_minutes,
            },
            "market": {
                "enabled": getattr(self.config.market, "enabled", False),
                "auto_balance": getattr(self.config.market, "auto_balance", True),
                "auto_balance_enabled": getattr(self.config.market, "auto_balance", True),
                "reserve_margin": getattr(self.config.market, "reserve_margin", 0.20),
                "reserve_margin_percent": getattr(self.config.market, "reserve_margin", 0.20),
                "interval_minutes": getattr(self.config.market, "interval_minutes", 30.0),
                "min_transfer_amount": getattr(self.config.market, "min_transfer_amount", 1000),
                "max_merchants_percent": getattr(self.config.market, "max_merchant_ratio", 0.80),
                "max_merchant_ratio": getattr(self.config.market, "max_merchant_ratio", 0.80),
            },
            "villages": {
                str(vid): {
                    "category": str(vcfg.category).lower().strip() if getattr(vcfg, "category", None) else "attack",
                    "building_template": getattr(vcfg, "building_template", None),
                    "recruitment_targets": getattr(vcfg, "recruitment_targets", None),
                }
                for vid, vcfg in self.config.villages.items()
            },
        }

    async def switch_village(self, village_id: int) -> Dict[str, Any]:
        """Alterna a aldeia ativa no bot e notifica a interface."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada."}
        try:
            v_data = await self.account.switch_village(village_id)
            self.broadcast_sync("VILLAGE_SWITCHED", {
                "village_id": village_id,
                "village": v_data.to_dict(),
            })
            self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
            return {
                "status": "success",
                "message": f"Aldeia alterada para {v_data.name} ({v_data.coordinates}).",
                "village": v_data.to_dict(),
            }
        except Exception as e:
            logger.error(f"Erro ao alternar para aldeia {village_id}: {e}")
            return {"status": "error", "message": str(e)}

    # --- Aliases e Utilitários de Perfis ---

    def list_profiles(self) -> List[Dict[str, Any]]:
        """Alias para list_accounts."""
        return self.list_accounts()

    async def switch_profile(self, profile_id: str) -> Dict[str, Any]:
        return await self.activate_account(profile_id)

    async def test_proxy(self, proxy_url: str) -> Dict[str, Any]:
        """Testa conectividade de um proxy residencial/dedicado."""
        from engine.core.profile_manager import test_proxy_connection
        return await test_proxy_connection(proxy_url)

# --- Gestão Multi-Mundo Concorrente ---

    def list_worlds(self) -> List[Dict[str, Any]]:
        """Lista todos os mundos geridos e os respetivos estados operacionais."""
        return self.world_manager.list_worlds()

    async def register_world(
        self,
        world: str,
        sid: str,
        domain: str = "tribalwars.com.pt",
        proxy: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Regista e inicializa um novo mundo em execução concorrente paralela."""
        inst = await self.world_manager.register_world(
            world=world,
            sid=sid,
            domain=domain,
            proxy=proxy,
            config=self.config,
            auto_start=True,
        )
        self.broadcast_sync("WORLDS_UPDATED", {"worlds": self.world_manager.list_worlds()})
        return {"status": "success", "message": f"Mundo '{world}' registado e ativo.", "world": inst.to_dict()}

    async def switch_world(self, world: str) -> Dict[str, Any]:
        """Alterna o foco do dashboard para outro mundo em execução, auto-registando apenas se a conta tiver acesso válido."""
        world_key = world.strip().lower()
        inst = self.world_manager.get_instance(world_key)
        if not inst:
            if self.config.sid:
                logger.info(f"A verificar se a conta possui aldeia/acesso no mundo '{world_key}'...")
                test_account = TribalAccount(
                    world=world_key,
                    sid=self.config.sid,
                    domain=self.config.domain,
                    proxy=self.config.proxy,
                )
                try:
                    await test_account.init_session()
                    await test_account.refresh_state()
                    if not test_account.current_village_id and not test_account.villages:
                        await test_account.close()
                        return {
                            "status": "error",
                            "message": f"A tua conta não possui aldeias no mundo '{world_key.upper()}'. Verifica se estás registado nesse mundo."
                        }
                    await test_account.close()
                except Exception as e:
                    try:
                        await test_account.close()
                    except Exception as close_err:
                        logger.debug(f"Aviso ao fechar sessão de teste: {close_err}")
                    logger.warning(f"Falha ao validar conta no mundo '{world_key}': {e}")
                    return {
                        "status": "error",
                        "message": f"Sem acesso ao mundo '{world_key.upper()}': {e}. Certifica-te de que a conta existe e tem acesso ativo a este mundo."
                    }

                logger.info(f"Acesso validado! A inicializar instância multi-mundo para '{world_key}'...")
                inst = await self.world_manager.register_world(
                    world=world_key,
                    sid=self.config.sid,
                    domain=self.config.domain,
                    proxy=self.config.proxy,
                    config=None,
                    auto_start=True,
                )
                self.broadcast_sync("WORLDS_UPDATED", {"worlds": self.world_manager.list_worlds()})
            else:
                return {"status": "error", "message": f"Mundo '{world}' não encontrado e nenhum 'sid' configurado."}

        self.world_manager.set_active_world(world_key)
        self.account = inst.account
        self.scheduler = inst.scheduler
        self.config = inst.config

        # Atualiza e persiste o mundo ativo no config.json
        self.update_config_and_save({"world": world_key})

        status = self.get_status_dict()
        self.broadcast_sync("WORLD_SWITCHED", {"active_world": world_key, "status": status})
        return {"status": "success", "message": f"Dashboard focado no mundo '{world_key}'.", "world": inst.to_dict()}

    async def discover_player_worlds(self) -> Dict[str, Any]:
        """Descobre os mundos do utilizador via portal oficial onde a conta tem aldeias criadas."""
        if not self.account or not self.account.sid:
            return {"status": "error", "message": "Conta não conectada ou sem 'sid'.", "worlds": []}
        try:
            active_worlds = await self.account.discover_active_worlds()
            if self.config.world and self.config.world not in active_worlds:
                active_worlds.append(self.config.world)
            return {"status": "success", "worlds": active_worlds}
        except Exception as e:
            logger.error(f"Erro ao descobrir mundos: {e}")
            return {"status": "error", "message": str(e), "worlds": [self.config.world] if self.config.world else []}

    # --- Rotas Multi-Aldeia & Categorização ---

    def set_village_category(self, village_id: int, category: str, world: Optional[str] = None) -> Dict[str, Any]:
        """Atribui tipo de aldeia (estritamente 'attack' ou 'defense') a uma aldeia e persiste no SQLite."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        cfg = inst.config if inst else self.config
        if not acc:
            return {"status": "error", "message": "Conta não inicializada."}

        raw = str(category).lower().strip()
        norm_cat = "defense" if "def" in raw else "attack"

        success = self.village_coordinator.set_village_category(acc, cfg, village_id, norm_cat)
        if success:
            new_v_data = {
                "villages": {
                    str(village_id): {
                        "category": norm_cat,
                    }
                }
            }
            self.update_config_and_save(new_v_data)
            self.broadcast_sync("VILLAGE_CATEGORY_UPDATED", {
                "village_id": village_id,
                "category": norm_cat,
            })
            status = self.get_status_dict()
            self.broadcast_sync("STATUS_UPDATE", status)
            self.broadcast_sync("VILLAGE_UPDATED", status)
            return {"status": "success", "message": f"Aldeia {village_id} categorizada como '{norm_cat}'."}
        return {"status": "error", "message": "Falha ao definir categoria."}

    async def sync_and_get_all_villages(self, world: Optional[str] = None, force_sync: bool = True) -> Dict[str, Any]:
        """Retorna visão detalhada de todas as aldeias da conta com categorias e recursos."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        cfg = inst.config if inst else self.config
        if not acc:
            return {"status": "error", "message": "Conta não inicializada."}

        if force_sync and acc.sid:
            try:
                await self.village_coordinator.sync_all_villages(acc)
            except Exception as e:
                logger.debug(f"[{acc.world}] Erro suave ao sincronizar aldeias: {e}")

        villages_data = []
        vill_list = [
            v for v in acc.villages.values()
            if v.id > 0 and not (v.x == 0 and v.y == 0 and v.name.lower() in ("farm", "fazenda"))
        ]
        if not vill_list and acc.current_village and acc.current_village.id > 0:
            vill_list = [acc.current_village]
        for v in vill_list:
            cat = self.village_coordinator.get_village_category(acc, cfg, v.id)
            cat_val = cat.value if hasattr(cat, "value") else str(cat)
            v_dict = v.to_dict()
            v_dict["category"] = cat_val
            villages_data.append(v_dict)

        balance = self.village_coordinator.calculate_resource_balance(acc)
        status = self.get_status_dict()
        self.broadcast_sync("STATUS_UPDATE", status)
        self.broadcast_sync("VILLAGE_UPDATED", status)

        return {
            "world": acc.world,
            "count": len(villages_data),
            "villages": villages_data,
            "balance": balance,
        }

    async def trigger_all_villages_cycle(self, world: Optional[str] = None) -> Dict[str, Any]:
        """Dispara ciclo coordenado em todas as aldeias da conta (Construção + Recrutamento)."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        cfg = inst.config if inst else self.config
        if not acc:
            return {"status": "error", "message": "Conta não inicializada."}

        res = await self.village_coordinator.run_coordinated_cycle(acc, cfg)
        self.broadcast_sync("ALL_VILLAGES_CYCLE_DONE", res)
        return {"status": "success", "results": res}

    # --- Visualizador de Mapa e Comandos Rápidos ---

    async def get_map_data(
        self,
        center_x: Optional[int] = None,
        center_y: Optional[int] = None,
        radius: float = 15.0,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Obtém dados estruturados do mapa em torno de coordenadas com cache inteligente."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada.", "villages": []}

        v_id = self.account.current_village_id or 0
        curr_village = self.account.villages.get(v_id)
        cx = center_x if center_x is not None else (curr_village.x if curr_village else 500)
        cy = center_y if center_y is not None else (curr_village.y if curr_village else 500)
        cache_key = f"{self.account.world}_{cx}_{cy}_{radius}"

        now = time.time()
        if not force_refresh and cache_key in self._map_cache:
            ts, cached_data = self._map_cache[cache_key]
            if now - ts < 60.0:
                return {"status": "success", "cached": True, **cached_data.to_dict()}

        try:
            map_data = await self.map_manager.get_map(
                account=self.account,
                center_x=cx,
                center_y=cy,
                radius=radius,
                village_id=v_id,
            )
            self._map_cache[cache_key] = (now, map_data)
            return {"status": "success", "cached": False, **map_data.to_dict()}
        except Exception as e:
            logger.error(f"Erro ao carregar mapa: {e}")
            return {"status": "error", "message": str(e), "villages": []}


    async def send_quick_attack(
        self,
        target_x: int,
        target_y: int,
        spear: int = 0,
        sword: int = 0,
        axe: int = 0,
        spy: int = 0,
        light: int = 0,
    ) -> Dict[str, Any]:
        """Envia um comando de ataque/farm rápido para as coordenadas especificadas."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada."}
        try:
            from engine.actions.place import UnitsCount
            troops = UnitsCount(spear=spear, sword=sword, axe=axe, spy=spy, light=light)
            res = await self.place_manager.send_attack(
                account=self.account,
                target_x=target_x,
                target_y=target_y,
                troops=troops,
            )
            # Registo de métricas
            tracker = self.get_stats_tracker()
            tracker.record_command(
                command_type="attack",
                target_coords=f"{target_x}|{target_y}",
                units={"spear": spear, "sword": sword, "axe": axe, "spy": spy, "light": light},
                success=True,
            )
            self.broadcast_sync("STATS_UPDATED", tracker.get_summary())

            return {
                "status": "success",
                "message": f"Ataque enviado para ({target_x}|{target_y})!",
                "command_id": res.command_id,
                "duration": res.duration,
            }
        except Exception as e:
            logger.error(f"Erro ao enviar ataque rápido para ({target_x}|{target_y}): {e}")
            tracker = self.get_stats_tracker()
            tracker.record_command(
                command_type="attack",
                target_coords=f"{target_x}|{target_y}",
                units={"spear": spear, "sword": sword, "axe": axe, "spy": spy, "light": light},
                success=False,
            )
            return {"status": "error", "message": str(e)}

    # --- Mercado & Balanceamento de Recursos ---

    async def get_market_state(self, village_id: Optional[int] = None) -> Dict[str, Any]:
        """Obtém o estado do mercado (mercadores e transportes) de uma aldeia."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada."}
        v_id = village_id or self.account.current_village_id or 0
        state = await self.market_manager.get_market_state(self.account, village_id=v_id, include_offers=True)
        return {"status": "success", "market": state.to_dict()}

    async def send_market_resources(
        self,
        source_village_id: int,
        target_village_id: int,
        wood: int = 0,
        stone: int = 0,
        iron: int = 0,
    ) -> Dict[str, Any]:
        """Envia recursos de uma aldeia de origem para destino via mercadores."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada."}
        success = await self.market_manager.send_resources(
            account=self.account,
            source_village_id=source_village_id,
            target_village_id=target_village_id,
            wood=wood,
            stone=stone,
            iron=iron,
        )
        if success:
            self.broadcast_sync("MARKET_RESOURCES_SENT", {
                "source_village_id": source_village_id,
                "target_village_id": target_village_id,
                "wood": wood,
                "stone": stone,
                "iron": iron,
            })
            return {
                "status": "success",
                "message": f"Recursos enviados com sucesso ({wood}W, {stone}S, {iron}I)!",
            }
        return {
            "status": "error",
            "message": "Falha ao enviar recursos pelo mercado (mercadores/recursos insuficientes ou limite de armazém excedido).",
        }

    def get_resource_balancing_plan(self) -> Dict[str, Any]:
        """Calcula o plano de transferências recomendado para balanceamento global."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada."}
        orders = self.market_manager.calculate_balancing_transfers(self.account)
        balance_summary = self.village_coordinator.calculate_resource_balance(self.account)
        return {
            "status": "success",
            "balance_summary": balance_summary,
            "planned_orders": [o.to_dict() for o in orders],
            "total_orders": len(orders),
        }

    async def trigger_resource_balancing(self) -> Dict[str, Any]:
        """Dispara a execução imediata de um ciclo de balanceamento de recursos entre aldeias."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada."}
        if not self.config.market.enabled:
            return {"status": "error", "message": "O módulo de Mercado está desativado nas configurações."}
        res = await self.market_manager.run_balancing_cycle(self.account)
        self.broadcast_sync("MARKET_BALANCING_DONE", res)
        return res

    async def create_market_offer(
        self,
        village_id: int,
        sell_res: str,
        sell_amount: int,
        buy_res: str,
        buy_amount: int,
        max_time: int = 10,
        multi: int = 1,
    ) -> Dict[str, Any]:
        """Cria uma oferta de troca de recursos no mercado próprio."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada."}
        success = await self.market_manager.create_market_offer(
            account=self.account,
            village_id=village_id,
            sell_res=sell_res,
            sell_amount=sell_amount,
            buy_res=buy_res,
            buy_amount=buy_amount,
            max_time=max_time,
            multi=multi,
        )
        if success:
            return {"status": "success", "message": "Oferta publicada com sucesso no mercado!"}
        return {"status": "error", "message": "Falha ao criar oferta no mercado."}

    # --- Métricas & Estatísticas de Eficiência ---

    def get_stats_tracker(self, world: Optional[str] = None, account_id: Optional[str] = None) -> StatsTracker:
        """Obtém ou instancia o rastreador de estatísticas da conta e mundo ativos/solicitados."""
        target_world = world or (self.world_manager.active_world if hasattr(self, "world_manager") else None) or self.config.world
        target_acc = account_id or self.active_profile_id or getattr(self.account, "username", None) or (self.account.player.name if self.account and self.account.player else "default")
        tracker_key = f"{target_acc}_{target_world}"
        if tracker_key not in self.stats_trackers:
            self.stats_trackers[tracker_key] = StatsTracker(world=target_world, account_id=target_acc)
        tracker = self.stats_trackers[tracker_key]
        if self.account and (not world or world == self.account.world):
            self.account.stats_tracker = tracker
            self.account._broadcast_sync = self.broadcast_sync
        return tracker

    def get_stats_summary(self, world: Optional[str] = None) -> Dict[str, Any]:
        """Retorna resumo consolidado de estatísticas e KPIs de rendimento."""
        tracker = self.get_stats_tracker(world)
        return {"status": "success", "summary": tracker.get_summary()}

    def get_stats_history(
        self, hours: int = 24, days: int = 7, world: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retorna séries temporais para os gráficos de rendimento e histórico recente."""
        tracker = self.get_stats_tracker(world)
        history = tracker.get_history(hours=hours, days=days)
        return {"status": "success", "history": history}

    def reset_stats(self, world: Optional[str] = None) -> Dict[str, Any]:
        """Reinicia os registos de estatísticas do mundo ativo."""
        tracker = self.get_stats_tracker(world)
        tracker.reset_stats()
        self.broadcast_sync("STATS_UPDATED", tracker.get_summary())
        return {
            "status": "success",
            "message": f"Estatísticas do mundo '{tracker.world}' reiniciadas com sucesso.",
        }

    # --- Edifício Principal (Roadmap & Fila) ---

    async def get_building_state(self, village_id: Optional[int] = None) -> Dict[str, Any]:
        """Retorna o estado detalhado do Edifício Principal, fila e próximos passos."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada."}
        v_id = village_id or self.account.current_village_id or 0
        try:
            state = await self.main_building_manager.get_state(self.account, village_id=v_id)
            plan = self.config.get_active_build_plan(village_id=str(v_id))
            curr_v = self.account.villages.get(v_id)
            resources = curr_v.resources if curr_v else None
            upcoming = self.main_building_manager.get_upcoming_plan(state, plan, resources=resources)
            candidate = self.main_building_manager.get_next_build_candidate(state, plan, resources=resources)

            # Calcula contagem de concluídos e total do plano
            completed_count = sum(1 for item in upcoming if item.get("status") == "completed")
            total_plan_count = len(plan)
            progress_pct = round((completed_count / total_plan_count * 100.0), 1) if total_plan_count > 0 else 100.0

            next_target = None
            if candidate:
                from engine.actions.main_building import BUILDING_NAMES
                b_name = BUILDING_NAMES.get(candidate.building, candidate.building)
                next_target = {
                    "building": candidate.building,
                    "building_name": b_name,
                    "target_level": candidate.target_level,
                    "wood": candidate.wood,
                    "stone": candidate.stone,
                    "iron": candidate.iron,
                    "pop": candidate.pop,
                    "can_build": candidate.can_build,
                    "can_afford": candidate.can_build,
                    "error_reason": candidate.error_reason,
                }
            else:
                next_item = next((item for item in upcoming if item.get("status") == "next"), None)
                if next_item:
                    next_target = {
                        "building": next_item["building"],
                        "building_name": next_item["building_name"],
                        "target_level": next_item["target_level"],
                        "wood": next_item.get("wood", 0),
                        "stone": next_item.get("stone", 0),
                        "iron": next_item.get("iron", 0),
                        "pop": next_item.get("pop", 0),
                        "can_build": next_item.get("can_afford", False),
                        "can_afford": next_item.get("can_afford", False),
                        "error_reason": "A aguardar recursos suficientes" if not next_item.get("can_afford", False) else None,
                    }

            return {
                "status": "success",
                "village_id": v_id,
                "template": self.config.get_village_template(str(v_id)),
                "enabled": getattr(self.config.building, "enabled", True),
                "interval_seconds": getattr(self.config.building, "interval_seconds", 75.0),
                "max_queue": getattr(self.config.building, "max_queue", 2),
                "queue": [
                    {
                        "order_id": q.order_id,
                        "building": q.building,
                        "building_name": q.building_name,
                        "target_level": q.target_level,
                        "timer_str": q.timer_str,
                        "cancel_url": q.cancel_url,
                    }
                    for q in state.queue
                ],
                "buildings": state.buildings,
                "virtual_levels": state.virtual_levels,
                "upcoming": upcoming,
                "next_target": next_target,
                "plan_total": total_plan_count,
                "plan_completed": completed_count,
                "completed_count": completed_count,
                "progress_pct": progress_pct,
                "scheduler_running": self.scheduler.is_running and not self.scheduler.is_paused,
            }
        except Exception as e:
            logger.error(f"Erro ao obter estado de construção: {e}")
            return {"status": "error", "message": str(e)}

    async def cancel_building_order(self, order_id: str, village_id: Optional[int] = None) -> Dict[str, Any]:
        """Cancela uma ordem de construção em andamento."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada."}
        v_id = village_id or self.account.current_village_id or 0
        success = await self.main_building_manager.cancel_order(self.account, order_id=order_id, village_id=v_id)
        if success:
            self.broadcast_sync("BUILDING_ORDER_CANCELLED", {"order_id": order_id, "village_id": v_id})
            return {"status": "success", "message": "Ordem de construção cancelada com sucesso!"}
        return {"status": "error", "message": "Não foi possível cancelar a ordem de construção."}

    def toggle_building_module(
        self,
        enabled: Optional[bool] = None,
        interval_seconds: Optional[float] = None,
        max_queue: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Ativa/desativa ou ajusta a rotina de auto-construção contínua."""
        update_data = {}
        if enabled is not None:
            update_data["enabled"] = bool(enabled)
            self.config.building.enabled = bool(enabled)
        if interval_seconds is not None:
            update_data["interval_seconds"] = float(interval_seconds)
            self.config.building.interval_seconds = float(interval_seconds)
        if max_queue is not None:
            update_data["max_queue"] = int(max_queue)
            self.config.building.max_queue = int(max_queue)

        self.update_config_and_save({"building": update_data})
        if self.config.building.enabled and self.account and self.scheduler:
            plan = self.config.get_active_build_plan()
            self.main_building_manager.schedule_auto_build(
                scheduler=self.scheduler,
                account=self.account,
                plan=plan,
                max_queue=self.config.building.max_queue,
                interval_seconds=self.config.building.interval_seconds,
                enabled_check=lambda: self.config.building.enabled,
                bot_config=self.config,
            )
        self.broadcast_sync("MODULE_TOGGLED", {"module": "building", "enabled": self.config.building.enabled})
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {
            "status": "success",
            "message": f"Construção Automática {'ATIVADA' if self.config.building.enabled else 'DESATIVADA'}.",
            "enabled": self.config.building.enabled,
        }

    # --- Recrutamento Militar & Tropas em Treino ---

    def toggle_recruitment_module(
        self,
        enabled: Optional[bool] = None,
        interval_minutes: Optional[float] = None,
        min_free_pop: Optional[int] = None,
        max_queue_elements: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Ativa/desativa ou ajusta a rotina de auto-recrutamento contínuo."""
        update_data = {}
        if enabled is not None:
            update_data["enabled"] = bool(enabled)
            self.config.recruitment.enabled = bool(enabled)
        if interval_minutes is not None:
            update_data["interval_minutes"] = float(interval_minutes)
            self.config.recruitment.interval_minutes = float(interval_minutes)
        if min_free_pop is not None:
            update_data["min_free_pop"] = int(min_free_pop)
            self.config.recruitment.min_free_pop = int(min_free_pop)
        if max_queue_elements is not None:
            update_data["max_queue_elements"] = int(max_queue_elements)
            self.config.recruitment.max_queue_elements = int(max_queue_elements)

        self.update_config_and_save({"recruitment": update_data})
        if self.config.recruitment.enabled and self.account and self.scheduler:
            self.recruitment_manager.schedule_auto_recruit(
                scheduler=self.scheduler,
                account=self.account,
                recruit_config=self.config.recruitment,
                enabled_check=lambda: self.config.recruitment.enabled,
                bot_config=self.config,
            )
        self.broadcast_sync("MODULE_TOGGLED", {"module": "recruitment", "enabled": self.config.recruitment.enabled})
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {
            "status": "success",
            "message": f"Recrutamento Automático {'ATIVADO' if self.config.recruitment.enabled else 'DESATIVADO'}.",
            "enabled": self.config.recruitment.enabled,
        }

    async def get_recruitment_state(self, village_id: Optional[int] = None) -> Dict[str, Any]:
        """Consulta o estado das filas de treino e unidades disponíveis nos edifícios militares."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada."}
        v_id = village_id or self.account.current_village_id or 0
        try:
            from engine.config.settings import DEFAULT_ATTACK_MODEL, DEFAULT_DEFENSE_MODEL
            targets = self.config.get_village_recruitment_targets(village_id=str(v_id))
            batch_sizes = self.config.recruitment.batch_sizes
            models = getattr(self.config.recruitment, "models", {
                "attack": DEFAULT_ATTACK_MODEL.copy(),
                "defense": DEFAULT_DEFENSE_MODEL.copy(),
            })
            village_cat = "defense"
            if self.village_coordinator:
                cat_obj = self.village_coordinator.get_village_category(self.account, self.config, v_id)
                village_cat = cat_obj.value if hasattr(cat_obj, "value") else str(cat_obj)

            buildings_data = {}
            total_in_queue_all: Dict[str, int] = {}
            available_units_all: Dict[str, int] = {}
            active_orders_list = []

            for bld in ("barracks", "stable", "garage"):
                try:
                    b_state = await self.recruitment_manager.get_building_state(self.account, bld, village_id=v_id)
                    bld_orders = []
                    for q in b_state.queue:
                        order_item = {
                            "building": bld,
                            "unit": q.unit,
                            "unit_name": getattr(q, "unit_name", q.unit),
                            "count": q.count,
                            "timer_str": q.timer_str,
                            "finish_time": q.finish_time,
                            "cancel_url": q.cancel_url,
                        }
                        bld_orders.append(order_item)
                        active_orders_list.append(order_item)

                    buildings_data[bld] = {
                        "available_units": b_state.available_units,
                        "queue": bld_orders,
                        "total_in_queue": b_state.total_in_queue,
                    }
                    for u, c in b_state.total_in_queue.items():
                        total_in_queue_all[u] = total_in_queue_all.get(u, 0) + c
                    for u, c in b_state.available_units.items():
                        available_units_all[u] = c
                except Exception as e:
                    logger.debug(f"Edifício militar '{bld}' indisponível na aldeia {v_id}: {e}")
                    buildings_data[bld] = {"available_units": {}, "queue": [], "total_in_queue": {}}

            village_troops = {}
            if v_id and v_id in self.account.villages:
                village_troops = self.account.villages[v_id].troops
            elif self.account.current_village:
                village_troops = self.account.current_village.troops

            return {
                "status": "success",
                "village_id": v_id,
                "village_category": village_cat,
                "enabled": self.config.recruitment.enabled,
                "interval_minutes": self.config.recruitment.interval_minutes,
                "min_free_pop": self.config.recruitment.min_free_pop,
                "max_queue_elements": getattr(self.config.recruitment, "max_queue_elements", 3),
                "models": models,
                "targets": targets,
                "batch_sizes": batch_sizes,
                "troops_home": village_troops,
                "total_in_queue": total_in_queue_all,
                "available_units": available_units_all,
                "buildings": buildings_data,
                "active_orders": active_orders_list,
            }
        except Exception as e:
            logger.error(f"Erro ao obter estado de recrutamento: {e}")
            return {"status": "error", "message": str(e)}

    # --- Gestão de Modelos de Construção (Building Templates - SQLite) ---

    def list_building_templates(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista todos os modelos de construção registados no SQLite."""
        target_acc = account_id or self.active_profile_id
        return self.profile_manager.db.list_building_templates(account_id=target_acc)

    def get_building_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Obtém os detalhes de um modelo de construção específico."""
        return self.profile_manager.db.get_building_template(template_id)

    def save_building_template(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria ou atualiza um modelo de construção no SQLite e notifica a interface."""
        res = self.profile_manager.db.save_building_template(data)
        self.broadcast_sync("BUILDING_TEMPLATES_UPDATED", {
            "templates": self.list_building_templates(),
            "updated_id": res.get("id") if res else None,
        })
        return {
            "status": "success",
            "message": f"Modelo de construção '{res.get('name', '')}' gravado com sucesso no SQLite.",
            "template": res,
        }

    def delete_building_template(self, template_id: str) -> Dict[str, Any]:
        """Remove um modelo de construção do SQLite."""
        tmpl = self.get_building_template(template_id)
        if not tmpl:
            return {"status": "error", "message": f"Modelo de construção '{template_id}' não encontrado."}
        if tmpl.get("is_default"):
            return {"status": "error", "message": "Os modelos de construção padrão do sistema não podem ser eliminados."}

        success = self.profile_manager.db.delete_building_template(template_id)
        if success:
            self.broadcast_sync("BUILDING_TEMPLATES_UPDATED", {
                "templates": self.list_building_templates(),
                "deleted_id": template_id,
            })
            return {"status": "success", "message": f"Modelo '{tmpl.get('name')}' eliminado com sucesso."}
        return {"status": "error", "message": "Falha ao eliminar modelo de construção."}

    def clone_building_template(
        self,
        template_id: str,
        new_name: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Clona um modelo de construção no SQLite."""
        target_acc = account_id or self.active_profile_id
        res = self.profile_manager.db.clone_building_template(
            template_id=template_id,
            new_name=new_name,
            account_id=target_acc,
        )
        if not res:
            return {"status": "error", "message": f"Modelo original '{template_id}' não encontrado para clonagem."}

        self.broadcast_sync("BUILDING_TEMPLATES_UPDATED", {
            "templates": self.list_building_templates(),
            "cloned_id": res.get("id"),
        })
        return {
            "status": "success",
            "message": f"Modelo clonado com sucesso: '{res.get('name')}'.",
            "template": res,
        }

    # --- Gestão de Modelos de Recrutamento (Recruitment Models - SQLite) ---

    def list_recruitment_models(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista todos os modelos de tropas de recrutamento guardados no SQLite."""
        target_acc = account_id or self.active_profile_id
        return self.profile_manager.db.list_recruitment_models(account_id=target_acc)

    def get_recruitment_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Obtém os detalhes de um modelo de tropas de recrutamento específico."""
        return self.profile_manager.db.get_recruitment_model(model_id)

    def save_recruitment_model(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria ou atualiza um modelo de tropas de recrutamento no SQLite."""
        res = self.profile_manager.db.save_recruitment_model(data)
        
        # Sincroniza em memória e no BotConfig
        if res and res.get("id"):
            m_id = res["id"].lower().strip()
            if hasattr(self.config.recruitment, "models"):
                self.config.recruitment.models[m_id] = res.get("units", {})

        self.broadcast_sync("RECRUITMENT_MODELS_UPDATED", {
            "models": self.list_recruitment_models(),
            "updated_id": res.get("id") if res else None,
        })
        return {
            "status": "success",
            "message": f"Modelo de tropas '{res.get('name', '')}' gravado com sucesso no SQLite.",
            "model": res,
        }

    def delete_recruitment_model_db(self, model_id: str) -> Dict[str, Any]:
        """Remove um modelo de tropas de recrutamento do SQLite."""
        m = self.get_recruitment_model(model_id)
        if not m:
            return {"status": "error", "message": f"Modelo de recrutamento '{model_id}' não encontrado."}
        if m.get("is_default") or model_id in ("attack", "defense"):
            return {"status": "error", "message": "Os modelos de tropas padrão do sistema ('attack', 'defense') não podem ser eliminados."}

        success = self.profile_manager.db.delete_recruitment_model(model_id)
        if success:
            if hasattr(self.config.recruitment, "models") and model_id in self.config.recruitment.models:
                del self.config.recruitment.models[model_id]
            self.broadcast_sync("RECRUITMENT_MODELS_UPDATED", {
                "models": self.list_recruitment_models(),
                "deleted_id": model_id,
            })
            return {"status": "success", "message": f"Modelo '{m.get('name')}' eliminado com sucesso."}
        return {"status": "error", "message": "Falha ao eliminar modelo de tropas."}

    def clone_recruitment_model(
        self,
        model_id: str,
        new_name: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Clona um modelo de tropas de recrutamento no SQLite."""
        target_acc = account_id or self.active_profile_id
        res = self.profile_manager.db.clone_recruitment_model(
            model_id=model_id,
            new_name=new_name,
            account_id=target_acc,
        )
        if not res:
            return {"status": "error", "message": f"Modelo original '{model_id}' não encontrado para clonagem."}

        if res and res.get("id"):
            m_id = res["id"].lower().strip()
            if hasattr(self.config.recruitment, "models"):
                self.config.recruitment.models[m_id] = res.get("units", {})

        self.broadcast_sync("RECRUITMENT_MODELS_UPDATED", {
            "models": self.list_recruitment_models(),
            "cloned_id": res.get("id"),
        })
        return {
            "status": "success",
            "message": f"Modelo de tropas clonado com sucesso: '{res.get('name')}'.",
            "model": res,
        }

    # Aliases e compatibilidade
    def get_recruitment_models(self) -> Dict[str, Any]:
        """Retorna todos os modelos de tropas de recrutamento configurados."""
        models_list = self.list_recruitment_models()
        models_dict = {m["id"]: m["units"] for m in models_list if "id" in m and "units" in m}
        if hasattr(self.config.recruitment, "models") and self.config.recruitment.models:
            models_dict.update(self.config.recruitment.models)
        return {
            "status": "success",
            "models": models_dict,
            "models_list": models_list,
        }

    def save_recruitment_models(
        self,
        attack: Optional[Dict[str, int]] = None,
        defense: Optional[Dict[str, int]] = None,
        models: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> Dict[str, Any]:
        """Salva modelos de tropas garantindo persistência no SQLite e retrocompatibilidade."""
        from engine.config.settings import DEFAULT_ATTACK_MODEL, DEFAULT_DEFENSE_MODEL
        if models is not None and isinstance(models, dict):
            for m_name, m_units in models.items():
                if isinstance(m_units, dict):
                    self.save_recruitment_model({
                        "id": str(m_name).lower().strip(),
                        "name": str(m_name).title(),
                        "units": {str(k): max(0, int(v)) for k, v in m_units.items()},
                        "is_default": str(m_name).lower().strip() in ("attack", "defense"),
                    })
        else:
            if attack is not None:
                self.save_recruitment_model({
                    "id": "attack",
                    "name": "Ataque Full",
                    "units": {str(k): max(0, int(v)) for k, v in attack.items()},
                    "is_default": True,
                })
            if defense is not None:
                self.save_recruitment_model({
                    "id": "defense",
                    "name": "Defesa Full",
                    "units": {str(k): max(0, int(v)) for k, v in defense.items()},
                    "is_default": True,
                })

        current_models = {m["id"]: m["units"] for m in self.list_recruitment_models()}
        self.config.recruitment.models = current_models
        self.update_config_and_save({"recruitment": {"models": current_models}})
        self.broadcast_sync("RECRUITMENT_MODELS_UPDATED", {"models": current_models})
        return {
            "status": "success",
            "message": "Modelos de tropas guardados e persistidos no SQLite com sucesso!",
            "models": current_models,
        }

    def delete_recruitment_model(self, model_name: str) -> Dict[str, Any]:
        """Remove um modelo de tropas customizado do SQLite e da configuração."""
        return self.delete_recruitment_model_db(model_name.lower().strip())



    def toggle_quest_module(
        self,
        enabled: Optional[bool] = None,
        auto_claim_quests: Optional[bool] = None,
        auto_daily_bonus: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Ativa/desativa ou ajusta a rotina de missões e bónus diário."""
        update_data = {}
        if enabled is not None:
            update_data["enabled"] = bool(enabled)
            self.config.quest.enabled = bool(enabled)
        if auto_claim_quests is not None:
            update_data["auto_claim_quests"] = bool(auto_claim_quests)
            self.config.quest.auto_claim_quests = bool(auto_claim_quests)
        if auto_daily_bonus is not None:
            update_data["auto_daily_bonus"] = bool(auto_daily_bonus)
            self.config.quest.auto_daily_bonus = bool(auto_daily_bonus)

        self.update_config_and_save({"quest": update_data})
        if self.config.quest.enabled and self.account and self.scheduler:
            self.quest_manager.schedule_auto_quest(
                scheduler=self.scheduler,
                account=self.account,
                quest_config=self.config.quest,
            )
        self.broadcast_sync("MODULE_TOGGLED", {"module": "quest", "enabled": self.config.quest.enabled})
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {
            "status": "success",
            "message": f"Missões & Bónus Diário {'ATIVADO' if self.config.quest.enabled else 'DESATIVADO'}.",
            "enabled": self.config.quest.enabled,
        }

    async def get_arbitrage_state(self, village_id: Optional[int] = None) -> Dict[str, Any]:
        """Consulta o estado da arbitragem económica, diagnóstico das 4 filas e projeção de fluxo de caixa."""
        if not self.account:
            return {"status": "error", "message": "Conta não conectada"}
        try:
            v_id = village_id or self.account.current_village_id
            decision = await self.arbitrage_manager.evaluate_village_arbitrage(
                account=self.account,
                village_id=v_id,
                emergency_queue_seconds=self.config.arbitrage.emergency_queue_seconds,
                min_military_batch=self.config.arbitrage.min_military_batch,
            )
            return {
                "status": "success",
                "enabled": self.config.arbitrage.enabled,
                "decision": decision.to_dict(),
            }
        except Exception as e:
            logger.error(f"Erro ao avaliar arbitragem económica: {e}")
            return {"status": "error", "message": str(e)}

    async def trigger_arbitrage_cycle(self, village_id: Optional[int] = None) -> Dict[str, Any]:
        """Dispara manualmente um ciclo de arbitragem económica para a aldeia."""
        if not self.account:
            return {"status": "error", "message": "Conta não conectada"}
        try:
            v_id = village_id or self.account.current_village_id
            decision = await self.arbitrage_manager.execute_arbitrage_cycle(
                account=self.account,
                village_id=v_id,
                emergency_queue_seconds=self.config.arbitrage.emergency_queue_seconds,
                min_military_batch=self.config.arbitrage.min_military_batch,
            )
            self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
            return {
                "status": "success",
                "message": f"Ciclo de Arbitragem executado: [{decision.action_type.value.upper()}] - {decision.reason}",
                "decision": decision.to_dict(),
            }
        except Exception as e:
            logger.error(f"Erro ao executar ciclo de arbitragem: {e}")
            return {"status": "error", "message": str(e)}

    def toggle_arbitrage_module(
        self,
        enabled: Optional[bool] = None,
        interval_seconds: Optional[float] = None,
        emergency_queue_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Ativa/desativa a rotina contínua de arbitragem económica 'Fila Sempre Ativa'."""
        update_data = {}
        if enabled is not None:
            update_data["enabled"] = bool(enabled)
            self.config.arbitrage.enabled = bool(enabled)
        if interval_seconds is not None:
            update_data["interval_seconds"] = float(interval_seconds)
            self.config.arbitrage.interval_seconds = float(interval_seconds)
        if emergency_queue_seconds is not None:
            update_data["emergency_queue_seconds"] = float(emergency_queue_seconds)
            self.config.arbitrage.emergency_queue_seconds = float(emergency_queue_seconds)

        self.update_config_and_save({"arbitrage": update_data})
        if self.config.arbitrage.enabled and self.account and self.scheduler:
            self.arbitrage_manager.schedule_auto_arbitrage(
                scheduler=self.scheduler,
                account=self.account,
                interval_seconds=self.config.arbitrage.interval_seconds,
                emergency_queue_seconds=self.config.arbitrage.emergency_queue_seconds,
                min_military_batch=self.config.arbitrage.min_military_batch,
            )
        self.broadcast_sync("MODULE_TOGGLED", {"module": "arbitrage", "enabled": self.config.arbitrage.enabled})
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {
            "status": "success",
            "message": f"Arbitragem Económica {'ATIVADA' if self.config.arbitrage.enabled else 'DESATIVADA'}.",
            "enabled": self.config.arbitrage.enabled,
        }

    async def get_radar_farm_plan(
        self,
        radius: Optional[float] = None,
        squad_troops: Optional[Dict[str, int]] = None,
        village_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Calcula o plano de Radar Farm e alocação de micro-esquadrões."""
        if not self.account:
            return {"status": "error", "message": "Conta não conectada"}
        try:
            r = radius if radius is not None else self.config.farm.map_scan_radius
            troops = UnitsCount.from_dict(squad_troops) if squad_troops else UnitsCount.from_dict(self.config.farm.custom_troops)
            plan = await self.farm_manager.get_radar_farm_plan(
                account=self.account,
                radius=r,
                squad_template=troops,
                skip_active_targets=self.config.farm.skip_active_targets,
                village_id=village_id,
            )
            return {
                "status": "success",
                "village_id": plan.village_id,
                "total_barbarians_found": plan.total_barbarians_found,
                "eligible_targets_count": len(plan.eligible_targets),
                "squads_assigned_count": len(plan.squads_assigned),
                "total_carrying_capacity": plan.total_carrying_capacity,
                "squads": [
                    {"target": f"({coords[0]}|{coords[1]})", "units": sq.to_dict()}
                    for coords, sq in plan.squads_assigned
                ],
            }
        except Exception as e:
            logger.error(f"Erro ao calcular plano de Radar Farm: {e}")
            return {"status": "error", "message": str(e)}

    async def trigger_radar_farm_cycle(
        self,
        radius: Optional[float] = None,
        squad_troops: Optional[Dict[str, int]] = None,
        village_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Dispara uma onda imediata de Radar Farming com alocação dinâmica de tropas."""
        if not self.account:
            return {"status": "error", "message": "Conta não conectada"}
        try:
            r = radius if radius is not None else self.config.farm.map_scan_radius
            troops = UnitsCount.from_dict(squad_troops) if squad_troops else UnitsCount.from_dict(self.config.farm.custom_troops)
            res = await self.farm_manager.run_radar_farm_cycle(
                account=self.account,
                radius=r,
                squad_template=troops,
                skip_active_targets=self.config.farm.skip_active_targets,
                village_id=village_id,
            )
            self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
            return {
                "status": "success",
                "message": f"Onda de Radar Farming concluída: {res['sent_attacks']} ataques despachados.",
                "data": res,
            }
        except Exception as e:
            logger.error(f"Erro ao executar Radar Farm: {e}")
            return {"status": "error", "message": str(e)}

    def get_network_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retorna histórico de requisições de rede da conta ativa."""
        if self.account:
            return self.account.get_recent_requests(limit=limit)
        return []

    # --- Gestão de Contas & Multi-Conta Monousuário (Single-Active Session) ---

    def list_accounts(self) -> List[Dict[str, Any]]:
        """Lista todas as contas guardadas a partir da base de dados SQLite."""
        return self.profile_manager.list_profiles()

    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Obtém detalhes de uma conta específica."""
        prof = self.profile_manager.get_profile(account_id)
        return prof.to_dict(include_plain_password=False) if prof else None

    def create_account(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria um novo perfil de conta isolado na base de dados SQLite."""
        prof = AccountProfile.from_dict(data)
        prof.is_active = False  # Criada inicialmente offline
        self.profile_manager.save_profile(prof)
        self.broadcast_sync("ACCOUNTS_UPDATED", {"accounts": self.list_accounts()})
        return {
            "status": "success",
            "message": f"Conta '{prof.name}' criada com sucesso.",
            "account": prof.to_dict(include_plain_password=False),
        }

    def update_account(self, account_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Atualiza as configurações de uma conta na base de dados SQLite."""
        prof = self.profile_manager.get_profile(account_id)
        if not prof:
            return {"status": "error", "message": f"Conta '{account_id}' não encontrada."}
        
        data["id"] = account_id
        updated = AccountProfile.from_dict(data)
        self.profile_manager.save_profile(updated)
        self.broadcast_sync("ACCOUNTS_UPDATED", {"accounts": self.list_accounts()})
        return {
            "status": "success",
            "message": f"Conta '{updated.name}' atualizada com sucesso.",
            "account": updated.to_dict(include_plain_password=False),
        }

    def delete_account(self, account_id: str) -> Dict[str, Any]:
        """Remove um perfil de conta da base de dados SQLite."""
        if self.active_profile_id == account_id:
            if self.scheduler:
                self.scheduler.clear()
            if self.account:
                try:
                    asyncio.create_task(self.account.close())
                except Exception as e:
                    logger.debug(f"Aviso ao encerrar conta eliminada: {e}")
                self.account = None
            self.active_profile_id = None
        
        self.profile_manager.delete_profile(account_id)
        self.broadcast_sync("ACCOUNTS_UPDATED", {"accounts": self.list_accounts()})
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {
            "status": "success",
            "message": f"Conta '{account_id}' eliminada com sucesso.",
        }

    async def activate_account(self, account_id: str) -> Dict[str, Any]:
        """
        Ativa uma conta específica com bloqueio monousuário estrito (Single-Active Session).
        Encerra qualquer sessão anterior de forma limpa antes de instanciar a nova.
        Suporta contas armazenadas no Cloud SQL ou em memória.
        """
        async with self._account_lock:
            prof = self.profile_manager.get_profile(account_id)
            if not prof:
                # Tenta carregar do Cloud SQL
                await self.ensure_current_app_user()
                if self.current_app_user:
                    try:
                        cloud_acc = await self.game_account_repo.get_by_id(account_id)
                        if not cloud_acc:
                            cloud_acc = await self.game_account_repo.get_by_user_and_username(self.current_app_user.id, account_id)
                        if cloud_acc:
                            creds = self.game_account_repo.decrypt_credentials(cloud_acc)
                            worlds = await self.game_world_repo.list_by_account(cloud_acc.id)
                            w_code = worlds[0].world_code if worlds else creds.get("world", "pt117")
                            from engine.core.profile_manager import AccountProfile
                            prof = AccountProfile(
                                id=cloud_acc.id,
                                name=cloud_acc.game_username,
                                world=w_code,
                                domain=creds.get("domain", "tribalwars.com.pt"),
                                world_domain=f"{w_code}.{creds.get('domain', 'tribalwars.com.pt')}",
                                session_cookie=creds.get("sid", ""),
                                is_active=True,
                            )
                            self.profile_manager.save_profile(prof)
                    except Exception as ce:
                        logger.warning(f"Erro ao carregar conta do Cloud SQL para ativação: {ce}")

            if not prof:
                return {"status": "error", "message": f"Conta com ID '{account_id}' não encontrada."}

            logger.info(f"🔄 A ativar perfil monousuário: '{prof.name}' ({prof.world})")

            # 1. Encerra a conta anterior se estiver a correr
            if self.account:
                try:
                    if self.scheduler:
                        self.scheduler.clear()
                    await self.account.close()
                except Exception as e:
                    logger.warning(f"Aviso ao encerrar conta anterior: {e}")
                self.account = None

            # 2. Marca na base de dados SQLite a conta ativa (e desativa todas as outras)
            self.profile_manager.set_active_profile(account_id)
            self.active_profile_id = account_id

            # 3. Atualiza BotConfig com as definições completas e agregadas do perfil no SQLite
            self.config = prof.to_bot_config()

            # 4. Instancia e inicializa o cliente de rede da nova conta
            account = TribalAccount(
                world=prof.world,
                sid=self.config.sid,
                domain=prof.domain,
                proxy=prof.proxy,
            )
            account.stats_tracker = self.get_stats_tracker(prof.world)
            self.account = account

            if self.config.sid:
                try:
                    await account.init_session()
                    await account.refresh_state()
                    await account.fetch_all_villages_overview()
                    await account.discover_active_worlds()
                    await self.sync_account_villages_to_cloud(
                        game_username=prof.name,
                        world_code=prof.world,
                    )
                except Exception as e:
                    logger.warning(f"Aviso na inicialização da conta ativada '{prof.name}': {e}")

            # 5. Configura e agenda as rotinas no Scheduler
            if self.scheduler and self.config.sid:
                self.scheduler.clear()
                # Main building
                if self.config.building.enabled:
                    mb_mgr = MainBuildingManager(default_max_queue=self.config.building.max_queue)
                    mb_mgr.schedule_auto_build(
                        scheduler=self.scheduler,
                        account=self.account,
                        plan=self.config.get_active_build_plan(),
                        max_queue=self.config.building.max_queue,
                        interval_seconds=self.config.building.interval_seconds,
                        enabled_check=lambda: self.config.building.enabled,
                        bot_config=self.config,
                    )
                # Recruitment
                if self.config.recruitment.enabled:
                    self.recruitment_manager.schedule_auto_recruit(
                        scheduler=self.scheduler,
                        account=self.account,
                        recruit_config=self.config.recruitment,
                        bot_config=self.config,
                    )
                # Auto-Farm
                if self.config.farm.enabled:
                    self.farm_manager.schedule_auto_farm(
                        scheduler=self.scheduler,
                        account=self.account,
                        farm_config=self.config.farm,
                        bot_config=self.config,
                    )
                # Defense & Incomings Monitor (Item 2.8)
                if getattr(self.config, "defense", None) and self.config.defense.enabled:
                    self.defense_manager.schedule_defense_monitor(
                        scheduler=self.scheduler,
                        account=self.account,
                        config=self.config.defense,
                    )
                if not self.scheduler.is_running:
                    self.scheduler.start()

            # 6. Sincroniza instâncias no MultiWorldManager
            self.world_manager.instances[prof.world] = WorldInstance(
                world=prof.world,
                account=self.account,
                scheduler=self.scheduler,
                config=self.config,
                coordinator=self.village_coordinator,
                is_active=True,
            )
            self.world_manager.active_world = prof.world

            # 7. Transmite broadcast de estado
            status_dict = self.get_status_dict()
            self.broadcast_sync("ACCOUNT_ACTIVATED", {"account_id": account_id, "account": prof.to_dict()})
            self.broadcast_sync("STATUS_UPDATE", status_dict)

            return {
                "status": "success",
                "message": f"Conta '{prof.name}' ({prof.world}) ativada com sucesso.",
                "account": prof.to_dict(include_plain_password=False),
            }

    async def disconnect_account(self) -> Dict[str, Any]:
        """Desconecta a conta ativa, pausa agendadores e liberta recursos (Modo Offline)."""
        async with self._account_lock:
            if self.scheduler:
                self.scheduler.clear()
            if self.account:
                try:
                    await self.account.close()
                except Exception as e:
                    logger.debug(f"Aviso ao fechar sessão de rede: {e}")
                self.account = None

            self.profile_manager.deactivate_all()
            self.active_profile_id = None
            self.config.sid = ""

            status_dict = self.get_status_dict()
            self.broadcast_sync("ACCOUNT_DISCONNECTED", {})
            self.broadcast_sync("STATUS_UPDATE", status_dict)

            logger.info("Conta desconectada. Motor em modo Standby / Offline.")
            return {"status": "success", "message": "Conta desconectada com sucesso."}

    # --- Métodos de Controlo do Assistente de Saque & Farm (/api/farm/*) ---

    def get_farm_status(self, world: Optional[str] = None) -> Dict[str, Any]:
        """Retorna o estado detalhado do módulo de farm e tropas disponíveis."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        cfg = inst.config if inst else self.config
        sch = inst.scheduler if inst else self.scheduler

        v_id = acc.current_village_id if acc else 0
        curr_v = acc.villages.get(v_id) if acc and v_id else None
        coords = f"{curr_v.x}|{curr_v.y}" if curr_v else "0|0"
        troops_raw = getattr(curr_v, "troops", None) if curr_v else None
        troops = troops_raw.to_dict() if hasattr(troops_raw, "to_dict") else (troops_raw or {})

        return {
            "status": "success",
            "world": acc.world if acc else cfg.world,
            "village_id": v_id,
            "village_coords": coords,
            "enabled": bool(getattr(cfg.farm, "enabled", True)),
            "default_template": getattr(cfg.farm, "default_template", "A"),
            "max_distance": getattr(cfg.farm, "max_distance", 25.0),
            "scan_all_radius_barbarians": getattr(cfg.farm, "scan_all_radius_barbarians", True),
            "bootstrap_unlisted_barbarians": getattr(cfg.farm, "bootstrap_unlisted_barbarians", True),
            "min_interval_seconds": getattr(cfg.farm, "min_interval_seconds", 45.0),
            "max_interval_seconds": getattr(cfg.farm, "max_interval_seconds", 90.0),
            "avoid_concurrent_attacks": getattr(cfg.farm, "avoid_concurrent_attacks", True),
            "stop_on_losses": getattr(cfg.farm, "stop_on_losses", True),
            "custom_targets": getattr(cfg.farm, "custom_targets", []),
            "available_troops": troops,
            "is_scheduler_running": sch.is_running and not sch.is_paused if sch else False,
        }

    def toggle_farm_module(
        self,
        enabled: Optional[bool] = None,
        world: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Liga ou desliga o envio contínuo de saques."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        cfg = inst.config if inst else self.config
        sch = inst.scheduler if inst else self.scheduler

        if enabled is not None:
            cfg.farm.enabled = bool(enabled)
            self.update_config_and_save({"farm": {"enabled": bool(enabled)}})

        if cfg.farm.enabled and acc and sch:
            self.farm_manager.schedule_auto_farm(
                scheduler=sch,
                account=acc,
                farm_config=cfg.farm,
                bot_config=cfg,
            )

        self.broadcast_sync("MODULE_TOGGLED", {"module": "farm", "enabled": cfg.farm.enabled, "world": cfg.world})
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {
            "status": "success",
            "message": f"Módulo de farm {'ativado' if cfg.farm.enabled else 'desativado'}.",
            "enabled": cfg.farm.enabled,
        }

    async def trigger_farm_cycle(
        self,
        force: bool = True,
        village_id: Optional[int] = None,
        world: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispara uma ronda imediata e assíncrona de saques."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        cfg = inst.config if inst else self.config
        if not acc:
            return {"status": "error", "message": "Conta não inicializada."}

        target_v_id = village_id or acc.current_village_id
        if target_v_id and target_v_id != acc.current_village_id:
            await acc.switch_village(target_v_id)

        res = await self.farm_manager.run_comprehensive_radius_farm_cycle(
            account=acc,
            config=cfg.farm,
            village_id=target_v_id,
        )
        total_attacks = res.get("am_farm_attacks_sent", 0) + res.get("bootstrap_attacks_sent", 0)
        self.broadcast_sync("FARM_CYCLE_DONE", res)
        tracker = self.get_stats_tracker(acc.world)
        self.broadcast_sync("STATS_UPDATED", tracker.get_summary())
        return {
            "status": "success",
            "message": f"Ciclo de farm concluído: {total_attacks} ataques enviados ({res.get('am_farm_attacks_sent', 0)} AM Farm, {res.get('bootstrap_attacks_sent', 0)} Praça).",
            "results": res,
        }

    def update_farm_configuration(
        self,
        payload: Dict[str, Any],
        world: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Atualiza e persiste os parâmetros operacionais do Assistente de Saque."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        cfg = inst.config if inst else self.config
        sch = inst.scheduler if inst else self.scheduler

        farm_dict = cfg.farm.to_dict() if hasattr(cfg.farm, "to_dict") else {}
        for k, v in payload.items():
            if hasattr(cfg.farm, k) and v is not None:
                setattr(cfg.farm, k, v)
                farm_dict[k] = v

        self.update_config_and_save({"farm": farm_dict})
        if cfg.farm.enabled and acc and sch:
            self.farm_manager.schedule_auto_farm(
                scheduler=sch,
                account=acc,
                farm_config=cfg.farm,
                bot_config=cfg,
            )
        self.broadcast_sync("FARM_CONFIG_UPDATED", {"farm": farm_dict})
        return {
            "status": "success",
            "message": "Configurações de Farm atualizadas com sucesso.",
            "farm": farm_dict,
        }

    async def update_farm_template(
        self,
        template: str,
        units: Dict[str, int],
        village_id: Optional[int] = None,
        world: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Atualiza a configuração de tropas do Modelo A ou B no jogo e persiste na base local."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        cfg = inst.config if inst else self.config
        if not acc:
            return {"status": "error", "message": "Conta não inicializada."}

        target_v_id = village_id or acc.current_village_id
        tmpl_key = template.lower().strip()

        # 1. Atualiza e persiste na configuração do bot
        clean_units = {u: max(0, int(qty)) for u, qty in units.items()}
        if tmpl_key == "a":
            cfg.farm.template_a_troops = clean_units.copy()
        elif tmpl_key == "b":
            cfg.farm.template_b_troops = clean_units.copy()

        self.update_config_and_save({
            "farm": {
                f"template_{tmpl_key}_troops": clean_units
            }
        })

        # 2. Grava nos servidores do jogo (screen=am_farm&action=edit_all)
        res = await self.farm_manager.save_am_farm_template(
            account=acc,
            template=template,
            units=clean_units,
            village_id=target_v_id,
        )
        self.broadcast_sync("FARM_TEMPLATES_UPDATED", res)
        return res

    async def get_farm_targets(
        self,
        radius: Optional[float] = None,
        limit: int = 100,
        village_id: Optional[int] = None,
        world: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Lista as aldeias bárbaras mapeadas no Assistente de Saque e no raio."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        cfg = inst.config if inst else self.config
        if not acc:
            return {"status": "error", "message": "Conta não inicializada.", "targets": []}

        target_v_id = village_id or acc.current_village_id
        if target_v_id and target_v_id != acc.current_village_id:
            await acc.switch_village(target_v_id)

        try:
            # 1. Carrega o estado do AM Farm (modelos A/B)
            am_state = await self.farm_manager.get_am_farm_state(acc, village_id=target_v_id)
            max_dist = radius or cfg.farm.max_distance

            # 2. Descobre TODAS as bárbaras no raio configurado (AM Farm + Mapa + Cache local)
            all_barbarians = await self.farm_manager.discover_all_radius_barbarians(
                account=acc,
                max_distance=max_dist,
                village_id=target_v_id,
                custom_targets=cfg.farm.custom_targets,
            )

            targets_data = []
            for t in all_barbarians:
                travel_sec = int(round(t.distance * 600))
                is_in_am = getattr(t, "is_in_am_farm", True)
                in_transit = t.has_attack_in_transit or (t.target_coords in self.farm_manager._recent_farm_targets)
                targets_data.append({
                    "village_id": t.target_id,
                    "name": t.target_name,
                    "coordinates": t.target_coords,
                    "distance": t.distance,
                    "last_report_color": t.report_color,
                    "loot_status": t.loot_status,
                    "wall_level": t.wall_level,
                    "has_attack_in_transit": in_transit,
                    "is_in_am_farm": is_in_am,
                    "travel_time_cl_str": f"{travel_sec // 60}m {travel_sec % 60}s",
                    "can_attack_a": bool(t.template_a_available or t.action_url_a or not is_in_am),
                    "can_attack_b": bool(t.template_b_available or t.action_url_b),
                })
                if len(targets_data) >= limit:
                    break

            return {
                "status": "success",
                "count": len(targets_data),
                "template_a": am_state.template_a_troops,
                "template_b": am_state.template_b_troops,
                "targets": targets_data,
            }
        except Exception as e:
            logger.error(f"Erro ao obter alvos de farm: {e}")
            return {"status": "error", "message": str(e), "targets": []}

    # --- Métodos de Controlo do Radar de Inativos (/api/radar/*) ---

    def get_radar_inactives(
        self,
        world: Optional[str] = None,
        max_distance: float = 25.0,
        days_window: float = 7.0,
        max_points_growth: int = 30,
        min_points: int = 200,
        max_points: int = 6000,
        only_tribeless: bool = False,
        include_single_member_tribes: bool = True,
        include_barbarians: bool = False,
        search_query: Optional[str] = None,
        limit: int = 150,
    ) -> Dict[str, Any]:
        """Executa a varredura geoespacial de alvos inativos."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        target_world = world or (acc.world if acc else self.config.world)

        curr_v = acc.current_village if acc else None
        o_x = curr_v.x if curr_v else 500
        o_y = curr_v.y if curr_v else 500

        cfg = InactivityFilterConfig(
            max_distance=max_distance,
            days_window=days_window,
            max_points_growth=max_points_growth,
            min_points=min_points,
            max_points=max_points,
            only_tribeless=only_tribeless,
            include_single_member_tribes=include_single_member_tribes,
            include_barbarians=include_barbarians,
            limit=limit,
        )

        report = self.inactivity_tracker.scan_inactives(
            world=target_world,
            origin_x=o_x,
            origin_y=o_y,
            filter_config=cfg,
        )

        farm_customs = set(getattr(self.config.farm, "custom_targets", []))
        targets_list = []
        q = (search_query or "").lower().strip()

        for t in report.targets:
            if q:
                match_name = q in t.village_name.lower() or q in t.player_name.lower() or q in t.coords
                if not match_name:
                    continue

            coords_tuple = (t.x, t.y)
            is_in_farm = coords_tuple in farm_customs or t.coords in farm_customs

            targets_list.append({
                "village_id": t.village_id,
                "village_name": t.village_name,
                "coordinates": t.coords,
                "x": t.x,
                "y": t.y,
                "player_id": t.player_id,
                "player_name": t.player_name,
                "tribe_id": t.ally_id,
                "tribe_name": t.ally_name,
                "tribe_tag": t.ally_tag,
                "tribe_members_count": t.ally_members_count,
                "current_points": t.player_points,
                "previous_points": t.past_player_points,
                "village_points": t.village_points,
                "delta_points": t.delta_points,
                "days_diff": t.days_diff,
                "inactivity_category": t.inactivity_category,
                "inactivity_label": t.inactivity_label,
                "distance": t.distance,
                "light_travel_time_str": t.travel_time_lc_str,
                "spy_travel_time_str": t.travel_time_spy_str,
                "eta_lc_str": t.eta_lc_str,
                "eta_spy_str": t.eta_spy_str,
                "is_in_farm_list": is_in_farm,
            })

        return {
            "status": "success",
            "world": target_world,
            "origin_coords": f"{o_x}|{o_y}",
            "scan_radius": max_distance,
            "days_window": days_window,
            "total_targets_found": len(targets_list),
            "stagnant_count": report.stagnant_count,
            "regressive_count": report.regressive_count,
            "residual_count": report.residual_count,
            "targets": targets_list,
        }

    async def sync_world_data(
        self,
        world: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Dispara a sincronização de dados públicos do mundo."""
        inst = self.world_manager.get_instance(world)
        target_world = world or (inst.world if inst else self.config.world)
        domain = inst.config.domain if inst else self.config.domain

        self.broadcast_sync("WORLD_SYNC_STARTED", {"world": target_world})
        result = await self.world_data_worker.sync_world_data(
            world=target_world,
            domain=domain,
            force=force,
        )

        status_dict = self.get_world_sync_status(world=target_world)
        self.broadcast_sync("WORLD_SYNC_FINISHED", {
            "world": target_world,
            "is_updated": result.is_updated,
            "villages_count": result.villages_count,
            "players_count": result.players_count,
            "sync_status": status_dict,
        })

        return {
            "status": "success",
            "is_updated": result.is_updated,
            "world": target_world,
            "villages_count": result.villages_count,
            "players_count": result.players_count,
            "allies_count": result.allies_count,
            "error": result.error,
        }

    def get_world_sync_status(self, world: Optional[str] = None) -> Dict[str, Any]:
        """Retorna o status de sincronização e idade da base local."""
        inst = self.world_manager.get_instance(world)
        target_world = world or (inst.world if inst else self.config.world)

        latest = self.world_database.get_latest_snapshot(target_world)
        if not latest:
            return {
                "status": "success",
                "world": target_world,
                "has_snapshot": False,
                "is_syncing": False,
                "last_sync_timestamp": None,
                "last_sync_human_str": "Nunca sincronizado",
                "total_villages": 0,
                "total_players": 0,
                "total_allies": 0,
                "history_days": 0,
            }

        last_ts = latest["timestamp"]
        diff_min = int((time.time() - last_ts) / 60)
        human_str = f"Há {diff_min} minutos" if diff_min < 60 else f"Há {diff_min // 60} horas"

        all_snaps = self.world_database.get_all_snapshots(target_world)
        history_days = 0.0
        if len(all_snaps) > 1:
            oldest_ts = all_snaps[-1]["timestamp"]
            history_days = round((last_ts - oldest_ts) / 86400.0, 1)

        return {
            "status": "success",
            "world": target_world,
            "has_snapshot": True,
            "is_syncing": False,
            "last_sync_timestamp": last_ts,
            "last_sync_human_str": human_str,
            "total_villages": latest["villages_count"],
            "total_players": latest["players_count"],
            "total_allies": latest["allies_count"],
            "history_days": history_days,
            "total_snapshots": len(all_snaps),
        }

    def add_custom_farm_target(
        self,
        coords: Any = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
        world: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Adiciona uma coordenada à lista de alvos customizados de farm."""
        inst = self.world_manager.get_instance(world)
        cfg = inst.config if inst else self.config

        if coords is not None and y is not None:
            cleaned = f"{coords}|{y}".strip()
        elif x is not None and y is not None:
            cleaned = f"{x}|{y}".strip()
        elif isinstance(coords, (tuple, list)) and len(coords) == 2:
            cleaned = f"{coords[0]}|{coords[1]}".strip()
        else:
            cleaned = str(coords or "").strip()

        customs = list(getattr(cfg.farm, "custom_targets", []))
        if cleaned and cleaned not in customs:
            customs.append(cleaned)
            cfg.farm.custom_targets = customs
            self.update_config_and_save({"farm": {"custom_targets": customs}})

        self.broadcast_sync("FARM_TARGET_ADDED", {"coords": cleaned, "custom_targets": customs})
        return {
            "status": "success",
            "message": f"Coordenada '{cleaned}' adicionada à lista de farm.",
            "custom_targets": customs,
        }

    def get_radar_players_radius(
        self,
        world: Optional[str] = None,
        max_distance: float = 25.0,
        search_query: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Retorna o relatório de evolução de todos os jogadores num raio de X campos."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        target_world = world or (acc.world if acc else self.config.world)

        curr_v = acc.current_village if acc else None
        o_x = curr_v.x if curr_v else 500
        o_y = curr_v.y if curr_v else 500

        report = self.inactivity_tracker.get_players_evolution_report(
            world=target_world,
            origin_x=o_x,
            origin_y=o_y,
            max_distance=max_distance,
            limit=limit,
        )

        players_list = report.get("players", [])
        q = (search_query or "").lower().strip()
        if q:
            players_list = [
                p for p in players_list
                if q in p.get("player_name", "").lower()
                or q in p.get("ally_name", "").lower()
                or q in p.get("ally_tag", "").lower()
                or q in p.get("nearest_coords", "")
            ]

        return {
            "status": "success",
            "world": target_world,
            "origin_coords": f"{o_x}|{o_y}",
            "scan_radius": max_distance,
            "total_players_found": len(players_list),
            "counts": report.get("counts", {}),
            "players": players_list,
        }

    def get_player_timeline(
        self,
        player_id: int,
        world: Optional[str] = None,
        limit: int = 30,
    ) -> Dict[str, Any]:
        """Retorna a linha do tempo cronológica de medições de um jogador específico."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        target_world = world or (acc.world if acc else self.config.world)

        timeline = self.inactivity_tracker.get_player_timeline(
            world=target_world,
            player_id=player_id,
            limit=limit,
        )
        return {
            "status": "success",
            "world": target_world,
            "player_id": player_id,
            "timeline": timeline,
        }

    def _setup_defense_callbacks(self) -> None:
        """Configura propagação de eventos do DefenseManager para os clientes WebSocket."""
        async def _on_alert(incomings: List[IncomingAttack]):
            self.broadcast_sync("INCOMING_ATTACK_ALERT", {
                "count": len(incomings),
                "incomings": [inc.to_dict() for inc in incomings],
                "world": self.config.world,
            })
            self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())

        async def _on_cleared():
            self.broadcast_sync("INCOMING_ATTACKS_CLEARED", {
                "count": 0,
                "world": self.config.world,
            })
            self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())

        async def _on_dodge_exec(op: DodgeOperation):
            self.broadcast_sync("DODGE_EXECUTED", {
                "dodge": op.to_dict(),
                "world": self.config.world,
            })
            self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())

        async def _on_dodge_cancel(op: DodgeOperation):
            self.broadcast_sync("DODGE_CANCELLED", {
                "dodge": op.to_dict(),
                "world": self.config.world,
            })
            self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())

        self.defense_manager.on_incoming_alert(_on_alert)
        self.defense_manager.on_incomings_cleared(_on_cleared)
        self.defense_manager.on_dodge_executed(_on_dodge_exec)
        self.defense_manager.on_dodge_cancelled(_on_dodge_cancel)

    def get_defense_status(self, world: Optional[str] = None) -> Dict[str, Any]:
        """Retorna o estado detalhado de defesa, incomings e dodges."""
        inst = self.world_manager.get_instance(world)
        cfg = inst.config if inst else self.config
        return {
            "status": "success",
            "world": cfg.world,
            "enabled": getattr(cfg.defense, "enabled", True),
            "auto_dodge_enabled": getattr(cfg.defense, "auto_dodge_enabled", False),
            "dodge_lead_time_seconds": getattr(cfg.defense, "dodge_lead_time_seconds", 30),
            "dodge_cancel_delay_seconds": getattr(cfg.defense, "dodge_cancel_delay_seconds", 5),
            "escape_coords": getattr(cfg.defense, "escape_coords", None),
            "auto_dodge_all_units": getattr(cfg.defense, "auto_dodge_all_units", True),
            "alarm_sound_enabled": getattr(cfg.defense, "alarm_sound_enabled", True),
            "check_interval_seconds": getattr(cfg.defense, "check_interval_seconds", 20.0),
            "incomings_count": self.defense_manager.last_incomings_count,
            "active_incomings": [inc.to_dict() for inc in self.defense_manager.active_incomings.values()],
            "active_dodges": [d.to_dict() for d in self.defense_manager.active_dodges.values()],
        }

    async def check_defense_incomings(self, world: Optional[str] = None) -> Dict[str, Any]:
        """Dispara uma verificação imediata de ataques recebidos."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        if not acc:
            return {"status": "error", "message": "Conta não conectada."}

        incomings = await self.defense_manager.check_incomings(acc)
        status_dict = self.get_defense_status(world)
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {
            "status": "success",
            "count": len(incomings),
            "incomings": [inc.to_dict() for inc in incomings],
            "defense_state": status_dict,
        }

    def toggle_defense_module(
        self,
        enabled: Optional[bool] = None,
        auto_dodge_enabled: Optional[bool] = None,
        dodge_lead_time_seconds: Optional[int] = None,
        dodge_cancel_delay_seconds: Optional[int] = None,
        escape_coords: Optional[str] = None,
        auto_dodge_all_units: Optional[bool] = None,
        alarm_sound_enabled: Optional[bool] = None,
        check_interval_seconds: Optional[float] = None,
        world: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Configura ou ativa/desativa os componentes do módulo de Defesa e Auto-Dodge."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        cfg = inst.config if inst else self.config
        sch = inst.scheduler if inst else self.scheduler

        def_patch: Dict[str, Any] = {}
        if enabled is not None:
            cfg.defense.enabled = bool(enabled)
            def_patch["enabled"] = bool(enabled)
        if auto_dodge_enabled is not None:
            cfg.defense.auto_dodge_enabled = bool(auto_dodge_enabled)
            def_patch["auto_dodge_enabled"] = bool(auto_dodge_enabled)
        if dodge_lead_time_seconds is not None:
            cfg.defense.dodge_lead_time_seconds = int(dodge_lead_time_seconds)
            def_patch["dodge_lead_time_seconds"] = int(dodge_lead_time_seconds)
        if dodge_cancel_delay_seconds is not None:
            cfg.defense.dodge_cancel_delay_seconds = int(dodge_cancel_delay_seconds)
            def_patch["dodge_cancel_delay_seconds"] = int(dodge_cancel_delay_seconds)
        if escape_coords is not None:
            clean_coords = escape_coords.strip() if escape_coords else None
            cfg.defense.escape_coords = clean_coords
            def_patch["escape_coords"] = clean_coords
        if auto_dodge_all_units is not None:
            cfg.defense.auto_dodge_all_units = bool(auto_dodge_all_units)
            def_patch["auto_dodge_all_units"] = bool(auto_dodge_all_units)
        if alarm_sound_enabled is not None:
            cfg.defense.alarm_sound_enabled = bool(alarm_sound_enabled)
            def_patch["alarm_sound_enabled"] = bool(alarm_sound_enabled)
        if check_interval_seconds is not None:
            cfg.defense.check_interval_seconds = float(check_interval_seconds)
            def_patch["check_interval_seconds"] = float(check_interval_seconds)

        if def_patch:
            self.update_config_and_save({"defense": def_patch})

        if cfg.defense.enabled and acc and sch:
            self.defense_manager.schedule_defense_monitor(
                scheduler=sch,
                account=acc,
                config=cfg.defense,
            )

        self.broadcast_sync("MODULE_TOGGLED", {"module": "defense", "config": def_patch, "world": cfg.world})
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {
            "status": "success",
            "message": "Configurações de defesa atualizadas com sucesso.",
            "defense": self.get_defense_status(world),
        }

    async def trigger_manual_dodge(
        self,
        village_id: Optional[int] = None,
        escape_coords: Optional[str] = None,
        offensive_only: bool = False,
        world: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispara uma manobra imediata de esquiva de tropas (Dodge) na aldeia especificada."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        cfg = inst.config if inst else self.config
        if not acc:
            return {"status": "error", "message": "Conta não conectada."}

        target_v_id = village_id or acc.current_village_id
        pref_coords = escape_coords or getattr(cfg.defense, "escape_coords", None)
        target_coords = await self.defense_manager.find_escape_village(acc, target_v_id, pref_coords)

        res = await self.place_manager.send_dodge_command(
            account=acc,
            target_coords=target_coords,
            village_id=target_v_id,
            offensive_only=offensive_only,
        )
        if not res.get("success"):
            return {"status": "error", "message": res.get("message", "Falha ao enviar dodge manual.")}

        cmd_id = res.get("command_id") or f"manual_dodge_{int(time.time())}"
        cancel_delay = getattr(cfg.defense, "dodge_cancel_delay_seconds", 5)
        impact_ts = time.time() + 60.0
        cancel_ts = time.time() + cancel_delay + 5.0

        op = DodgeOperation(
            incoming_command_id=f"manual_{int(time.time())}",
            village_id=target_v_id,
            escape_coords=f"{target_coords[0]}|{target_coords[1]}",
            dodge_command_id=cmd_id,
            impact_timestamp=impact_ts,
            dispatched_at=time.time(),
            cancel_at=cancel_ts,
            status="dispatched",
            units=res.get("units", {}),
            message="Dodge manual disparado com sucesso.",
        )
        self.defense_manager.active_dodges[cmd_id] = op

        self.broadcast_sync("DODGE_EXECUTED", {"dodge": op.to_dict(), "world": cfg.world})
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {
            "status": "success",
            "message": f"Dodge manual enviado para ({target_coords[0]}|{target_coords[1]}). Comando: {cmd_id}",
            "dodge": op.to_dict(),
        }

    async def cancel_defense_command(
        self,
        command_id: str,
        village_id: Optional[int] = None,
        world: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancela um comando militar de esquiva em andamento."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        if not acc:
            return {"status": "error", "message": "Conta não conectada."}

        target_v_id = village_id or acc.current_village_id
        ok = await self.defense_manager.cancel_dodge(acc, command_id, village_id=target_v_id)
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {
            "status": "success" if ok else "error",
            "message": "Comando cancelado com sucesso." if ok else "Falha ao cancelar comando.",
            "command_id": command_id,
            "cancelled": ok,
        }

    # =========================================================================
    # Táticas de Combate & Sincronização ao Milissegundo (Item 2.9)
    # =========================================================================

    async def ping_clock_sync(self, world: Optional[str] = None) -> Dict[str, Any]:
        """Efetua uma medição rápida de RTT e sincronização com o servidor do jogo."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        if not acc:
            return {"status": "error", "message": "Conta não conectada."}

        t_send = time.time()
        try:
            html = await acc.get_screen("place", apply_jitter=False)
            t_recv = time.time()
            server_ts = self.clock_sync.parse_server_time_from_headers_or_html(html=html, game_data=acc.last_game_data)
            self.clock_sync.record_sample(t_send, t_recv, server_ts)
            stats = self.clock_sync.get_stats().to_dict()
            self.broadcast_sync("COMBAT_CLOCK_SYNCED", stats)
            self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
            return {"status": "success", "clock_stats": stats}
        except Exception as e:
            return {"status": "error", "message": f"Falha na sincronização de relógio: {e}"}

    async def launch_noble_train(
        self,
        plan_data: Dict[str, Any],
        village_id: Optional[int] = None,
        world: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispara um Comboio de Nobres (Noble Train) com gaps milimétricos e Fail-Safe."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        if not acc:
            return {"status": "error", "message": "Conta não conectada."}

        target_coords = plan_data.get("target_coords")
        if not target_coords or "|" not in target_coords:
            return {"status": "error", "message": "Coordenadas de alvo inválidas (use formato xxx|yyy)."}

        train_size = int(plan_data.get("train_size", 4))
        nuke_dict = plan_data.get("nuke_units", {})
        escort_dict = plan_data.get("escort_units", {"axe": 50, "light": 20})
        gap_ms = int(plan_data.get("gap_ms", getattr(self.config.combat, "noble_train_gap_ms", 100)))
        failsafe_enabled = bool(plan_data.get("failsafe_enabled", getattr(self.config.combat, "failsafe_enabled", True)))
        failsafe_spread = int(plan_data.get("failsafe_max_spread_ms", getattr(self.config.combat, "failsafe_max_spread_ms", 400)))

        plan = NobleTrainPlan(
            target_coords=target_coords,
            train_size=train_size,
            nuke_units=UnitsCount.from_dict(nuke_dict),
            escort_units=UnitsCount.from_dict(escort_dict),
            gap_ms=gap_ms,
            failsafe_enabled=failsafe_enabled,
            failsafe_max_spread_ms=failsafe_spread,
            launch_at_server_ts=plan_data.get("launch_at_server_ts"),
            target_arrival_server_ts=plan_data.get("target_arrival_server_ts"),
        )

        target_v_id = village_id or acc.current_village_id
        operation = await self.combat_manager.execute_noble_train(acc, plan, village_id=target_v_id)

        op_dict = operation.to_dict()
        event_name = "COMBAT_FAILSAFE_TRIGGERED" if operation.status == TacticalOperationStatus.CANCELLED_FAILSAFE else "COMBAT_OPERATION_EXECUTED"
        self.broadcast_sync(event_name, op_dict)
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {
            "status": "success" if operation.status == TacticalOperationStatus.COMPLETED else "warning",
            "message": f"Noble train processado: status '{operation.status.value}'.",
            "operation": op_dict,
        }

    def calculate_backtime(
        self,
        data: Dict[str, Any],
        village_id: Optional[int] = None,
        world: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calcula o momento exato de partida para um contra-ataque de Backtime."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        v_id = village_id or (acc.current_village_id if acc else 1)
        v_obj = acc.villages.get(v_id) if acc else None
        origin_coords = f"{v_obj.x}|{v_obj.y}" if v_obj else data.get("origin_coords", "500|500")

        target_coords = data.get("target_coords", "")
        enemy_return_ts = float(data.get("enemy_return_server_ts", 0))
        slowest_unit = data.get("slowest_unit", "light")

        if not target_coords or enemy_return_ts <= 0:
            return {"status": "error", "message": "Coordenadas ou hora de regresso do inimigo inválidas."}

        res = self.combat_manager.calculate_backtime(
            origin_coords=origin_coords,
            target_coords=target_coords,
            enemy_return_server_ts=enemy_return_ts,
            slowest_unit=slowest_unit,
        )
        return {"status": "success", "calculation": res}

    async def schedule_backtime(
        self,
        data: Dict[str, Any],
        village_id: Optional[int] = None,
        world: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Agenda uma operação militar de Backtime."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        if not acc:
            return {"status": "error", "message": "Conta não conectada."}

        target_coords = data.get("target_coords", "")
        enemy_return_ts = float(data.get("enemy_return_server_ts", 0))
        slowest_unit = data.get("slowest_unit", "light")
        units_dict = data.get("units", {})

        plan = BacktimePlan(
            target_coords=target_coords,
            enemy_return_server_ts=enemy_return_ts,
            units=UnitsCount.from_dict(units_dict),
            slowest_unit=slowest_unit,
        )

        target_v_id = village_id or acc.current_village_id
        try:
            op = await self.combat_manager.schedule_backtime(acc, plan, village_id=target_v_id)
            self.broadcast_sync("COMBAT_OPERATION_SCHEDULED", op.to_dict())
            self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
            return {"status": "success", "operation": op.to_dict()}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def analyze_snipes(
        self,
        village_id: Optional[int] = None,
        world: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analisa incomings ativos para detectar comboios e sugerir janelas de intercalação (snipe)."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account

        incomings = [inc.to_dict() for inc in self.defense_manager.active_incomings.values()]
        own_vills = []
        if acc:
            for v in acc.villages.values():
                own_vills.append({"id": v.id, "name": v.name, "x": v.x, "y": v.y})

        suggestions = self.combat_manager.analyze_snipes(incomings, own_vills)
        return {"status": "success", "suggestions": suggestions, "incomings_count": len(incomings)}

    def cancel_tactical_operation(self, op_id: str) -> Dict[str, Any]:
        """Cancela uma operação tática de combate agendada."""
        op = self.combat_manager.operations.get(op_id)
        if not op:
            return {"status": "error", "message": f"Operação '{op_id}' não encontrada."}

        op.status = TacticalOperationStatus.CANCELLED_MANUAL
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {"status": "success", "message": f"Operação {op_id} cancelada manualmente.", "operation": op.to_dict()}

    def update_combat_config(
        self,
        config_data: Dict[str, Any],
        world: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Atualiza os parâmetros de combate e persistência."""
        inst = self.world_manager.get_instance(world)
        cfg = inst.config if inst else self.config

        if "noble_train_gap_ms" in config_data:
            cfg.combat.noble_train_gap_ms = max(20, min(1000, int(config_data["noble_train_gap_ms"])))
        if "failsafe_enabled" in config_data:
            cfg.combat.failsafe_enabled = bool(config_data["failsafe_enabled"])
        if "failsafe_max_spread_ms" in config_data:
            cfg.combat.failsafe_max_spread_ms = max(50, min(5000, int(config_data["failsafe_max_spread_ms"])))
        if "default_noble_escort" in config_data and isinstance(config_data["default_noble_escort"], dict):
            cfg.combat.default_noble_escort = config_data["default_noble_escort"]
        if "snipe_tolerance_ms" in config_data:
            cfg.combat.snipe_tolerance_ms = int(config_data["snipe_tolerance_ms"])

        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {
            "status": "success",
            "message": "Configurações de combate atualizadas com sucesso.",
            "combat_config": {
                "noble_train_gap_ms": cfg.combat.noble_train_gap_ms,
                "failsafe_enabled": cfg.combat.failsafe_enabled,
                "failsafe_max_spread_ms": cfg.combat.failsafe_max_spread_ms,
                "default_noble_escort": cfg.combat.default_noble_escort,
                "snipe_tolerance_ms": cfg.combat.snipe_tolerance_ms,
            },
        }

    def _get_world_context(self, world: Optional[str] = None):
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst and inst.account else self.account
        cfg = inst.config if inst and inst.config else self.config
        return inst, acc, cfg

    # =========================================================================
    # Coleta de Recursos / Scavenging (Ponto 2.4 & Fase 4)
    # =========================================================================

    async def get_scavenge_status(self, village_id: Optional[int] = None, world: Optional[str] = None) -> Dict[str, Any]:
        inst, acc, cfg = self._get_world_context(world)
        if not acc:
            return {"status": "error", "message": "Conta não conectada no mundo especificado."}

        v_id = village_id or acc.current_village_id or 0
        state = await self.scavenge_manager.get_scavenge_state(acc, village_id=v_id)
        scv_cfg = getattr(cfg, "scavenge", None)
        return {
            "status": "success",
            "village_id": v_id,
            "options": [
                {
                    "id": opt.id,
                    "name": opt.name,
                    "description": opt.description,
                    "is_unlocked": opt.is_unlocked,
                    "is_locked": opt.is_locked,
                    "is_scavenging": opt.is_scavenging,
                    "time_remaining_seconds": opt.time_remaining_seconds,
                    "loot_ratio": opt.loot_ratio,
                    "unlock_cost": opt.unlock_cost,
                }
                for opt in state.options
            ],
            "available_troops": state.available_troops,
            "active_expeditions_count": state.active_expeditions_count,
            "min_return_time_seconds": state.min_return_time_seconds,
            "config": {
                "enabled": getattr(scv_cfg, "enabled", False),
                "auto_unlock": getattr(scv_cfg, "auto_unlock", True),
                "eligible_units": getattr(scv_cfg, "eligible_units", ["spear", "sword", "axe", "archer", "light"]),
                "min_reserved_units": getattr(scv_cfg, "min_reserved_units", {}),
            },
        }

    def toggle_scavenge_module(
        self,
        enabled: Optional[bool] = None,
        auto_unlock: Optional[bool] = None,
        eligible_units: Optional[List[str]] = None,
        min_reserved_units: Optional[Dict[str, int]] = None,
        check_interval_seconds: Optional[float] = None,
        world: Optional[str] = None,
    ) -> Dict[str, Any]:
        inst, acc, cfg = self._get_world_context(world)
        scv = getattr(cfg, "scavenge", None)
        if not scv:
            return {"status": "error", "message": "Configurações de scavenge não encontradas."}

        if enabled is not None:
            scv.enabled = bool(enabled)
        if auto_unlock is not None:
            scv.auto_unlock = bool(auto_unlock)
        if eligible_units is not None:
            scv.eligible_units = eligible_units
        if min_reserved_units is not None:
            scv.min_reserved_units = min_reserved_units
        if check_interval_seconds is not None:
            scv.check_interval_seconds = float(check_interval_seconds)

        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {"status": "success", "message": f"Coleta automática {'ligada' if scv.enabled else 'desligada'}."}

    async def trigger_scavenge_cycle(self, village_id: Optional[int] = None, world: Optional[str] = None) -> Dict[str, Any]:
        inst, acc, cfg = self._get_world_context(world)
        if not acc:
            return {"status": "error", "message": "Conta não conectada no mundo especificado."}

        scv_cfg = getattr(cfg, "scavenge", None)
        res = await self.scavenge_manager.execute_scavenge_cycle(acc, scv_cfg, village_id=village_id)
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return res

    async def unlock_scavenge_option(self, option_id: int, village_id: Optional[int] = None, world: Optional[str] = None) -> Dict[str, Any]:
        inst, acc, cfg = self._get_world_context(world)
        if not acc:
            return {"status": "error", "message": "Conta não conectada no mundo especificado."}

        ok = await self.scavenge_manager.unlock_scavenge_option(acc, option_id, village_id=village_id)
        return {"status": "success" if ok else "failed", "unlocked": ok}

    # =========================================================================
    # Academia & Cunha de Moedas (Ponto 2.6 & Fase 4)
    # =========================================================================

    async def get_snob_status(self, village_id: Optional[int] = None, world: Optional[str] = None) -> Dict[str, Any]:
        inst, acc, cfg = self._get_world_context(world)
        if not acc:
            return {"status": "error", "message": "Conta não conectada no mundo especificado."}

        state = await self.snob_manager.get_snob_state(acc, village_id=village_id)
        snb_cfg = getattr(cfg, "snob", None)
        return {
            "status": "success",
            "snob_state": state.to_dict(),
            "config": {
                "auto_mint_enabled": getattr(snb_cfg, "auto_mint_enabled", False),
                "storage_threshold_percent": getattr(snb_cfg, "storage_threshold_percent", 85.0),
                "auto_recruit_nobles": getattr(snb_cfg, "auto_recruit_nobles", False),
            },
        }

    async def mint_snob_coins(self, count: int = 1, village_id: Optional[int] = None, world: Optional[str] = None) -> Dict[str, Any]:
        inst, acc, cfg = self._get_world_context(world)
        if not acc:
            return {"status": "error", "message": "Conta não conectada no mundo especificado."}

        ok = await self.snob_manager.mint_coins(acc, count=count, village_id=village_id)
        return {"status": "success" if ok else "failed", "minted_count": count if ok else 0}

    async def recruit_snob_nobleman(self, village_id: Optional[int] = None, world: Optional[str] = None) -> Dict[str, Any]:
        inst, acc, cfg = self._get_world_context(world)
        if not acc:
            return {"status": "error", "message": "Conta não conectada no mundo especificado."}

        ok = await self.snob_manager.recruit_nobleman(acc, village_id=village_id)
        return {"status": "success" if ok else "failed"}

    def update_snob_config(self, payload: Dict[str, Any], world: Optional[str] = None) -> Dict[str, Any]:
        inst, acc, cfg = self._get_world_context(world)
        snb = getattr(cfg, "snob", None)
        if not snb:
            return {"status": "error", "message": "Configurações de snob não encontradas."}

        if "auto_mint_enabled" in payload:
            snb.auto_mint_enabled = bool(payload["auto_mint_enabled"])
        if "storage_threshold_percent" in payload:
            snb.storage_threshold_percent = float(payload["storage_threshold_percent"])
        if "auto_recruit_nobles" in payload:
            snb.auto_recruit_nobles = bool(payload["auto_recruit_nobles"])

        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {"status": "success", "message": "Configurações da Academia atualizadas."}

    # =========================================================================
    # Visualizador de Inventário & Gestão de Itens (Ponto 2.10 & Fase 4)
    # =========================================================================

    async def get_inventory_items(self, force_refresh: bool = False, world: Optional[str] = None) -> Dict[str, Any]:
        inst, acc, cfg = self._get_world_context(world)
        if not acc:
            return {"status": "error", "message": "Conta não conectada no mundo especificado."}

        items = await self.inventory_manager.get_inventory_items(acc, force_refresh=force_refresh)
        return {
            "status": "success",
            "items_count": len(items),
            "items": [it.to_dict() for it in items],
        }

    async def use_inventory_item(self, item_id: str, village_id: Optional[int] = None, world: Optional[str] = None) -> Dict[str, Any]:
        inst, acc, cfg = self._get_world_context(world)
        if not acc:
            return {"status": "error", "message": "Conta não conectada no mundo especificado."}

        ok = await self.inventory_manager.use_item(acc, item_id=item_id, village_id=village_id)
        return {
            "status": "success" if ok else "failed",
            "message": f"Item {item_id} {'ativado com sucesso' if ok else 'falhou ao ser ativado'}."
        }

    # =========================================================================
    # Cloud SQL / Multi-Account & Multi-World Concurrency Handlers
    # =========================================================================

    async def register_app_user(self, email: str, password: str, license_type: str = "standard") -> Dict[str, Any]:
        """Regista um novo utilizador da aplicação na base de dados Cloud SQL."""
        existing = await self.user_repo.get_by_email(email)
        if existing:
            return {"status": "error", "message": "Já existe um utilizador registado com este email."}
        user = await self.user_repo.create_user(email=email, password=password, license_type=license_type)
        self.current_app_user = user
        return {
            "status": "success",
            "user": user.to_dict(),
            "message": "Utilizador registado com sucesso!",
        }

    async def login_app_user(self, email: str, password: str) -> Dict[str, Any]:
        """Autentica o utilizador da aplicação."""
        user = await self.user_repo.authenticate(email=email, password=password)
        if not user:
            return {"status": "error", "message": "Email ou password inválidos."}
        # Se mudou de utilizador da app, limpa a sessão em memória do utilizador anterior
        if self.current_app_user and self.current_app_user.id != user.id:
            self.account = None
            self.active_profile_id = None
            if hasattr(self, "session_manager"):
                self.session_manager.active_account_id = None
                self.session_manager.active_game_username = None
                try:
                    await self.session_manager.stop_current_session()
                except Exception:
                    pass
        self.current_app_user = user
        return {
            "status": "success",
            "user": user.to_dict(),
            "message": f"Sessão iniciada como {user.email}.",
        }

    async def ensure_current_app_user(self):
        """Assegura que self.current_app_user está carregado a partir do token_storage se for None."""
        if not self.current_app_user:
            try:
                from engine.storage.token_storage import token_storage
                saved_token = token_storage.load_token()
                if saved_token:
                    user = await self.user_repo.get_by_id(saved_token)
                    if user:
                        self.current_app_user = user
            except Exception as e:
                logger.debug(f"Aviso ao tentar restaurar sessão do Cloud SQL: {e}")
        return self.current_app_user

    async def get_current_app_user(self) -> Dict[str, Any]:
        """Retorna o utilizador da aplicação atualmente autenticado."""
        await self.ensure_current_app_user()
        if not self.current_app_user:
            return {"status": "error", "message": "Nenhum utilizador autenticado."}
        return {
            "status": "success",
            "user": self.current_app_user.to_dict(),
        }

    async def list_user_game_accounts(self) -> Dict[str, Any]:
        """Lista todas as contas de jogo do utilizador autenticado com mundos e cofres."""
        await self.ensure_current_app_user()
        if not self.current_app_user:
            return {"status": "error", "message": "Autenticação requerida."}
        accounts = await self.game_account_repo.list_by_user(self.current_app_user.id)
        active_user = self.session_manager.active_game_username

        result = []
        for acc in accounts:
            a_dict = acc.to_dict()
            a_dict["name"] = acc.game_username
            a_dict["is_active_session"] = bool(active_user and active_user.lower() == acc.game_username.lower())

            # Consulta mundos associados no Cloud SQL
            try:
                worlds = await self.game_world_repo.list_by_account(acc.id)
                world_codes = [w.world_code for w in worlds]
                a_dict["worlds"] = world_codes
                a_dict["world"] = world_codes[0] if world_codes else "pt117"
                a_dict["world_domain"] = f"{a_dict['world']}.tribalwars.com.pt"
            except Exception:
                a_dict["worlds"] = ["pt117"]
                a_dict["world"] = "pt117"
                a_dict["world_domain"] = "pt117.tribalwars.com.pt"

            try:
                creds = self.game_account_repo.decrypt_credentials(acc)
                a_dict["session_cookie"] = creds.get("sid", "")
                a_dict["sid"] = creds.get("sid", "")
                a_dict["has_password"] = bool(creds.get("password"))
                a_dict["auto_login_enabled"] = bool(creds.get("auto_login_enabled", False))
                a_dict["last_auto_login"] = creds.get("last_auto_login")
                if creds.get("domain"):
                    a_dict["domain"] = creds.get("domain")
                    a_dict["world_domain"] = f"{a_dict['world']}.{creds.get('domain')}"
                if creds.get("world"):
                    a_dict["world"] = creds.get("world")
            except Exception:
                pass
            result.append(a_dict)

        return {
            "status": "success",
            "active_username": active_user,
            "accounts": result,
        }

    async def add_user_game_account(
        self,
        game_username: str,
        sid: str = "",
        domain: str = "tribalwars.com.pt",
        world: Optional[str] = None,
        proxy: Optional[str] = None,
        password: Optional[str] = None,
        auto_login_enabled: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Regista ou atualiza uma conta de jogo encriptando as credenciais no cofre e persistindo o mundo."""
        await self.ensure_current_app_user()
        if not self.current_app_user:
            return {"status": "error", "message": "Autenticação requerida."}

        target_world = (world.split(".")[0].strip().lower() if world else "pt117")

        # Preserva password e definições anteriores se não forem passadas novamente
        existing_acc = await self.game_account_repo.get_by_user_and_username(self.current_app_user.id, game_username)
        existing_creds = {}
        if existing_acc:
            try:
                existing_creds = self.game_account_repo.decrypt_credentials(existing_acc)
            except Exception:
                pass

        final_password = password.strip() if password else existing_creds.get("password")
        final_sid = sid.strip() if sid else existing_creds.get("sid", "")
        final_auto_login = (
            bool(auto_login_enabled)
            if auto_login_enabled is not None
            else existing_creds.get("auto_login_enabled", bool(final_password))
        )

        creds = {
            "sid": final_sid,
            "domain": domain.strip() if domain else "tribalwars.com.pt",
            "world": target_world,
            "proxy": proxy.strip() if proxy else existing_creds.get("proxy"),
            "password": final_password,
            "auto_login_enabled": final_auto_login,
            "last_auto_login": existing_creds.get("last_auto_login"),
        }
        acc = await self.game_account_repo.create_or_update(
            app_user_id=self.current_app_user.id,
            game_username=game_username.strip(),
            credentials_data=creds,
        )

        gw_obj = None
        if target_world:
            gw_obj = await self.game_world_repo.get_or_create(
                game_account_id=acc.id,
                world_code=target_world,
                is_active=True,
            )

        return {
            "status": "success",
            "account": acc.to_dict(),
            "world": gw_obj.to_dict() if gw_obj else None,
            "message": f"Conta de jogo '{game_username}' gravada com cofre seguro no Cloud SQL!",
        }

    async def perform_auto_login(self, account_id: str) -> Dict[str, Any]:
        """
        Executa o fluxo de autenticação automática direta para a conta selecionada.
        Se bem-sucedido, atualiza o SID no cofre e na sessão em runtime.
        Se falhar por CAPTCHA ou credenciais, reporta o erro e NÃO repete para evitar bloqueio.
        """
        await self.ensure_current_app_user()
        if not self.current_app_user:
            return {"status": "error", "message": "Autenticação requerida."}

        acc = await self.game_account_repo.get_by_id(account_id)
        if not acc:
            return {"status": "error", "message": f"Conta '{account_id}' não encontrada."}

        if acc.app_user_id != self.current_app_user.id:
            return {"status": "error", "message": "Acesso não autorizado a esta conta de jogo."}

        try:
            creds = self.game_account_repo.decrypt_credentials(acc)
        except Exception as e:
            return {"status": "error", "message": f"Falha ao aceder ao cofre de credenciais: {e}"}

        password = creds.get("password")
        if not password:
            return {
                "status": "error",
                "error_type": "no_password",
                "message": f"A conta '{acc.game_username}' não tem palavra-passe guardada no cofre. Edite a conta para configurar.",
            }

        world = creds.get("world") or "pt117"
        domain = creds.get("domain") or "tribalwars.com.pt"
        proxy = creds.get("proxy")

        from engine.core.auth_handler import TribalWarsAuthHandler
        handler = TribalWarsAuthHandler(domain=domain, proxy=proxy)

        logger.info(f"[AutoLogin] A iniciar autenticação automática para '{acc.game_username}' no mundo {world}...")
        res = await handler.login(
            username=acc.game_username,
            password=password,
            target_world=world,
        )

        if not res.success:
            logger.warning(f"[AutoLogin] Falha no auto-login de '{acc.game_username}': {res.message}")
            if res.captcha_detected and hasattr(self, "broadcast_sync"):
                self.broadcast_sync("ANTI_BOT_ALERT", {
                    "account": acc.game_username,
                    "world": world,
                    "message": "CAPTCHA / Verificação anti-bot intercetada no login. Resolução manual necessária.",
                })
            return {
                "status": "error",
                "error_type": res.error_type,
                "captcha_detected": res.captcha_detected,
                "message": res.message,
            }

        # Sucesso! Atualiza o SID no cofre encriptado
        new_sid = res.sid
        creds["sid"] = new_sid
        creds["last_auto_login"] = time.time()
        await self.game_account_repo.create_or_update(
            app_user_id=self.current_app_user.id,
            game_username=acc.game_username,
            credentials_data=creds,
        )

        # Atualiza a sessão em runtime se for a conta ativa
        if self.account and (getattr(self.account, "username", "").lower() == acc.game_username.lower() or self.active_profile_id == acc.id):
            await self.account.update_sid(new_sid)
            try:
                await self.account.refresh_state()
            except Exception:
                pass

        if hasattr(self, "broadcast_sync"):
            self.broadcast_sync("AUTO_LOGIN_SUCCESS", {
                "account": acc.game_username,
                "world": world,
                "message": f"Sessão renovada com sucesso via auto-login ({acc.game_username}).",
            })

        return {
            "status": "success",
            "message": f"Login automático concluído com sucesso para '{acc.game_username}'!",
            "account_id": acc.id,
            "game_username": acc.game_username,
            "world": world,
            "sid": new_sid,
        }

    async def switch_active_game_account(self, game_username: str, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Invoca o singleton AccountSessionManager para realizar a exclusão mútua e troca atómica.
        """
        if not self.current_app_user:
            return {"status": "error", "message": "Autenticação requerida."}

        target_acc = None
        if account_id:
            target_acc = await self.game_account_repo.get_by_id(account_id)
        if not target_acc:
            target_acc = await self.game_account_repo.get_by_user_and_username(self.current_app_user.id, game_username)

        acc_id = target_acc.id if target_acc else account_id

        session_status = await self.session_manager.switch_account(
            app_user_id=self.current_app_user.id,
            game_username=game_username,
            account_id=acc_id,
        )
        self.broadcast_sync("ACCOUNT_SWITCHED", session_status)
        return {
            "status": "success",
            "session": session_status,
            "message": f"Conta ativa alterada para '{game_username}'.",
        }

    async def list_game_worlds(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """Lista os mundos associados à conta ativa e respetivo status dos workers."""
        acc_id = account_id or self.session_manager.active_account_id
        if not acc_id:
            return {"status": "error", "message": "Nenhuma conta de jogo selecionada."}

        worlds = await self.game_world_repo.list_by_account(acc_id)
        orch = self.session_manager.orchestrator
        workers_status = orch.get_status().get("workers", {}) if orch else {}

        result = []
        for w in worlds:
            w_dict = w.to_dict()
            worker_info = workers_status.get(w.world_code, {})
            w_dict["worker"] = worker_info
            result.append(w_dict)

        return {
            "status": "success",
            "account_id": acc_id,
            "active_focus_world": orch.active_focus_world if orch else None,
            "worlds": result,
        }

    async def add_game_world(self, world_code: str, is_active: bool = True) -> Dict[str, Any]:
        """Adiciona um mundo à conta de jogo ativa no Cloud SQL."""
        acc_id = self.session_manager.active_account_id
        if not acc_id:
            return {"status": "error", "message": "Nenhuma conta de jogo ativa no momento."}

        gw = await self.game_world_repo.get_or_create(game_account_id=acc_id, world_code=world_code, is_active=is_active)
        orch = self.session_manager.orchestrator
        if orch:
            await orch.register_and_start_worker(
                world_code=world_code,
                is_active=is_active,
                account_id=acc_id,
            )
        return {
            "status": "success",
            "world": gw.to_dict(),
            "message": f"Mundo '{world_code}' adicionado e orquestrado!",
        }

    async def toggle_game_world_worker(self, world_code: str, is_active: bool) -> Dict[str, Any]:
        """Ativa ou desativa as rotinas de background de um mundo individual."""
        orch = self.session_manager.orchestrator
        if orch:
            await orch.toggle_world_worker(world_code=world_code, is_active=is_active)
        return {
            "status": "success",
            "world_code": world_code,
            "is_active": is_active,
            "message": f"Mundo '{world_code}' {'ativado' if is_active else 'pausado'}.",
        }

    async def list_world_villages(self, world_code: str) -> Dict[str, Any]:
        """Lista todas as aldeias da tabela 'villages' para o mundo especificado."""
        await self.ensure_current_app_user()
        acc_id = self.session_manager.active_account_id or self.active_profile_id

        # 1. Se não tiver acc_id direto, tenta obter a partir do username ativo ou das contas do utilizador
        if not acc_id and self.current_app_user:
            runtime_name = None
            if self.account:
                runtime_name = getattr(self.account, "player_name", None)
                if not runtime_name and getattr(self.account, "player", None):
                    runtime_name = getattr(self.account.player, "name", None)
                if not runtime_name:
                    runtime_name = getattr(self.account, "username", None)

            target_username = self.session_manager.active_game_username or runtime_name
            if target_username:
                acc = await self.game_account_repo.get_by_user_and_username(self.current_app_user.id, target_username)
                if acc:
                    acc_id = acc.id
                    self.session_manager.active_account_id = acc.id
                    self.session_manager.active_game_username = acc.game_username

            if not acc_id:
                user_accounts = await self.game_account_repo.list_by_user(self.current_app_user.id)
                if user_accounts:
                    acc_id = user_accounts[0].id
                    self.session_manager.active_account_id = acc_id
                    self.session_manager.active_game_username = user_accounts[0].game_username

        # 2. Se o runtime do bot tiver uma conta conectada em memória, assegura no Cloud SQL
        runtime_p = None
        if self.account:
            runtime_p = getattr(self.account, "player_name", None)
            if not runtime_p and getattr(self.account, "player", None):
                runtime_p = getattr(self.account.player, "name", None)
            if not runtime_p:
                runtime_p = getattr(self.account, "username", None)

        if not acc_id and self.current_app_user and runtime_p:
            p_name = str(runtime_p).strip()
            acc = await self.game_account_repo.create_or_update(
                app_user_id=self.current_app_user.id,
                game_username=p_name,
                credentials_data={
                    "sid": getattr(self.account, "sid", "") or self.config.sid or "",
                    "domain": self.config.domain,
                    "world": world_code,
                },
            )
            acc_id = acc.id
            self.session_manager.active_account_id = acc.id
            self.session_manager.active_game_username = p_name
            self.session_manager.active_account_id = acc.id
            self.session_manager.active_game_username = p_name

        # 3. Se realmente não existir nenhuma conta ainda, retorna lista vazia de aldeias graciosamente
        if not acc_id:
            return {
                "status": "success",
                "world_code": world_code,
                "game_world_id": None,
                "villages": [],
                "message": "Nenhuma conta de jogo ativa configurada no momento.",
            }

        target_world = (world_code or getattr(self.account, "world", "") or self.config.world or "pt117").lower()
        gw = await self.game_world_repo.get_or_create(game_account_id=acc_id, world_code=target_world)
        villages = await self.village_repo.list_by_world(gw.id)

        # Se a tabela 'villages' na Cloud SQL estiver vazia mas tivermos aldeias em memória no bot, sincroniza-as!
        if not villages and self.account and self.account.villages:
            await self.sync_account_villages_to_cloud(
                world_code=target_world,
                villages_dict=self.account.villages,
            )
            villages = await self.village_repo.list_by_world(gw.id)

        return {
            "status": "success",
            "world_code": target_world,
            "game_world_id": gw.id,
            "villages": [v.to_dict() for v in villages],
        }

    async def update_village_build_model(self, village_id: str, active_build_model_id: str) -> Dict[str, Any]:
        """Define o modelo de construção ativo para uma aldeia na base de dados."""
        updated = await self.village_repo.update_build_model(
            village_id=village_id,
            active_build_model_id=active_build_model_id,
        )
        if not updated:
            return {"status": "error", "message": "Aldeia não encontrada."}
        return {
            "status": "success",
            "village": updated.to_dict(),
            "message": f"Modelo '{active_build_model_id}' atribuído com sucesso!",
        }

    async def sync_account_villages_to_cloud(
        self,
        game_username: Optional[str] = None,
        world_code: Optional[str] = None,
        villages_dict: Optional[Dict[int, Any]] = None,
    ) -> int:
        """
        Persiste todas as aldeias sincronizadas em memória na tabela 'villages' do Cloud SQL.
        Garante que a hierarquia GameAccount -> GameWorld -> Village está íntegra e persistida.
        """
        await self.ensure_current_app_user()
        if not self.current_app_user:
            return 0

        target_username = game_username or self.session_manager.active_game_username
        if not target_username and self.account:
            p_val = getattr(self.account, "player_name", None)
            if not p_val and getattr(self.account, "player", None):
                p_val = getattr(self.account.player, "name", None)
            if not p_val:
                p_val = getattr(self.account, "username", None)
            if p_val:
                target_username = str(p_val).strip()

        if not target_username:
            return 0

        # Obtém ou cria a GameAccount no Cloud SQL
        target_acc = await self.game_account_repo.get_by_user_and_username(
            self.current_app_user.id, target_username
        )
        sid_val = getattr(self.account, "sid", "") or self.config.sid or ""
        target_world = (world_code or getattr(self.account, "world", "") or self.config.world or "pt117").lower()

        if not target_acc:
            target_acc = await self.game_account_repo.create_or_update(
                app_user_id=self.current_app_user.id,
                game_username=target_username,
                credentials_data={"sid": sid_val, "domain": self.config.domain, "world": target_world},
            )
        elif sid_val:
            try:
                creds = self.game_account_repo.decrypt_credentials(target_acc)
                if creds.get("sid") != sid_val or creds.get("world") != target_world:
                    creds["sid"] = sid_val
                    creds["world"] = target_world
                    await self.game_account_repo.create_or_update(
                        app_user_id=self.current_app_user.id,
                        game_username=target_username,
                        credentials_data=creds,
                    )
            except Exception:
                pass

        # Garante a existência do GameWorld
        gw = await self.game_world_repo.get_or_create(
            game_account_id=target_acc.id,
            world_code=target_world,
            is_active=True,
        )

        # Mapeia as aldeias a persistir
        vills = villages_dict if villages_dict is not None else (getattr(self.account, "villages", {}) if self.account else {})
        count = 0
        for vid, vdata in vills.items():
            try:
                name = getattr(vdata, "name", "") or f"Aldeia {vid}"
                x = getattr(vdata, "x", 0) or 0
                y = getattr(vdata, "y", 0) or 0
                await self.village_repo.upsert_village(
                    game_world_id=gw.id,
                    village_game_id=int(vid),
                    village_name=name,
                    coord_x=int(x),
                    coord_y=int(y),
                )
                count += 1
            except Exception as e:
                logger.warning(f"Erro ao persistir aldeia {vid} no Cloud SQL: {e}")

        if count > 0:
            logger.info(f"[Cloud SQL] Sincronizadas {count} aldeias no mundo '{target_world}' para '{target_username}'.")
        return count








