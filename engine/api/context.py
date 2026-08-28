"""
Tribal Wars Mobile Automation Engine - Orquestrador de Contexto do Sidecar
Mantém o estado unificado, distribui eventos para WebSockets e fornece acesso às ações.
"""

import asyncio
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import WebSocket

from engine.actions.economic_arbitrage import EconomicArbitrageManager
from engine.actions.farm import FarmManager
from engine.actions.main_building import MainBuildingManager
from engine.actions.map import MapData, MapManager
from engine.actions.market import MarketManager
from engine.actions.place import PlaceManager, UnitsCount
from engine.actions.quest import QuestManager
from engine.actions.recruitment import RecruitmentManager
from engine.actions.village_coordinator import MultiVillageCoordinator
from engine.config.settings import BotConfig, load_config
from engine.core.account import TribalAccount
from engine.core.models import TaskPriority
from engine.core.multi_world import MultiWorldManager, WorldInstance
from engine.core.profile_manager import ProfileManager
from engine.core.scheduler import TaskScheduler
from engine.core.stats import StatsTracker


logger = logging.getLogger(__name__)


class EngineContext:
    """
    Contexto global do Sidecar. Agrupa o agendador, a conta, os gestores de ações,
    a configuração ativa e o canal de distribuição de eventos via WebSocket.
    """

    def __init__(
        self,
        scheduler: TaskScheduler,
        config: BotConfig,
        account: Optional[TribalAccount] = None,
        config_path: Optional[Path] = None,
    ):
        self.scheduler = scheduler
        self.config = config
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
        self.profile_manager = ProfileManager()
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
        alert_data = {
            "world": world,
            "detected_at": time.time(),
            "url": f"https://{world}.{self.config.domain}/game.php?screen=bot_protect&page=mobile",
            "snippet": html_snippet[:600] if html_snippet else "",
        }
        self.last_captcha_alert = alert_data
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
            await self.recruitment_manager.run_recruitment_cycle(
                account=self.account,
                targets=targets,
                batch_sizes=self.config.recruitment.batch_sizes,
                min_free_pop=self.config.recruitment.min_free_pop,
                village_id=v_id,
            )

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
        Atualiza as configurações do bot em memória e grava as alterações no config.json.
        """
        try:
            # Lê o JSON atual para preservar comentários e estrutura
            current_raw = {}
            if self.config_path.exists():
                try:
                    current_raw = json.loads(self.config_path.read_text(encoding="utf-8"))
                except Exception:
                    current_raw = {}

            # Atualiza recursivamente campos permitidos com fusão profunda (deep merge)
            def _deep_merge(target: dict, source: dict) -> None:
                for k, v in source.items():
                    if isinstance(v, dict) and isinstance(target.get(k), dict):
                        _deep_merge(target[k], v)
                    else:
                        target[k] = v

            _deep_merge(current_raw, new_data)

            # Grava no disco de forma atómica e persistente
            self.config_path.write_text(json.dumps(current_raw, indent=2), encoding="utf-8")

            # Recarrega a configuração ativa
            self.config = load_config(str(self.config_path))
            self.broadcast_sync("CONFIG_UPDATED", {"config": self.get_config_dict()})
            return {"status": "success", "message": "Configuração atualizada e persistida."}
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
                troops_dict = getattr(curr_v, "troops", {}) or {}
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
        if self.account:
            vill_objs = list(self.account.villages.values())
            if not vill_objs and self.account.current_village:
                vill_objs = [self.account.current_village]
            for v in vill_objs:
                v_dict = v.to_dict()
                cat = self.village_coordinator.get_village_category(self.account, self.config, v.id)
                cat_val = cat.value if hasattr(cat, "value") else str(cat)
                v_dict["category"] = cat_val
                villages_list.append(v_dict)

        # Balanceamento de recursos entre aldeias
        balance_summary = None
        if self.account and len(self.account.villages) > 0:
            balance_summary = self.village_coordinator.calculate_resource_balance(self.account)

        return {
            "engine": {
                "uptime_seconds": round(self.uptime_seconds, 1),
                "is_running": self.scheduler.is_running,
                "is_paused": self.scheduler.is_paused,
                "queue_size": self.scheduler.queue_size,
            },
            "active_world": self.world_manager.active_world or self.config.world,
            "worlds": self.world_manager.list_worlds(),
            "account": {
                "world": self.config.world,
                "domain": self.config.domain,
                "has_sid": bool(self.config.sid),
                "proxy": self.config.proxy,
                "player": player_data,
                "village": village_data,
                "villages": villages_list,
            },
            "resource_balance": balance_summary,
            "resources": resources_dict,
            "troops": troops_dict,
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
            except Exception:
                pass
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

    def list_profiles(self) -> List[Dict[str, Any]]:
        """Lista todos os perfis guardados."""
        return self.profile_manager.list_profiles()

    async def switch_profile(self, profile_id: str) -> Dict[str, Any]:
        """Alterna o perfil de conta ativo."""
        target = self.profile_manager.set_active_profile(profile_id)
        if not target:
            return {"status": "error", "message": f"Perfil '{profile_id}' não encontrado."}

        # Atualiza a configuração ativa
        self.config.world = target.world
        self.config.domain = target.domain
        self.config.sid = target.sid
        self.config.proxy = target.proxy
        self.config.building.template = target.building_template
        if target.username:
            self.config.auth.username = target.username
        if target.password:
            self.config.auth.password = target.password

        # Atualiza a conta de jogo
        if self.account:
            self.account.world = target.world
            self.account.domain = target.domain
            self.account.sid = target.sid
            self.account.proxy = target.proxy
            await self.account.init_session()

        self.broadcast_sync("PROFILE_SWITCHED", {"profile": target.to_dict()})
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {"status": "success", "message": f"Perfil '{target.name}' ativado com sucesso.", "profile": target.to_dict()}

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
        """Alterna o foco do dashboard para outro mundo em execução, auto-registando se necessário."""
        world_key = world.strip().lower()
        inst = self.world_manager.get_instance(world_key)
        if not inst:
            if self.config.sid:
                logger.info(f"A inicializar automaticamente nova instância para o mundo '{world_key}'...")
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

    # --- Gestão Coordenada Multi-Aldeia & Categorização ---

    def set_village_category(self, village_id: int, category: str, world: Optional[str] = None) -> Dict[str, Any]:
        """Atribui categoria (attack, defense, balanced) a uma aldeia e persiste no config.json."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        cfg = inst.config if inst else self.config
        if not acc:
            return {"status": "error", "message": "Conta não inicializada."}

        success = self.village_coordinator.set_village_category(acc, cfg, village_id, category)
        if success:
            new_v_data = {
                "villages": {
                    str(village_id): {
                        "category": category.lower().strip(),
                    }
                }
            }
            self.update_config_and_save(new_v_data)
            self.broadcast_sync("VILLAGE_CATEGORY_UPDATED", {
                "village_id": village_id,
                "category": category,
            })
            return {"status": "success", "message": f"Aldeia {village_id} categorizada como '{category}'."}
        return {"status": "error", "message": "Falha ao definir categoria."}

    async def sync_and_get_all_villages(self, world: Optional[str] = None) -> Dict[str, Any]:
        """Retorna visão detalhada de todas as aldeias da conta com categorias e recursos."""
        inst = self.world_manager.get_instance(world)
        acc = inst.account if inst else self.account
        cfg = inst.config if inst else self.config
        if not acc:
            return {"status": "error", "message": "Conta não inicializada."}

        villages_data = []
        vill_list = list(acc.villages.values())
        if not vill_list and acc.current_village:
            vill_list = [acc.current_village]
        for v in vill_list:
            cat = self.village_coordinator.get_village_category(acc, cfg, v.id)
            cat_val = cat.value if hasattr(cat, "value") else str(cat)
            v_dict = v.to_dict()
            v_dict["category"] = cat_val
            villages_data.append(v_dict)

        balance = self.village_coordinator.calculate_resource_balance(acc)
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

    def add_custom_farm_target(self, x: int, y: int) -> Dict[str, Any]:
        """Adiciona uma coordenada [x, y] à lista de alvos de farm e persiste no config.json."""
        target_pair = (int(x), int(y))
        if target_pair not in self.config.farm.custom_targets:
            self.config.farm.custom_targets.append(target_pair)
            targets_list = [list(t) for t in self.config.farm.custom_targets]
            self.update_config_and_save({"farm": {"custom_targets": targets_list}})
            return {
                "status": "success",
                "message": f"Alvo ({x}|{y}) adicionado com sucesso aos alvos de farm.",
                "custom_targets": targets_list,
            }
        return {
            "status": "info",
            "message": f"Alvo ({x}|{y}) já constava nos alvos de farm.",
            "custom_targets": [list(t) for t in self.config.farm.custom_targets],
        }

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

    def get_stats_tracker(self, world: Optional[str] = None) -> StatsTracker:
        """Obtém ou instancia o rastreador de estatísticas do mundo ativo/solicitado."""
        target_world = world or (self.world_manager.active_world if hasattr(self, "world_manager") else None) or self.config.world
        if target_world not in self.stats_trackers:
            self.stats_trackers[target_world] = StatsTracker(world=target_world)
        return self.stats_trackers[target_world]

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
            )
        self.broadcast_sync("MODULE_TOGGLED", {"module": "building", "enabled": self.config.building.enabled})
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {
            "status": "success",
            "message": f"Construção Automática {'ATIVADA' if self.config.building.enabled else 'DESATIVADA'}.",
            "enabled": self.config.building.enabled,
        }

    # --- Recrutamento Militar & Tropas em Treino ---

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
                village_cat = self.village_coordinator.get_village_category(self.account, self.config, v_id).value

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

    def get_recruitment_models(self) -> Dict[str, Any]:
        """Retorna os modelos de tropas de Ataque e Defesa configurados."""
        from engine.config.settings import DEFAULT_ATTACK_MODEL, DEFAULT_DEFENSE_MODEL
        models = getattr(self.config.recruitment, "models", {
            "attack": DEFAULT_ATTACK_MODEL.copy(),
            "defense": DEFAULT_DEFENSE_MODEL.copy(),
        })
        return {
            "status": "success",
            "models": models,
        }

    def save_recruitment_models(
        self,
        attack: Optional[Dict[str, int]] = None,
        defense: Optional[Dict[str, int]] = None,
        models: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> Dict[str, Any]:
        """Salva todos os modelos de tropas (Ataque, Defesa e Customizados) no config.json."""
        from engine.config.settings import DEFAULT_ATTACK_MODEL, DEFAULT_DEFENSE_MODEL
        current_models = getattr(self.config.recruitment, "models", {
            "attack": DEFAULT_ATTACK_MODEL.copy(),
            "defense": DEFAULT_DEFENSE_MODEL.copy(),
        }).copy()

        if models is not None and isinstance(models, dict):
            # Salva o dicionário completo de modelos recebido
            current_models = {
                str(m_name).lower().strip(): {str(k): max(0, int(v)) for k, v in m_dict.items()}
                for m_name, m_dict in models.items()
                if isinstance(m_dict, dict)
            }
            if "attack" not in current_models:
                current_models["attack"] = DEFAULT_ATTACK_MODEL.copy()
            if "defense" not in current_models:
                current_models["defense"] = DEFAULT_DEFENSE_MODEL.copy()
        else:
            if attack is not None:
                current_models["attack"] = {str(k): max(0, int(v)) for k, v in attack.items()}
            if defense is not None:
                current_models["defense"] = {str(k): max(0, int(v)) for k, v in defense.items()}

        self.config.recruitment.models = current_models
        self.update_config_and_save({"recruitment": {"models": current_models}})
        self.broadcast_sync("RECRUITMENT_MODELS_UPDATED", {"models": current_models})
        return {
            "status": "success",
            "message": "Modelos de tropas guardados e persistidos no config.json com sucesso!",
            "models": current_models,
        }

    def delete_recruitment_model(self, model_name: str) -> Dict[str, Any]:
        """Remove um modelo de tropas customizado e persiste no config.json."""
        m_name = str(model_name).lower().strip()
        if m_name in ("attack", "defense"):
            return {"status": "error", "message": "Os modelos padrão 'attack' e 'defense' não podem ser removidos."}

        current_models = getattr(self.config.recruitment, "models", {}).copy()
        if m_name in current_models:
            del current_models[m_name]
            self.config.recruitment.models = current_models
            self.update_config_and_save({"recruitment": {"models": current_models}})
            self.broadcast_sync("RECRUITMENT_MODELS_UPDATED", {"models": current_models})
            return {"status": "success", "message": f"Modelo '{m_name}' removido com sucesso!", "models": current_models}
        return {"status": "error", "message": f"Modelo '{m_name}' não encontrado."}

    def toggle_recruitment_module(
        self,
        enabled: Optional[bool] = None,
        interval_minutes: Optional[float] = None,
        min_free_pop: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Ativa/desativa ou ajusta a rotina de recrutamento militar contínuo."""
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

        self.update_config_and_save({"recruitment": update_data})
        if self.config.recruitment.enabled and self.account and self.scheduler:
            self.recruitment_manager.schedule_auto_recruit(
                scheduler=self.scheduler,
                account=self.account,
                recruit_config=self.config.recruitment,
                enabled_check=lambda: self.config.recruitment.enabled,
            )
        self.broadcast_sync("MODULE_TOGGLED", {"module": "recruitment", "enabled": self.config.recruitment.enabled})
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {
            "status": "success",
            "message": f"Recrutamento Automático {'ATIVADO' if self.config.recruitment.enabled else 'DESATIVADO'}.",
            "enabled": self.config.recruitment.enabled,
        }

    def toggle_farm_module(
        self,
        enabled: Optional[bool] = None,
        mode: Optional[str] = None,
        template: Optional[str] = None,
        max_distance: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Ativa/desativa ou ajusta a rotina de micro-farming contínuo."""
        update_data = {}
        if enabled is not None:
            update_data["enabled"] = bool(enabled)
            self.config.farm.enabled = bool(enabled)
        if mode is not None:
            update_data["mode"] = str(mode)
            self.config.farm.mode = str(mode)
        if template is not None:
            update_data["template"] = str(template)
            self.config.farm.template = str(template)
        if max_distance is not None:
            update_data["max_distance"] = float(max_distance)
            self.config.farm.max_distance = float(max_distance)

        self.update_config_and_save({"farm": update_data})
        if self.config.farm.enabled and self.account and self.scheduler:
            self.farm_manager.schedule_auto_farm(
                scheduler=self.scheduler,
                account=self.account,
                farm_config=self.config.farm,
            )
        self.broadcast_sync("MODULE_TOGGLED", {"module": "farm", "enabled": self.config.farm.enabled})
        self.broadcast_sync("STATUS_UPDATE", self.get_status_dict())
        return {
            "status": "success",
            "message": f"Micro-Farming {'ATIVADO' if self.config.farm.enabled else 'DESATIVADO'}.",
            "enabled": self.config.farm.enabled,
        }

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




