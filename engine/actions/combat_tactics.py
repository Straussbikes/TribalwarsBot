"""
Tribal Wars Mobile Automation Engine - CombatManager (screen=place)
Motor tático de combate de precisão milimétrica:
- Comboio de Nobres Automatizado (Noble Train com gaps controlados de 50ms a 150ms).
- Mecanismo Fail-Safe com cancelamento de emergência pós-disparo.
- Calculadora e Agendador de Backtime.
- Sniper de Nobres Anti-Conquista (Support Snipe e Return Snipe).
- Fake Trains coordenados.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import math
import re
import time
from typing import Any, Dict, List, Optional

from engine.actions.combat_sync import ClockSynchronizer
from engine.actions.place import (
    PlaceManager,
    UNIT_SPEED_MIN_PER_FIELD,
    UnitType,
    UnitsCount,
)
from engine.core.account import TribalAccount
from engine.utils.parsers import parse_command_confirmation

logger = logging.getLogger(__name__)


class TacticalOperationType(str, Enum):
    NOBLE_TRAIN = "noble_train"
    BACKTIME = "backtime"
    SNIPE_SUPPORT = "snipe_support"
    SNIPE_RETURN = "snipe_return"
    FAKE_TRAIN = "fake_train"


class TacticalOperationStatus(str, Enum):
    SCHEDULED = "scheduled"
    PREPARING = "preparing"
    EXECUTING = "executing"
    COMPLETED = "completed"
    CANCELLED_FAILSAFE = "cancelled_failsafe"
    CANCELLED_MANUAL = "cancelled_manual"
    FAILED = "failed"


@dataclass
class SubCommandResult:
    """Resultado individual de um dos ataques de uma operação composta (ex.: comboio)."""
    attack_index: int
    command_id: Optional[str] = None
    target_time: float = 0.0
    launched_at: float = 0.0
    drift_ms: float = 0.0
    success: bool = False
    is_cancelled: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attack_index": self.attack_index,
            "command_id": self.command_id,
            "target_time": self.target_time,
            "launched_at": self.launched_at,
            "drift_ms": round(self.drift_ms, 2),
            "success": self.success,
            "is_cancelled": self.is_cancelled,
            "error": self.error,
        }


@dataclass
class TacticalOperation:
    """Registo persistente de uma manobra tática de combate agendada ou executada."""
    operation_id: str
    operation_type: TacticalOperationType
    village_id: int
    target_coords: str
    scheduled_launch_time: float
    status: TacticalOperationStatus = TacticalOperationStatus.SCHEDULED
    sub_commands: List[SubCommandResult] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type.value,
            "village_id": self.village_id,
            "target_coords": self.target_coords,
            "scheduled_launch_time": self.scheduled_launch_time,
            "status": self.status.value,
            "sub_commands": [cmd.to_dict() for cmd in self.sub_commands],
            "details": self.details,
            "created_at": self.created_at,
        }


@dataclass
class NobleTrainPlan:
    """Plano de execução de um Comboio de Nobres (Noble Train)."""
    target_coords: str
    train_size: int = 4
    nuke_units: UnitsCount = field(default_factory=UnitsCount)
    escort_units: UnitsCount = field(default_factory=lambda: UnitsCount(axe=50, light=20))
    gap_ms: int = 100
    launch_at_server_ts: Optional[float] = None
    target_arrival_server_ts: Optional[float] = None
    failsafe_enabled: bool = True
    failsafe_max_spread_ms: int = 400


@dataclass
class BacktimePlan:
    """Plano de cálculo e disparo de contra-ataque de Backtime."""
    target_coords: str
    enemy_return_server_ts: float
    units: UnitsCount
    village_id: Optional[int] = None
    slowest_unit: str = UnitType.LIGHT


@dataclass
class SnipePlan:
    """Plano de intercalação defensiva contra comboio de nobres inimigo."""
    incoming_id: str
    target_village_coords: str
    target_noble_arrival_ts: float
    window_start_ts: float
    window_end_ts: float
    snipe_type: str  # "support" ou "cancel_return"
    source_village_id: int
    units: UnitsCount


def calculate_euclidean_distance(coords_a: str, coords_b: str) -> float:
    """Calcula a distância euclidiana em campos entre duas aldeias (xxx|yyy)."""
    try:
        ax_s, ay_s = coords_a.replace("(", "").replace(")", "").split("|", 1)
        bx_s, by_s = coords_b.replace("(", "").replace(")", "").split("|", 1)
        ax, ay = int(ax_s), int(ay_s)
        bx, by = int(bx_s), int(by_s)
        return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)
    except Exception:
        return 0.0


def calculate_travel_duration(
    origin_coords: str,
    target_coords: str,
    slowest_unit: str,
    world_speed: float = 1.0,
    unit_speed: float = 1.0,
) -> float:
    """Calcula a duração da marcha em segundos de acordo com a unidade mais lenta."""
    dist = calculate_euclidean_distance(origin_coords, target_coords)
    base_min_per_field = UNIT_SPEED_MIN_PER_FIELD.get(slowest_unit, 18.0)
    effective_seconds_per_field = (base_min_per_field * 60.0) / (world_speed * unit_speed)
    return dist * effective_seconds_per_field


class CombatManager:
    """
    Gestor militar de operações táticas e sincronização ao milissegundo.
    Coordena Noble Trains, Backtimes e Snipes com fail-safe e compensação RTT.
    """

    def __init__(
        self,
        place_manager: Optional[PlaceManager] = None,
        clock_sync: Optional[ClockSynchronizer] = None,
    ):
        self.place: PlaceManager = place_manager or PlaceManager()
        self.clock: ClockSynchronizer = clock_sync or ClockSynchronizer()
        self.operations: Dict[str, TacticalOperation] = {}
        self._op_counter: int = 0

    def generate_operation_id(self, prefix: str = "tactical") -> str:
        self._op_counter += 1
        return f"{prefix}_{int(time.time())}_{self._op_counter}"

    async def execute_noble_train(
        self,
        account: TribalAccount,
        plan: NobleTrainPlan,
        village_id: Optional[int] = None,
    ) -> TacticalOperation:
        """
        Executa um Comboio de Nobres (Noble Train) sequencial com espaçamento milimétrico.
        Possui Fail-Safe automático: se o spread exceder o limite, cancela todos os ataques.
        """
        v_id = village_id or account.current_village_id
        op_id = self.generate_operation_id("train")
        tx_s, ty_s = plan.target_coords.split("|", 1)
        target_x, target_y = int(tx_s), int(ty_s)

        # Determina a aldeia de origem para cálculo de distância
        v_obj = account.villages.get(v_id)
        origin_coords = f"{v_obj.x}|{v_obj.y}" if v_obj else "500|500"

        operation = TacticalOperation(
            operation_id=op_id,
            operation_type=TacticalOperationType.NOBLE_TRAIN,
            village_id=v_id,
            target_coords=plan.target_coords,
            scheduled_launch_time=time.time(),
            status=TacticalOperationStatus.PREPARING,
            details={
                "train_size": plan.train_size,
                "gap_ms": plan.gap_ms,
                "failsafe_enabled": plan.failsafe_enabled,
                "failsafe_max_spread_ms": plan.failsafe_max_spread_ms,
            },
        )
        self.operations[op_id] = operation

        logger.info(
            f"[{account.world}] 🚀 A iniciar Noble Train {op_id}: {plan.train_size} ataques "
            f"para ({plan.target_coords}) com gap de {plan.gap_ms}ms..."
        )

        # 1. Preparação Sequencial na Praça de Reunião (Etapa 1 de cada ataque)
        prepared_attacks: List[Dict[str, Any]] = []

        for i in range(plan.train_size):
            if i == 0:
                # 1º Ataque: Nuke + 1 Nobre
                units_dict = plan.nuke_units.to_dict()
                units_dict["snob"] = 1
            else:
                # Ataques 2 a N: Escolta + 1 Nobre
                units_dict = plan.escort_units.to_dict()
                units_dict["snob"] = 1

            send_units = UnitsCount.from_dict(units_dict)
            prep = await self.place.prepare_command(
                account=account,
                target_x=target_x,
                target_y=target_y,
                units=send_units,
                is_attack=True,
                village_id=v_id,
            )

            if not prep.get("success"):
                err_msg = prep.get("error_message") or "Falha na preparação do formulário de confirmação."
                logger.error(f"[{account.world}] Erro na preparação do ataque #{i+1} do comboio: {err_msg}")
                operation.status = TacticalOperationStatus.FAILED
                operation.details["failure_reason"] = f"Ataque #{i+1}: {err_msg}"
                return operation

            prepared_attacks.append(prep)

        # 2. Cálculo do Instante de Lançamento Inicial
        travel_sec = calculate_travel_duration(origin_coords, plan.target_coords, UnitType.SNOB)

        if plan.launch_at_server_ts:
            base_launch_local = self.clock.server_to_local_time(plan.launch_at_server_ts)
        elif plan.target_arrival_server_ts:
            base_launch_local = self.clock.calculate_launch_time(plan.target_arrival_server_ts, travel_sec)
        else:
            base_launch_local = time.time() + 0.1  # Disparo imediato em 100ms

        operation.status = TacticalOperationStatus.EXECUTING
        operation.scheduled_launch_time = base_launch_local

        # 3. Disparo Milimétrico dos Ataques do Comboio
        results: List[SubCommandResult] = []
        launched_cmd_ids: List[str] = []

        for i, prep_data in enumerate(prepared_attacks):
            target_launch_i = base_launch_local + (i * (plan.gap_ms / 1000.0))
            drift_sec = await self.clock.spin_wait_until(target_launch_i)
            t_sent = time.time()

            # Disparo da confirmação sem jitters adicionais
            hidden_fields = prep_data.get("hidden_fields", {})
            try:
                html = await account.post_action(
                    screen="place",
                    action="command",
                    data=hidden_fields,
                    village_id=v_id,
                    apply_jitter=False,
                )
                # No envio final (action=command), a página de sucesso é a praça ou confirmação.
                # Só é erro se houver uma mensagem de erro explícita no HTML (error_box ou similar).
                err = parse_command_confirmation(html)
                is_ok = True
                err_msg = None
                if not err["success"] and err["error_message"] and "Formulário de confirmação" not in err["error_message"]:
                    is_ok = False
                    err_msg = err["error_message"]

                cmd_id = None
                if is_ok:
                    cmd_match = re.search(r'info_command&id=(\d+)', html) or re.search(r'command_id["\']?>(\d+)', html)
                    cmd_id = cmd_match.group(1) if cmd_match else f"cmd_train_{i+1}_{int(t_sent*1000)}"
                    launched_cmd_ids.append(cmd_id)

                sub_res = SubCommandResult(
                    attack_index=i + 1,
                    command_id=cmd_id,
                    target_time=target_launch_i,
                    launched_at=t_sent,
                    drift_ms=drift_sec * 1000.0,
                    success=is_ok,
                    error=err_msg,
                )
                results.append(sub_res)
                logger.info(
                    f"[{account.world}] ⚔️ Nobre #{i+1} disparado! ID: {cmd_id} | "
                    f"Drift: {sub_res.drift_ms:+.1f}ms | Sucesso: {is_ok}"
                )
            except Exception as e:
                logger.error(f"[{account.world}] Exceção ao despachar ataque #{i+1} do comboio: {e}")
                results.append(SubCommandResult(
                    attack_index=i + 1,
                    target_time=target_launch_i,
                    launched_at=t_sent,
                    drift_ms=drift_sec * 1000.0,
                    success=False,
                    error=str(e),
                ))

        operation.sub_commands = results

        # 4. Avaliação de Fail-Safe (Dispersão Excessiva ou Falha de Lançamento)
        first_launch = results[0].launched_at if results else 0.0
        last_launch = results[-1].launched_at if results else 0.0
        actual_spread_ms = (last_launch - first_launch) * 1000.0
        operation.details["actual_spread_ms"] = round(actual_spread_ms, 2)

        has_failures = any(not r.success for r in results)
        spread_exceeded = plan.failsafe_enabled and actual_spread_ms > plan.failsafe_max_spread_ms

        if has_failures or spread_exceeded:
            reason = "Falha num dos ataques" if has_failures else f"Spread excessivo ({actual_spread_ms:.0f}ms > {plan.failsafe_max_spread_ms}ms)"
            logger.critical(
                f"[{account.world}] 🚨 FAIL-SAFE ACIONADO no Noble Train {op_id}! Motivo: {reason}. "
                f"A cancelar todos os comandos para resgatar os Nobres!"
            )
            # Cancela de emergência todos os comandos que chegaram a sair
            for r in results:
                if r.command_id and not r.is_cancelled:
                    try:
                        await self.place.cancel_command(account, r.command_id, village_id=v_id)
                        r.is_cancelled = True
                    except Exception as ce:
                        logger.error(f"Erro ao cancelar comando {r.command_id} no fail-safe: {ce}")

            operation.status = TacticalOperationStatus.CANCELLED_FAILSAFE
            operation.details["failsafe_triggered"] = True
            operation.details["failsafe_reason"] = reason
        else:
            operation.status = TacticalOperationStatus.COMPLETED
            logger.info(
                f"[{account.world}] ✅ Noble Train {op_id} concluído com sucesso perfeito! "
                f"Spread total: {actual_spread_ms:.1f}ms (Gaps médios: {actual_spread_ms / max(1, plan.train_size - 1):.1f}ms)."
            )

        return operation

    def calculate_backtime(
        self,
        origin_coords: str,
        target_coords: str,
        enemy_return_server_ts: float,
        slowest_unit: str = UnitType.LIGHT,
        world_speed: float = 1.0,
        unit_speed: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Calcula o plano de contra-ataque de Backtime.
        Determina o momento exato de partida para que as nossas tropas aterrem no instante
        em que o exército inimigo regressa à base dele.
        """
        dist = calculate_euclidean_distance(origin_coords, target_coords)
        travel_sec = calculate_travel_duration(
            origin_coords, target_coords, slowest_unit, world_speed, unit_speed
        )
        departure_server_ts = enemy_return_server_ts - travel_sec
        launch_local_ts = self.clock.calculate_launch_time(enemy_return_server_ts, travel_sec)

        now_server = self.clock.get_server_time()
        time_until_launch = departure_server_ts - now_server

        return {
            "origin_coords": origin_coords,
            "target_coords": target_coords,
            "distance_fields": round(dist, 2),
            "slowest_unit": slowest_unit,
            "travel_duration_seconds": round(travel_sec, 2),
            "enemy_return_server_ts": enemy_return_server_ts,
            "departure_server_ts": round(departure_server_ts, 3),
            "launch_local_ts": round(launch_local_ts, 3),
            "time_until_launch_seconds": round(time_until_launch, 2),
            "is_feasible": time_until_launch > 5.0,  # Viável se faltarem mais de 5s para o envio
        }

    async def schedule_backtime(
        self,
        account: TribalAccount,
        plan: BacktimePlan,
        village_id: Optional[int] = None,
    ) -> TacticalOperation:
        """Agenda uma operação de Backtime com disparo no milissegundo exato."""
        v_id = village_id or account.current_village_id
        v_obj = account.villages.get(v_id)
        origin_coords = f"{v_obj.x}|{v_obj.y}" if v_obj else "500|500"

        calc = self.calculate_backtime(
            origin_coords=origin_coords,
            target_coords=plan.target_coords,
            enemy_return_server_ts=plan.enemy_return_server_ts,
            slowest_unit=plan.slowest_unit,
        )

        if not calc["is_feasible"]:
            raise ValueError(
                f"Backtime inviável: tempo até ao lançamento insuficiente ({calc['time_until_launch_seconds']:.1f}s)."
            )

        op_id = self.generate_operation_id("backtime")
        operation = TacticalOperation(
            operation_id=op_id,
            operation_type=TacticalOperationType.BACKTIME,
            village_id=v_id,
            target_coords=plan.target_coords,
            scheduled_launch_time=calc["launch_local_ts"],
            status=TacticalOperationStatus.SCHEDULED,
            details=calc,
        )
        self.operations[op_id] = operation
        logger.info(
            f"[{account.world}] ⏱️ Backtime agendado {op_id}: envio em {calc['time_until_launch_seconds']:.1f}s "
            f"para aterrar em {plan.enemy_return_server_ts:.0f}."
        )
        return operation

    def analyze_snipes(
        self,
        incomings: List[Dict[str, Any]],
        own_villages: List[Dict[str, Any]],
        world_speed: float = 1.0,
        unit_speed: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        Analisa os ataques recebidos (incomings) para detectar comboios de nobres e identificar
        janelas de intercalação (sniping). Sugere tanto Support Snipe (aldeias vizinhas)
        como Return Snipe (cancelamento de comando na própria aldeia).
        """
        # Agrupa ataques por aldeia de destino
        grouped_by_target: Dict[str, List[Dict[str, Any]]] = {}
        for inc in incomings:
            tgt = inc.get("target_coords") or ""
            if tgt:
                grouped_by_target.setdefault(tgt, []).append(inc)

        suggestions: List[Dict[str, Any]] = []

        for target_coords, attacks in grouped_by_target.items():
            if len(attacks) < 2:
                continue

            # Ordena por hora de chegada
            attacks_sorted = sorted(attacks, key=lambda a: a.get("arrival_timestamp", 0))

            # Procura ataques consecutivos separados por menos de 3 segundos com velocidade de nobre
            for i in range(len(attacks_sorted) - 1):
                atk_lead = attacks_sorted[i]
                atk_follow = attacks_sorted[i + 1]

                t_lead = atk_lead.get("arrival_timestamp", 0)
                t_follow = atk_follow.get("arrival_timestamp", 0)
                gap_sec = t_follow - t_lead

                if 0.05 <= gap_sec <= 3.0:
                    # Encontrada janela entre o ataque de limpeza (ou nobre anterior) e o próximo nobre
                    window_start = t_lead
                    window_end = t_follow
                    target_land_ts = (window_start + window_end) / 2.0

                    # 1. Sugestões de Support Snipe a partir de aldeias vizinhas
                    for v in own_villages:
                        v_coords = f"{v.get('x')}|{v.get('y')}"
                        v_id = v.get("id")
                        if v_coords == target_coords:
                            continue  # Aldeia alvo tratada em Return Snipe

                        for def_unit in [UnitType.SWORD, UnitType.SPEAR, UnitType.HEAVY]:
                            travel_sec = calculate_travel_duration(
                                v_coords, target_coords, def_unit, world_speed, unit_speed
                            )
                            dep_server = target_land_ts - travel_sec
                            time_left = dep_server - self.clock.get_server_time()

                            if time_left > 10.0:  # Viável se houver tempo para disparar
                                suggestions.append({
                                    "snipe_type": "support",
                                    "target_coords": target_coords,
                                    "target_noble_arrival_ts": t_follow,
                                    "window_gap_ms": round(gap_sec * 1000, 1),
                                    "source_village_id": v_id,
                                    "source_village_coords": v_coords,
                                    "slowest_unit": def_unit,
                                    "travel_duration_seconds": round(travel_sec, 2),
                                    "departure_server_ts": round(dep_server, 3),
                                    "time_until_launch_seconds": round(time_left, 1),
                                    "lead_attack_id": atk_lead.get("command_id"),
                                    "noble_attack_id": atk_follow.get("command_id"),
                                })

                    # 2. Sugestão de Return Snipe na própria aldeia (cancelamento milimétrico)
                    now_ts = self.clock.get_server_time()
                    time_until_noble = t_follow - now_ts
                    if time_until_noble > 20.0:
                        suggestions.append({
                            "snipe_type": "cancel_return",
                            "target_coords": target_coords,
                            "target_noble_arrival_ts": t_follow,
                            "window_gap_ms": round(gap_sec * 1000, 1),
                            "source_village_coords": target_coords,
                            "time_until_noble_seconds": round(time_until_noble, 1),
                            "lead_attack_id": atk_lead.get("command_id"),
                            "noble_attack_id": atk_follow.get("command_id"),
                            "explanation": "Desvia tropas agora e cancela exatamente na metade do tempo para regresso antes do nobre!",
                        })

        return suggestions

    def get_operations(self) -> List[Dict[str, Any]]:
        """Retorna todas as operações táticas ativas e recentes."""
        return [op.to_dict() for op in self.operations.values()]
