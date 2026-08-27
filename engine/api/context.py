"""
Tribal Wars Mobile Automation Engine - Orquestrador de Contexto do Sidecar
Mantém o estado unificado, distribui eventos para WebSockets e fornece acesso às ações.
"""

import asyncio
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket

from engine.actions.farm import FarmManager
from engine.actions.main_building import MainBuildingManager
from engine.actions.place import PlaceManager
from engine.actions.recruitment import RecruitmentManager
from engine.config.settings import BotConfig, load_config
from engine.core.account import TribalAccount
from engine.core.models import TaskPriority
from engine.core.profile_manager import ProfileManager
from engine.core.scheduler import TaskScheduler


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

        # Gestores de ecrãs/ações da Fase 2
        self.main_building_manager = MainBuildingManager()
        self.place_manager = PlaceManager()
        self.farm_manager = FarmManager()
        self.recruitment_manager = RecruitmentManager()
        self.profile_manager = ProfileManager()


        # Clientes WebSocket ativos
        self.active_websockets: Set[WebSocket] = set()

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
        """Força a execução imediata de um ciclo de construção de edifícios."""
        if not self.account:
            return {"status": "error", "message": "Conta não inicializada."}

        target_village = self.account.current_village_id or "active"
        task_id = f"ManualBuild-Village-{target_village}_{time.time_ns()}"

        async def _run():
            await self.main_building_manager.run_build_cycle(
                account=self.account,
                plan=self.config.effective_building_plan,
                max_queue=self.config.building.max_queue,
            )

        self.scheduler.schedule(
            name=f"ManualBuild-Village-{target_village}",
            priority=TaskPriority.BUILD,
            action=_run,
            delay_seconds=0.1,
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

        target_village = self.account.current_village_id or "active"
        task_id = f"ManualRecruit-Village-{target_village}_{time.time_ns()}"

        async def _run():
            await self.recruitment_manager.run_recruitment_cycle(
                account=self.account,
                targets=self.config.recruitment.targets,
                batch_sizes=self.config.recruitment.batch_sizes,
                min_free_pop=self.config.recruitment.min_free_pop,
            )

        self.scheduler.schedule(
            name=f"ManualRecruit-Village-{target_village}",
            priority=TaskPriority.RECRUIT,
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

            # Atualiza recursivamente campos permitidos
            for key, val in new_data.items():
                if isinstance(val, dict) and isinstance(current_raw.get(key), dict):
                    current_raw[key].update(val)
                else:
                    current_raw[key] = val

            # Grava no disco
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

        if self.account:
            curr_v = self.account.current_village
            if curr_v:
                village_data = {
                    "id": curr_v.id,
                    "name": curr_v.name,
                    "coordinates": curr_v.coordinates,
                    "points": curr_v.points,
                    "resources": {
                        "wood": curr_v.resources.wood,
                        "stone": curr_v.resources.stone,
                        "iron": curr_v.resources.iron,
                        "storage_max": curr_v.resources.storage_max,
                        "pop": curr_v.resources.pop,
                        "pop_max": curr_v.resources.pop_max,
                        "free_pop": curr_v.resources.free_pop,
                    },
                }

            if self.account.player:
                p = self.account.player
                player_data = {
                    "id": p.id,
                    "name": p.name,
                    "points": p.points,
                    "villages_count": p.villages_count,
                }

        return {
            "engine": {
                "uptime_seconds": round(self.uptime_seconds, 1),
                "is_running": self.scheduler.is_running,
                "is_paused": self.scheduler.is_paused,
                "queue_size": self.scheduler.queue_size,
            },
            "account": {
                "world": self.config.world,
                "domain": self.config.domain,
                "has_sid": bool(self.config.sid),
                "proxy": self.config.proxy,
                "player": player_data,
                "village": village_data,
                "villages": [v.to_dict() for v in self.account.villages.values()] if self.account else [],
            },

            "modules": {
                "building": {
                    "enabled": True,
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
                },
            },
            "captcha_alert": self.last_captcha_alert,
        }

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

