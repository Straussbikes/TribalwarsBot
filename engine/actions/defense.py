"""
Tribal Wars Mobile Automation Engine - Defense & Incomings Attack Alarm (Prioridade 0 / Alertas)
Monitorização em tempo real de comandos recebidos, deteção da unidade mais lenta (Nobre / Aríete),
rotina de Auto-Dodge com envio a aldeia bárbara 30s antes do impacto e cancelamento pós-impacto.
"""

from dataclasses import asdict, dataclass, field
import logging
import math
import re
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

from engine.actions.place import PlaceManager, UnitsCount
from engine.core.account import TribalAccount
from engine.core.models import Task, TaskPriority
from engine.core.scheduler import TaskScheduler
from engine.utils.parsers import (
    parse_incomings_count,
    parse_incomings_overview,
    parse_timer_to_seconds,
)

logger = logging.getLogger(__name__)

# Velocidades base de marcha por unidade (em segundos por campo, velocidade mundo 1.0)
# 1 campo = minutos * 60
UNIT_SPEED_SECONDS: Dict[str, int] = {
    "spy": 9 * 60,       # 540s
    "light": 10 * 60,     # 600s
    "knight": 10 * 60,    # 600s
    "heavy": 11 * 60,     # 660s
    "axe": 18 * 60,       # 1080s
    "spear": 18 * 60,     # 1080s
    "archer": 18 * 60,    # 1080s
    "sword": 22 * 60,     # 1320s
    "ram": 30 * 60,       # 1800s
    "catapult": 30 * 60,  # 1800s
    "snob": 35 * 60,      # 2100s
}

UNIT_NAMES_PT: Dict[str, str] = {
    "spy": "Espião 👁️",
    "light": "Cavalaria Leve 🐎",
    "knight": "Paladino 🛡️",
    "heavy": "Cavalaria Pesada 🐎🛡️",
    "axe": "Bárbaro / Lanceiro 🪓",
    "spear": "Lanceiro 🗡️",
    "archer": "Arqueiro 🏹",
    "sword": "Espadachim 🗡️",
    "ram": "Aríete / Catapulta 🔨",
    "catapult": "Catapulta 🪨",
    "snob": "Nobre 👑",
    "unknown": "Desconhecido ❓",
}


