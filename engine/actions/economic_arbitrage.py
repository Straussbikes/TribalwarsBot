"""
Tribal Wars Mobile Automation Engine - EconomicArbitrageManager (Item 2.12)
Algoritmo de Arbitragem Económica & Orquestração (Construção vs. Recrutamento)
Filosofia 'Fila Sempre Ativa': manter as 4 filas principais (Edifício Principal,
Quartel, Estábulo e Oficina) permanentemente em execução contínua sem tempo ocioso,
com projeção de fluxo de caixa em tempo real e recrutamento dinâmico em micro-lotes.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from engine.actions.main_building import (
    BUILDING_NAMES,
    BuildingType,
    BuildingUpgrade,
    MainBuildingManager,
    MainBuildingState,
    estimate_building_cost,
)
from engine.actions.place import PlaceManager, PlaceState, UnitsCount
from engine.actions.recruitment import (
    BUILDING_UNITS,
    UNIT_TO_BUILDING,
    RecruitmentManager,
    RecruitmentState,
)
from engine.core.account import TribalAccount
from engine.core.models import Resources, TaskPriority
from engine.core.scheduler import TaskScheduler
from engine.utils.timing import get_human_delay

logger = logging.getLogger(__name__)

# Tabela base de produção de recursos por nível de edifício (unidades/hora em velocidade 1)
BASE_PRODUCTION_HOURLY: Dict[int, int] = {
    0: 5,
    1: 30,
    2: 35,
    3: 41,
    4: 47,
    5: 55,
    6: 64,
    7: 74,
    8: 86,
    9: 100,
    10: 117,
    11: 136,
    12: 158,
    13: 184,
    14: 214,
    15: 249,
    16: 289,
    17: 337,
    18: 391,
    19: 455,
    20: 530,
    21: 616,
    22: 717,
    23: 833,
    24: 969,
    25: 1127,
    26: 1311,
    27: 1525,
    28: 1774,
    29: 2063,
    30: 2400,
}

# Custos base das unidades militares para cálculo de micro-lotes
UNIT_COSTS: Dict[str, Dict[str, int]] = {
    "spear": {"wood": 50, "stone": 30, "iron": 10, "pop": 1},
    "sword": {"wood": 30, "stone": 30, "iron": 70, "pop": 1},
    "axe": {"wood": 60, "stone": 30, "iron": 40, "pop": 1},
    "archer": {"wood": 100, "stone": 30, "iron": 60, "pop": 1},
    "spy": {"wood": 50, "stone": 50, "iron": 20, "pop": 2},
    "light": {"wood": 125, "stone": 100, "iron": 250, "pop": 4},
    "marcher": {"wood": 250, "stone": 100, "iron": 150, "pop": 5},
    "heavy": {"wood": 200, "stone": 150, "iron": 600, "pop": 6},
    "ram": {"wood": 300, "stone": 200, "iron": 200, "pop": 5},
    "catapult": {"wood": 320, "stone": 400, "iron": 100, "pop": 8},
}


def parse_timer_to_seconds(timer_str: Optional[str]) -> float:
    """
    Converte strings de temporizador do jogo em segundos decimais.
    Exemplos aceites: '0:15:30' (930s), '1:04:12' (3852s), '45:10' (2710s), '0:45' (45s).
    """
    if not timer_str:
        return 0.0

    cleaned = str(timer_str).strip()
    if not cleaned:
        return 0.0

    parts = cleaned.split(":")
    try:
        if len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
            return float(h * 3600 + m * 60 + s)
        elif len(parts) == 2:
            m, s = int(parts[0]), int(parts[1])
            return float(m * 60 + s)
        elif len(parts) == 1:
            return float(int(parts[0]))
    except (ValueError, TypeError):
        return 0.0

    return 0.0


class ArbitrageActionType(str, Enum):
    """Tipo de decisão gerada pelo motor de arbitragem económica."""
    BUILD = "build"                       # Iniciar construção do próximo edifício do plano
    RECRUIT_NORMAL = "recruit_normal"     # Recrutamento de lote padrão
    RECRUIT_MICRO = "recruit_micro"       # Micro-lote de emergência (manter fila militar sem canibalizar build)
    HOLD_FOR_BUILD = "hold_for_build"     # Retenção estratégica de recursos para construção iminente
    SPEND_SURPLUS = "spend_surplus"       # Excedente: gastar recursos antes que o armazém transborde
    IDLE = "idle"                         # Todas as filas operacionais e sem ações necessárias


@dataclass
class CashFlowProjection:
    """Projeção preditiva de fluxo de caixa da aldeia no tempo."""
    hourly_production: Dict[str, float] = field(default_factory=dict)
    estimated_returning_loot: Dict[str, int] = field(default_factory=dict)
    projected_15m: Dict[str, int] = field(default_factory=dict)
    projected_1h: Dict[str, int] = field(default_factory=dict)
    projected_3h: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hourly_production": self.hourly_production,
            "estimated_returning_loot": self.estimated_returning_loot,
            "projected_15m": self.projected_15m,
            "projected_1h": self.projected_1h,
            "projected_3h": self.projected_3h,
        }


@dataclass
class ArbitrageDecision:
    """Decisão consolidada de arbitragem económica para uma aldeia."""
    village_id: int
    action_type: ArbitrageActionType
    reason: str
    target_building: Optional[BuildingUpgrade] = None
    target_recruitment: Dict[str, int] = field(default_factory=dict)
    building_queue_time_left: float = 0.0
    military_queues_time_left: Dict[str, float] = field(default_factory=dict)
    cash_flow: Optional[CashFlowProjection] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "village_id": self.village_id,
            "action_type": self.action_type.value,
            "reason": self.reason,
            "target_building": {
                "building": self.target_building.building,
                "target_level": self.target_building.target_level,
                "wood": self.target_building.wood,
                "stone": self.target_building.stone,
                "iron": self.target_building.iron,
                "pop": self.target_building.pop,
            } if self.target_building else None,
            "target_recruitment": self.target_recruitment,
            "building_queue_time_left": round(self.building_queue_time_left, 1),
            "military_queues_time_left": {
                k: round(v, 1) for k, v in self.military_queues_time_left.items()
            },
            "cash_flow": self.cash_flow.to_dict() if self.cash_flow else None,
        }


class EconomicArbitrageManager:
    """
    Gestor de Arbitragem Económica e Orquestração Contínua (Fila Sempre Ativa).
    Garante que os recursos da conta são alocados de forma ótima entre
    construção e recrutamento, minimizando tempo de inatividade das filas.
    """

    def __init__(
        self,
        main_building_manager: Optional[MainBuildingManager] = None,
        recruitment_manager: Optional[RecruitmentManager] = None,
        place_manager: Optional[PlaceManager] = None,
    ):
        self.main_building_manager = main_building_manager or MainBuildingManager()
        self.recruitment_manager = recruitment_manager or RecruitmentManager(place_manager=place_manager)
        self.place_manager = place_manager or PlaceManager()

    @staticmethod
    def calculate_hourly_production(
        buildings: Dict[str, int], speed_factor: float = 1.0
    ) -> Dict[str, float]:
        """Calcula a taxa de produção horária estimada de madeira, argila e ferro."""
        w_lvl = buildings.get(BuildingType.WOOD, buildings.get("wood", 0))
        s_lvl = buildings.get(BuildingType.STONE, buildings.get("stone", 0))
        i_lvl = buildings.get(BuildingType.IRON, buildings.get("iron", 0))

        w_prod = BASE_PRODUCTION_HOURLY.get(min(30, max(0, w_lvl)), 30) * speed_factor
        s_prod = BASE_PRODUCTION_HOURLY.get(min(30, max(0, s_lvl)), 30) * speed_factor
        i_prod = BASE_PRODUCTION_HOURLY.get(min(30, max(0, i_lvl)), 30) * speed_factor

        return {
            "wood": round(w_prod, 1),
            "stone": round(s_prod, 1),
            "iron": round(i_prod, 1),
            "total": round(w_prod + s_prod + i_prod, 1),
        }

    @staticmethod
    def project_resources(
        current_resources: Resources,
        hourly_prod: Dict[str, float],
        returning_loot: Dict[str, int],
        seconds_ahead: float,
    ) -> Dict[str, int]:
        """Projeta a quantidade de recursos da aldeia após N segundos."""
        factor = seconds_ahead / 3600.0
        storage_max = current_resources.storage_max or 999999

        p_wood = int(min(storage_max, current_resources.wood + hourly_prod.get("wood", 0.0) * factor + returning_loot.get("wood", 0)))
        p_stone = int(min(storage_max, current_resources.stone + hourly_prod.get("stone", 0.0) * factor + returning_loot.get("stone", 0)))
        p_iron = int(min(storage_max, current_resources.iron + hourly_prod.get("iron", 0.0) * factor + returning_loot.get("iron", 0)))

        return {"wood": p_wood, "stone": p_stone, "iron": p_iron}

    async def get_cash_flow_projection(
        self,
        account: TribalAccount,
        village_id: Optional[int] = None,
        main_state: Optional[MainBuildingState] = None,
        place_state: Optional[PlaceState] = None,
    ) -> CashFlowProjection:
        """Constrói a projeção de fluxo de caixa em tempo real para a aldeia."""
        v_id = village_id or account.current_village_id

        if not main_state:
            main_state = await self.main_building_manager.get_state(account, village_id=v_id)

        if not place_state:
            place_state = await self.place_manager.get_state(account, village_id=v_id)

        hourly_prod = self.calculate_hourly_production(main_state.buildings)

        # Estima recursos em marcha de retorno à aldeia
        returning_cap = sum(
            cmd.timer_str and 100 for cmd in place_state.commands if cmd.movement_type in ("return", "returning")
        )
        loot_split = {
            "wood": int(returning_cap / 3),
            "stone": int(returning_cap / 3),
            "iron": int(returning_cap / 3),
        }

        res = account.resources
        p_15m = self.project_resources(res, hourly_prod, loot_split, 900.0)
        p_1h = self.project_resources(res, hourly_prod, loot_split, 3600.0)
        p_3h = self.project_resources(res, hourly_prod, loot_split, 10800.0)

        return CashFlowProjection(
            hourly_production=hourly_prod,
            estimated_returning_loot=loot_split,
            projected_15m=p_15m,
            projected_1h=p_1h,
            projected_3h=p_3h,
        )

    async def evaluate_village_arbitrage(
        self,
        account: TribalAccount,
        village_id: Optional[int] = None,
        emergency_queue_seconds: float = 900.0,  # 15 minutos
        min_military_batch: int = 2,
    ) -> ArbitrageDecision:
        """
        Avalia o estado global da aldeia e toma a decisão ótima de arbitragem económica
        seguindo a filosofia 'Fila Sempre Ativa'.
        """
        v_id = village_id or account.current_village_id or 0
        cfg = account.config if hasattr(account, "config") and account.config else None

        # 1. Obter estado do Edifício Principal
        main_state = await self.main_building_manager.get_state(account, village_id=v_id)

        # 2. Obter estados dos edifícios militares presentes
        military_states: Dict[str, RecruitmentState] = {}
        military_timers: Dict[str, float] = {}

        for b in ("barracks", "stable", "garage"):
            if main_state.buildings.get(b, 0) > 0:
                m_state = await self.recruitment_manager.get_building_state(account, b, village_id=v_id)
                military_states[b] = m_state
                # Calcula tempo total restante na fila do edifício militar
                total_m_sec = sum(parse_timer_to_seconds(o.timer_str) for o in m_state.queue)
                military_timers[b] = total_m_sec
            else:
                military_timers[b] = 0.0

        # 3. Tempo restante na fila de construção do Edifício Principal
        build_queue_time = sum(parse_timer_to_seconds(o.timer_str) for o in main_state.queue)

        # 4. Projeção de fluxo de caixa
        place_state = await self.place_manager.get_state(account, village_id=v_id)
        cash_flow = await self.get_cash_flow_projection(
            account=account,
            village_id=v_id,
            main_state=main_state,
            place_state=place_state,
        )

        res = account.resources
        if cfg and hasattr(cfg, "get_active_build_plan"):
            build_plan = cfg.get_active_build_plan(v_id)
        else:
            from engine.actions.main_building import RUSH_RESOURCES_TEMPLATE
            build_plan = RUSH_RESOURCES_TEMPLATE

        next_upgrade = self.main_building_manager.get_next_build_candidate(
            state=main_state,
            plan=build_plan,
            resources=res,
        )

        # --- Árvore de Decisão da Arbitragem ---

        # Regra 1: Prevenção de Armazém a Transbordar (Overflow)
        if res.is_storage_full or (res.wood >= res.storage_max * 0.95 and res.stone >= res.storage_max * 0.95):
            # Se podemos construir, constrói de imediato
            if next_upgrade and main_state.queue_count < main_state.max_queue_size:
                return ArbitrageDecision(
                    village_id=v_id,
                    action_type=ArbitrageActionType.BUILD,
                    reason=f"Armazém quase cheio e próximo edifício '{next_upgrade.building}' disponível.",
                    target_building=next_upgrade,
                    building_queue_time_left=build_queue_time,
                    military_queues_time_left=military_timers,
                    cash_flow=cash_flow,
                )
            # Caso contrário, despacha excedente para tropas
            military_batch = self._find_affordable_military_batch(res, military_states, batch_size=10)
            if military_batch:
                return ArbitrageDecision(
                    village_id=v_id,
                    action_type=ArbitrageActionType.SPEND_SURPLUS,
                    reason="Armazém em risco de transbordamento. A recrutar tropas excedentes.",
                    target_recruitment=military_batch,
                    building_queue_time_left=build_queue_time,
                    military_queues_time_left=military_timers,
                    cash_flow=cash_flow,
                )

        # Regra 2: Fila de Construção Vazia ou Prestes a Terminar
        if main_state.queue_count == 0 or (build_queue_time < emergency_queue_seconds and main_state.queue_count < main_state.max_queue_size):
            if next_upgrade:
                return ArbitrageDecision(
                    village_id=v_id,
                    action_type=ArbitrageActionType.BUILD,
                    reason=f"Fila de construção com baixa ocupação ({build_queue_time:.0f}s). Prioridade evolução '{next_upgrade.building}'.",
                    target_building=next_upgrade,
                    building_queue_time_left=build_queue_time,
                    military_queues_time_left=military_timers,
                    cash_flow=cash_flow,
                )

        # Regra 3: Fila Militar em Risco de Esgotamento (Emergency Military Queue)
        for b_name, t_sec in military_timers.items():
            if main_state.buildings.get(b_name, 0) > 0 and t_sec < emergency_queue_seconds:
                # Fila do Quartel/Estábulo/Oficina está a expirar!
                # Tenta alocar um micro-lote dinâmico (2 a 5 unidades) para manter o temporizador a rodar
                micro_batch = self._find_affordable_military_batch(
                    resources=res,
                    military_states={b_name: military_states[b_name]},
                    batch_size=min_military_batch,
                )
                if micro_batch:
                    return ArbitrageDecision(
                        village_id=v_id,
                        action_type=ArbitrageActionType.RECRUIT_MICRO,
                        reason=f"Fila do {b_name.capitalize()} a expirar em {t_sec:.0f}s. A despachar micro-lote de emergência.",
                        target_recruitment=micro_batch,
                        building_queue_time_left=build_queue_time,
                        military_queues_time_left=military_timers,
                        cash_flow=cash_flow,
                    )

        # Regra 4: Fila de Construção Longa (Permitir Recrutamento Padrão)
        if build_queue_time >= emergency_queue_seconds:
            standard_batch = self._find_affordable_military_batch(res, military_states, batch_size=8)
            if standard_batch:
                return ArbitrageDecision(
                    village_id=v_id,
                    action_type=ArbitrageActionType.RECRUIT_NORMAL,
                    reason=f"Fila de construção confortável ({build_queue_time:.0f}s). A executar recrutamento militar padrão.",
                    target_recruitment=standard_batch,
                    building_queue_time_left=build_queue_time,
                    military_queues_time_left=military_timers,
                    cash_flow=cash_flow,
                )

        # Regra 5: Retenção Estratégica para o Próximo Edifício
        return ArbitrageDecision(
            village_id=v_id,
            action_type=ArbitrageActionType.HOLD_FOR_BUILD,
            reason="A reter recursos para completar custo da próxima construção ou aguardar fluxo de caixa.",
            building_queue_time_left=build_queue_time,
            military_queues_time_left=military_timers,
            cash_flow=cash_flow,
        )

    def _find_affordable_military_batch(
        self,
        resources: Resources,
        military_states: Dict[str, RecruitmentState],
        batch_size: int = 5,
    ) -> Dict[str, int]:
        """Calcula o melhor lote de tropas possível com os recursos e edifícios disponíveis."""
        orders: Dict[str, int] = {}
        curr_res = Resources(
            wood=resources.wood,
            stone=resources.stone,
            iron=resources.iron,
            pop_max=resources.pop_max,
            pop=resources.pop,
        )

        for b_name, m_state in military_states.items():
            possible_units = BUILDING_UNITS.get(b_name, [])
            for unit in possible_units:
                cost = UNIT_COSTS.get(unit)
                if not cost:
                    continue

                req_wood = cost["wood"] * batch_size
                req_stone = cost["stone"] * batch_size
                req_iron = cost["iron"] * batch_size
                req_pop = cost["pop"] * batch_size

                if curr_res.can_afford(wood=req_wood, stone=req_stone, iron=req_iron, pop=req_pop):
                    orders[unit] = batch_size
                    curr_res.wood -= req_wood
                    curr_res.stone -= req_stone
                    curr_res.iron -= req_iron
                    curr_res.pop += req_pop
                    break

        return orders

    async def execute_arbitrage_cycle(
        self,
        account: TribalAccount,
        village_id: Optional[int] = None,
        emergency_queue_seconds: float = 900.0,
        min_military_batch: int = 2,
    ) -> ArbitrageDecision:
        """
        Executa um ciclo completo de arbitragem económica:
        Avalia o estado da aldeia e despacha imediatamente a ação priorizada.
        """
        decision = await self.evaluate_village_arbitrage(
            account=account,
            village_id=village_id,
            emergency_queue_seconds=emergency_queue_seconds,
            min_military_batch=min_military_batch,
        )

        logger.info(
            f"[{account.world}] ⚖️ Decisão de Arbitragem Económica (Aldeia {decision.village_id}): "
            f"[{decision.action_type.value.upper()}] - {decision.reason}"
        )

        if decision.action_type == ArbitrageActionType.BUILD and decision.target_building:
            b_target = decision.target_building.building
            await self.main_building_manager.build_building(
                account=account,
                building=b_target,
                village_id=decision.village_id,
            )

        elif decision.action_type in (ArbitrageActionType.RECRUIT_MICRO, ArbitrageActionType.RECRUIT_NORMAL, ArbitrageActionType.SPEND_SURPLUS) and decision.target_recruitment:
            for unit, count in decision.target_recruitment.items():
                b_name = UNIT_TO_BUILDING.get(unit, "barracks")
                await self.recruitment_manager.train_units(
                    account=account,
                    building=b_name,
                    orders={unit: count},
                    village_id=decision.village_id,
                )
                await asyncio.sleep(get_human_delay(1.5, 0.3, 0.8, 2.5))

        return decision

    def schedule_auto_arbitrage(
        self,
        scheduler: TaskScheduler,
        account: TribalAccount,
        interval_seconds: float = 60.0,
        emergency_queue_seconds: float = 900.0,
        min_military_batch: int = 2,
        village_id: Optional[int] = None,
    ) -> None:
        """Agenda no TaskScheduler a execução periódica contínua da arbitragem económica."""
        async def arbitrage_task():
            try:
                await self.execute_arbitrage_cycle(
                    account=account,
                    village_id=village_id,
                    emergency_queue_seconds=emergency_queue_seconds,
                    min_military_batch=min_military_batch,
                )
            except Exception as e:
                logger.warning(f"Erro no ciclo de Arbitragem Económica: {e}")
            finally:
                if scheduler.is_running and not scheduler.is_paused:
                    scheduler.schedule_human_like(
                        name=f"AutoArbitrage-Village-{village_id or 'active'}",
                        priority=TaskPriority.BUILD,
                        action=arbitrage_task,
                        base_seconds=interval_seconds,
                        std_dev=interval_seconds * 0.15,
                        min_seconds=max(20.0, interval_seconds * 0.5),
                        max_seconds=interval_seconds * 1.5,
                    )

        scheduler.schedule(
            name=f"AutoArbitrage-Village-{village_id or 'active'}",
            priority=TaskPriority.BUILD,
            action=arbitrage_task,
            delay_seconds=5.0,
        )
        logger.info(
            f"Arbitragem Económica 'Fila Sempre Ativa' agendada a cada ~{interval_seconds:.0f}s."
        )