@dataclass
class IncomingAttack:
    """Representação estruturada de um ataque a caminho."""
    command_id: str
    target_village_id: int
    target_name: str
    target_coords: str
    origin_village_id: int
    origin_name: str
    origin_coords: str
    attacker_name: str
    attacker_id: int
    distance: float
    arrival_time_str: str
    arrival_timestamp: float
    time_remaining_seconds: float
    slowest_unit: str = "unknown"
    slowest_unit_name: str = "Desconhecido ❓"
    is_threat: bool = False  # True para Nobre ou Aríete/Catapulta
    first_seen_timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DodgeOperation:
    """Registo de um comando de Auto-Dodge ativo ou concluído."""
    incoming_command_id: str
    village_id: int
    escape_coords: str
    dodge_command_id: Optional[str] = None
    impact_timestamp: float = 0.0
    dispatched_at: float = 0.0
    cancel_at: float = 0.0
    cancelled: bool = False
    status: str = "pending"  # "pending", "dispatched", "cancelled", "failed"
    units: Dict[str, int] = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DefenseManager:
    """
    Gestor de Defesa, Alerta de Incomings e Esquiva Automática (Auto-Dodge).
    Opera com prioridade máxima TaskPriority.ALERT (0) para resposta instantânea.
    """

    def __init__(
        self,
        place_manager: Optional[PlaceManager] = None,
        map_manager: Optional[Any] = None,
    ):
        self.place_manager = place_manager or PlaceManager()
        self.map_manager = map_manager
        self.active_incomings: Dict[str, IncomingAttack] = {}
        self.active_dodges: Dict[str, DodgeOperation] = {}
        self.last_check_timestamp: float = 0.0
        self.last_incomings_count: int = 0
        self._on_incoming_alert: Optional[Callable[[List[IncomingAttack]], Coroutine]] = None
        self._on_incomings_cleared: Optional[Callable[[], Coroutine]] = None
        self._on_dodge_executed: Optional[Callable[[DodgeOperation], Coroutine]] = None
        self._on_dodge_cancelled: Optional[Callable[[DodgeOperation], Coroutine]] = None

    def on_incoming_alert(self, callback: Callable[[List[IncomingAttack]], Coroutine]) -> None:
        self._on_incoming_alert = callback

    def on_incomings_cleared(self, callback: Callable[[], Coroutine]) -> None:
        self._on_incomings_cleared = callback

    def on_dodge_executed(self, callback: Callable[[DodgeOperation], Coroutine]) -> None:
        self._on_dodge_executed = callback

    def on_dodge_cancelled(self, callback: Callable[[DodgeOperation], Coroutine]) -> None:
        self._on_dodge_cancelled = callback

    @staticmethod
    def calculate_distance(coords1: str, coords2: str) -> float:
        """Calcula a distância euclidiana exata entre duas aldeias (xxx|yyy)."""
        m1 = re.search(r'(\d{1,3})\|(\d{1,3})', str(coords1))
        m2 = re.search(r'(\d{1,3})\|(\d{1,3})', str(coords2))
        if not m1 or not m2:
            return 0.0
        x1, y1 = int(m1.group(1)), int(m1.group(2))
        x2, y2 = int(m2.group(1)), int(m2.group(2))
        return round(math.hypot(x2 - x1, y2 - y1), 2)

    @staticmethod
    def estimate_slowest_unit(
        distance: float,
        time_remaining_seconds: float,
        known_duration_seconds: Optional[float] = None,
    ) -> Tuple[str, str, bool]:
        """
        Calcula a unidade mais lenta do ataque baseando-se na distância euclidiana e tempo.
        Retorna (unidade_chave, nome_pt, is_threat).
        """
        if distance <= 0.0 or (time_remaining_seconds <= 0 and not known_duration_seconds):
            return "unknown", UNIT_NAMES_PT["unknown"], False

        # 1. Se a duração total for conhecida diretamente
        if known_duration_seconds and known_duration_seconds > 0:
            best_unit = "spy"
            min_diff = float("inf")
            for unit, speed in UNIT_SPEED_SECONDS.items():
                expected_dur = distance * speed
                diff = abs(expected_dur - known_duration_seconds)
                if diff < min_diff:
                    min_diff = diff
                    best_unit = unit
            is_threat = best_unit in ("snob", "ram", "catapult")
            return best_unit, UNIT_NAMES_PT.get(best_unit, best_unit), is_threat

        # 2. Estimativa por tempo restante:
        # Qualquer unidade cujo tempo total de viagem seja estritamente menor que o tempo restante
        # é impossível (já teria chegado).
        speed_order = [
            ("snob", 35 * 60),
            ("ram", 30 * 60),
            ("sword", 22 * 60),
            ("axe", 18 * 60),
            ("heavy", 11 * 60),
            ("light", 10 * 60),
            ("spy", 9 * 60),
        ]

        candidates = []
        for unit, speed in speed_order:
            total_dur = distance * speed
            if total_dur >= time_remaining_seconds:
                candidates.append((unit, total_dur))

        if not candidates:
            best_unit = "snob"
        else:
            best_unit = candidates[-1][0]
            # Se o tempo restante for superior à marcha de espadachim, só pode ser aríete ou nobre
            if time_remaining_seconds > (distance * 22 * 60):
                best_unit = "snob" if time_remaining_seconds > (distance * 30 * 60) else "ram"

        is_threat = best_unit in ("snob", "ram", "catapult")
        return best_unit, UNIT_NAMES_PT.get(best_unit, best_unit), is_threat

    async def check_incomings(
        self,
        account: TribalAccount,
        village_id: Optional[int] = None,
    ) -> List[IncomingAttack]:
        """
        Executa a verificação em tempo real de ataques a chegar à conta.
        Extrai contagem e detalhes de cada comando e atualiza a lista de ameaças ativas.
        """
        v_id = village_id or account.current_village_id
        logger.debug(f"[{account.world}] A verificar ataques recebidos (incomings)...")

        html = ""
        try:
            html = await account.get_screen(
                screen="overview_villages&mode=incomings",
                village_id=v_id,
                apply_jitter=False,
            )
        except Exception as e:
            logger.debug(f"[{account.world}] overview_villages&mode=incomings indisponível, a tentar place: {e}")
            try:
                html = await account.get_screen(
                    screen="place",
                    village_id=v_id,
                    apply_jitter=False,
                )
            except Exception as e2:
                logger.error(f"[{account.world}] Falha ao ler tela de incomings: {e2}")
                return list(self.active_incomings.values())

        acc_gd = getattr(account, "last_game_data", None) or getattr(account, "game_data", None)
        total_count = parse_incomings_count(html, acc_gd)
        parsed_list = parse_incomings_overview(html)
        current_time = time.time()
        new_incomings: Dict[str, IncomingAttack] = {}

        for item in parsed_list:
            if item.get("type") != "attack":
                continue

            cmd_id = item.get("command_id") or f"inc_{len(new_incomings)}"
            target_v_id = item.get("target_village_id") or v_id
            target_coords = item.get("target_coords") or ""
            target_name = item.get("target_name") or f"Aldeia {target_v_id}"
            origin_coords = item.get("origin_coords") or ""
            origin_name = item.get("origin_name") or "Inimigo"
            attacker_name = item.get("attacker_name") or "Desconhecido"
            attacker_id = item.get("attacker_id") or 0
            time_rem = float(item.get("time_remaining_seconds") or 0.0)

            if not target_coords and hasattr(account, "village_coords"):
                target_coords = account.village_coords.get(target_v_id, "")

            dist = self.calculate_distance(origin_coords, target_coords)
            slow_unit, slow_unit_pt, is_threat = self.estimate_slowest_unit(
                distance=dist,
                time_remaining_seconds=time_rem,
            )

            arrival_ts = current_time + time_rem

            attack = IncomingAttack(
                command_id=cmd_id,
                target_village_id=target_v_id,
                target_name=target_name,
                target_coords=target_coords,
                origin_village_id=item.get("origin_village_id") or 0,
                origin_name=origin_name,
                origin_coords=origin_coords,
                attacker_name=attacker_name,
                attacker_id=attacker_id,
                distance=dist,
                arrival_time_str=item.get("arrival_time_str") or "",
                arrival_timestamp=arrival_ts,
                time_remaining_seconds=time_rem,
                slowest_unit=slow_unit,
                slowest_unit_name=slow_unit_pt,
                is_threat=is_threat,
                first_seen_timestamp=current_time,
            )
            new_incomings[cmd_id] = attack

        # Validação de segurança anti-falso-positivo: se total_count for igual ao ID da aldeia ou >= 500 sem ataques detalhados
        if total_count == v_id or (total_count >= 500 and not new_incomings):
            logger.debug(f"[{account.world}] Falso positivo detetado em parse_incomings_count ({total_count} igual a village_id ou >= 500).")
            total_count = len(new_incomings)

        if total_count > 0 and not new_incomings:
            synthetic_id = f"alert_incomings_{int(current_time)}"
            new_incomings[synthetic_id] = IncomingAttack(
                command_id=synthetic_id,
                target_village_id=v_id,
                target_name=f"Aldeia {v_id}",
                target_coords="",
                origin_village_id=0,
                origin_name="Ataque Não Mapeado",
                origin_coords="",
                attacker_name="Inimigo",
                attacker_id=0,
                distance=0.0,
                arrival_time_str="A chegar",
                arrival_timestamp=current_time + 60.0,
                time_remaining_seconds=60.0,
                slowest_unit="unknown",
                slowest_unit_name="Ataque Detectado!",
                is_threat=True,
            )

        had_incomings = len(self.active_incomings) > 0 or self.last_incomings_count > 0
        has_incomings = len(new_incomings) > 0 or total_count > 0

        self.active_incomings = new_incomings
        self.last_incomings_count = max(total_count, len(new_incomings))
        self.last_check_timestamp = current_time

        if has_incomings:
            logger.warning(
                f"[{account.world}] 🚨 [ALERTA DE ATAQUE] {self.last_incomings_count} ataque(s) a caminho!"
            )
            if self._on_incoming_alert:
                try:
                    await self._on_incoming_alert(list(new_incomings.values()))
                except Exception as ex:
                    logger.error(f"Erro ao disparar callback de alerta: {ex}")
        elif had_incomings and not has_incomings:
            logger.info(f"[{account.world}] 🛡️ Todos os ataques foram concluídos ou cancelados. Aldeias seguras!")
            if self._on_incomings_cleared:
                try:
                    await self._on_incomings_cleared()
                except Exception as ex:
                    logger.error(f"Erro ao disparar callback de aldeias seguras: {ex}")

        return list(self.active_incomings.values())

    async def find_escape_village(
        self,
        account: TribalAccount,
        village_id: int,
        preferred_coords: Optional[str] = None,
    ) -> Tuple[int, int]:
        """
        Localiza coordenadas seguras para onde desviar as tropas (Auto-Dodge).
        Se preferred_coords for fornecido, utiliza-as; caso contrário, busca a bárbara mais próxima.
        """
        if preferred_coords and "|" in preferred_coords:
            p = preferred_coords.split("|")
            return int(p[0]), int(p[1])

        origin_x, origin_y = 500, 500
        if hasattr(account, "village_coords") and village_id in account.village_coords:
            c = account.village_coords[village_id].split("|")
            origin_x, origin_y = int(c[0]), int(c[1])

        if self.map_manager and hasattr(self.map_manager, "get_cached_barbarians"):
            try:
                barbs = self.map_manager.get_cached_barbarians(account.world)
                if barbs:
                    best_b = None
                    min_d = float("inf")
                    for b in barbs:
                        bx, by = b.get("x", 0), b.get("y", 0)
                        d = math.hypot(bx - origin_x, by - origin_y)
                        if 1.0 <= d < min_d:
                            min_d = d
                            best_b = (bx, by)
                    if best_b:
                        return best_b
            except Exception as e:
                logger.debug(f"Aviso ao consultar bárbaras em cache: {e}")

        return origin_x + 2, origin_y + 2

    async def execute_dodge(
        self,
        account: TribalAccount,
        incoming: IncomingAttack,
        config: Any,
        scheduler: Optional[TaskScheduler] = None,
        village_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Executa a manobra de Auto-Dodge para um ataque a chegar:
        1. Despacha tropas para coordenadas de escape.
        2. Regista o ID do comando gerado.
        3. Agenda o cancelamento pós-impacto (T_impacto + cancel_delay) com TaskPriority.ALERT = 0.
        """
        v_id = village_id or incoming.target_village_id or account.current_village_id
        pref_coords = getattr(config, "escape_coords", None)
        target_coords = await self.find_escape_village(account, v_id, pref_coords)

        offensive_only = not getattr(config, "auto_dodge_all_units", True)
        logger.info(
            f"[{account.world}] 🛡️ [EXECUTANDO AUTO-DODGE] "
            f"Aldeia {v_id} | Alvo de Fuga: ({target_coords[0]}|{target_coords[1]}) | "
            f"Ataque inimigo ID: {incoming.command_id}"
        )

        res = await self.place_manager.send_dodge_command(
            account=account,
            target_coords=target_coords,
            village_id=v_id,
            offensive_only=offensive_only,
        )

        if not res.get("success"):
            logger.error(f"[{account.world}] Falha ao enviar tropas em Auto-Dodge: {res.get('message')}")
            return res

        dodge_cmd_id = res.get("command_id") or f"dodge_{int(time.time())}"
        cancel_delay = getattr(config, "dodge_cancel_delay_seconds", 5)
        impact_ts = incoming.arrival_timestamp
        cancel_ts = max(time.time() + 5.0, impact_ts + cancel_delay)

        op = DodgeOperation(
            incoming_command_id=incoming.command_id,
            village_id=v_id,
            escape_coords=f"{target_coords[0]}|{target_coords[1]}",
            dodge_command_id=dodge_cmd_id,
            impact_timestamp=impact_ts,
            dispatched_at=time.time(),
            cancel_at=cancel_ts,
            status="dispatched",
            units=res.get("units", {}),
            message=f"Tropas desviadas para ({target_coords[0]}|{target_coords[1]}). Cancelamento agendado.",
        )
        self.active_dodges[dodge_cmd_id] = op

        # Agenda o cancelamento milimétrico pós-impacto no TaskScheduler
        if scheduler:
            delay_sec = max(0.5, cancel_ts - time.time())
            logger.info(
                f"[{account.world}] ⏰ [CANCELAMENTO AGENDADO] Comando {dodge_cmd_id} "
                f"será cancelado em {delay_sec:.1f}s (Prioridade ALERT = 0)."
            )
            scheduler.schedule(
                name=f"Cancel_Dodge_{dodge_cmd_id}",
                priority=TaskPriority.ALERT,  # Prioridade 0 Máxima
                action=self.cancel_dodge,
                account=account,
                dodge_command_id=dodge_cmd_id,
                village_id=v_id,
                delay_seconds=delay_sec,
                task_id=f"cancel_dodge_{dodge_cmd_id}",
            )

        if self._on_dodge_executed:
            try:
                await self._on_dodge_executed(op)
            except Exception as ex:
                logger.error(f"Erro em callback on_dodge_executed: {ex}")

        return {
            "status": "success",
            "message": f"Dodge despachado com sucesso. Comando: {dodge_cmd_id}",
            "dodge": op.to_dict(),
        }

    async def cancel_dodge(
        self,
        account: TribalAccount,
        dodge_command_id: str,
        village_id: Optional[int] = None,
    ) -> bool:
        """
        Executa o cancelamento da manobra de esquiva após o ataque inimigo ter impactado.
        As tropas voltam para a aldeia em total segurança.
        """
        v_id = village_id or account.current_village_id
        cmd_id = str(dodge_command_id)
        logger.info(f"[{account.world}] 🔙 [A CANCELAR AUTO-DODGE] Comando {cmd_id} na aldeia {v_id}...")

        ok = await self.place_manager.cancel_command(account, cmd_id, village_id=v_id)

        if cmd_id in self.active_dodges:
            op = self.active_dodges[cmd_id]
            op.cancelled = ok
            op.status = "cancelled" if ok else "cancel_failed"
            if ok:
                op.message = "Comando cancelado com sucesso. Tropas em regresso seguro!"
            if self._on_dodge_cancelled:
                try:
                    await self._on_dodge_cancelled(op)
                except Exception as ex:
                    logger.error(f"Erro em callback on_dodge_cancelled: {ex}")

        return ok

    def schedule_defense_monitor(
        self,
        scheduler: TaskScheduler,
        account: TribalAccount,
        config: Any,
        interval_seconds: Optional[float] = None,
    ) -> Optional[Task]:
        """
        Agenda o ciclo periódico de verificação de ataques a chegar com prioridade TaskPriority.ALERT (0).
        """
        if not getattr(config, "enabled", True):
            return None

        inv = interval_seconds or getattr(config, "check_interval_seconds", 20.0)

        async def _defense_tick():
            try:
                incomings = await self.check_incomings(account)

                # Se Auto-Dodge estiver ligado, planeia o envio
                auto_dodge = getattr(config, "auto_dodge_enabled", False)
                if auto_dodge and incomings:
                    lead_time = getattr(config, "dodge_lead_time_seconds", 30)
                    now = time.time()

                    for inc in incomings:
                        already_dodged = any(
                            d.incoming_command_id == inc.command_id and d.status in ("pending", "dispatched")
                            for d in self.active_dodges.values()
                        )
                        if already_dodged:
                            continue

                        sec_to_impact = inc.arrival_timestamp - now
                        if sec_to_impact <= (lead_time + 5):
                            logger.warning(
                                f"[{account.world}] ⚡ [DISPARANDO AUTO-DODGE] Ataque {inc.command_id} "
                                f"impacta em {sec_to_impact:.1f}s (Limiar: {lead_time}s)!"
                            )
                            await self.execute_dodge(
                                account=account,
                                incoming=inc,
                                config=config,
                                scheduler=scheduler,
                            )
                        elif sec_to_impact > lead_time:
                            delay_to_dodge = max(0.5, sec_to_impact - lead_time)
                            task_id = f"auto_dodge_dispatch_{inc.command_id}"
                            logger.info(
                                f"[{account.world}] 🛡️ [AUTO-DODGE PRÉ-AGENDADO] "
                                f"Ataque {inc.command_id} - Envio de esquiva em {delay_to_dodge:.1f}s."
                            )
                            scheduler.schedule(
                                name=f"AutoDodge_{inc.command_id}",
                                priority=TaskPriority.ALERT,
                                action=self.execute_dodge,
                                account=account,
                                incoming=inc,
                                config=config,
                                scheduler=scheduler,
                                delay_seconds=delay_to_dodge,
                                task_id=task_id,
                            )
            except Exception as e:
                logger.error(f"[{account.world}] Erro no ciclo de monitorização de defesa: {e}")
            finally:
                if scheduler and getattr(config, "enabled", True):
                    next_inv = getattr(config, "check_interval_seconds", inv) or inv
                    self.schedule_defense_monitor(
                        scheduler=scheduler,
                        account=account,
                        config=config,
                        interval_seconds=next_inv,
                    )

        return scheduler.schedule(
            name="Defense_Monitor_Tick",
            priority=TaskPriority.ALERT,
            action=_defense_tick,
            delay_seconds=inv,
            task_id="defense_monitor_tick",
        )
