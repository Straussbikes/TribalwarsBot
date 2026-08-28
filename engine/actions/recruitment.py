"""
Tribal Wars Mobile Automation Engine - RecruitmentManager (screen=barracks, stable, garage)
Gestão de Recrutamento Militar: Quartel, Estábulo e Oficina com controlo de metas de exército,
produção contínua em pequenos lotes e validação de população livre da Fazenda.
"""

import asyncio
from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional

from engine.actions.place import PlaceManager
from engine.core.account import TribalAccount
from engine.core.models import TaskPriority
from engine.core.scheduler import TaskScheduler
from engine.utils.parsers import parse_recruitment_page

logger = logging.getLogger(__name__)

# Mapeamento canónico de cada unidade para o respetivo edifício militar
UNIT_TO_BUILDING: Dict[str, str] = {
    "spear": "barracks",
    "sword": "barracks",
    "axe": "barracks",
    "archer": "barracks",
    "spy": "stable",
    "light": "stable",
    "marcher": "stable",
    "heavy": "stable",
    "ram": "garage",
    "catapult": "garage",
}

BUILDING_UNITS: Dict[str, List[str]] = {
    "barracks": ["spear", "sword", "axe", "archer"],
    "stable": ["spy", "light", "marcher", "heavy"],
    "garage": ["ram", "catapult"],
}

# Tabela de pré-requisitos mínimos de edifícios para desbloqueio/pesquisa de cada unidade
UNIT_BUILDING_REQUIREMENTS: Dict[str, Dict[str, int]] = {
    "spear": {"barracks": 1},
    "sword": {"barracks": 1, "smith": 1},
    "axe": {"barracks": 2, "smith": 2},
    "archer": {"barracks": 5, "smith": 5},
    "spy": {"stable": 1},
    "light": {"stable": 3},
    "marcher": {"stable": 5},
    "heavy": {"stable": 10, "smith": 15},
    "ram": {"garage": 1},
    "catapult": {"garage": 2, "smith": 12},
}


UNIT_POP_COST: Dict[str, int] = {
    "spear": 1,
    "sword": 1,
    "axe": 1,
    "archer": 1,
    "spy": 2,
    "light": 4,
    "marcher": 5,
    "heavy": 6,
    "ram": 5,
    "catapult": 8,
}


@dataclass
class TrainingOrder:
    """Representação de uma ordem ativa na fila de recrutamento."""
    unit: str
    count: int
    timer_str: str = ""
    finish_time: str = ""
    cancel_url: Optional[str] = None


@dataclass
class RecruitmentState:
    """Estado consolidado de um edifício militar."""
    building: str
    available_units: Dict[str, int] = field(default_factory=dict)
    queue: List[TrainingOrder] = field(default_factory=list)
    total_in_queue: Dict[str, int] = field(default_factory=dict)

    @property
    def is_training(self) -> bool:
        return len(self.queue) > 0


class RecruitmentManager:
    """
    Controlador de automação de Recrutamento Militar.
    Permite ler filas de treino, verificar custos e capacidade máxima,
    e submeter ordens de recrutamento em lotes inteligentes.
    """

    def __init__(
        self,
        place_manager: Optional[PlaceManager] = None,
        smith_manager: Optional[Any] = None,
    ):
        self.place_manager = place_manager or PlaceManager()
        if smith_manager is not None:
            self.smith_manager = smith_manager
        else:
            from engine.actions.smith import SmithManager
            self.smith_manager = SmithManager()

    async def get_building_state(
        self, account: TribalAccount, building: str, village_id: Optional[int] = None
    ) -> RecruitmentState:
        """
        Consulta o ecrã do edifício militar ('barracks', 'stable' ou 'garage')
        e extrai as tropas disponíveis e ordens ativas na fila.
        """
        html = await account.get_screen(building, village_id=village_id)
        raw_data = parse_recruitment_page(html)

        orders: List[TrainingOrder] = [
            TrainingOrder(
                unit=str(q["unit"]),
                count=int(q["count"]),
                timer_str=str(q.get("timer_str", "")),
                finish_time=str(q.get("finish_time", "")),
                cancel_url=q.get("cancel_url"),
            )
            for q in raw_data.get("queue", [])
        ]

        state = RecruitmentState(
            building=building,
            available_units=raw_data.get("available_units", {}),
            queue=orders,
            total_in_queue=raw_data.get("total_in_queue", {}),
        )

        logger.info(
            f"[{account.world}] {building.capitalize()}: {len(orders)} ordens na fila "
            f"(Total em treino: {sum(state.total_in_queue.values())} tropas)."
        )
        return state

    async def train_units(
        self,
        account: TribalAccount,
        building: str,
        orders: Dict[str, int],
        village_id: Optional[int] = None,
    ) -> bool:
        """
        Submete o formulário de treino de unidades para 'screen={building}&action=train'.
        Injeta o token CSRF e micro-jitter de toque em ecrã.
        """
        valid_orders = {u: str(cnt) for u, cnt in orders.items() if cnt > 0}
        if not valid_orders:
            return False

        v_id = village_id or account.current_village_id
        order_summary = ", ".join(f"{cnt}x {u}" for u, cnt in valid_orders.items())
        logger.info(f"[{account.world}] A recrutar no {building.capitalize()}: {order_summary}...")

        # Prepara payload compatível com inputs planos ('spear=10') e aninhados ('units[spear]=10')
        post_data = {}
        for u, cnt in valid_orders.items():
            post_data[u] = str(cnt)
            post_data[f"units[{u}]"] = str(cnt)
        if account.csrf_token:
            post_data["h"] = account.csrf_token

        try:
            await account.post_action(
                screen=building,
                action="train",
                data=post_data,
                village_id=v_id,
                apply_jitter=True,
            )
            logger.info(f"[{account.world}] ✅ Recrutamento iniciado com sucesso: {order_summary}")
            return True
        except Exception as e:
            logger.error(f"[{account.world}] Falha ao recrutar no {building}: {e}")
            return False

    async def run_recruitment_cycle(
        self,
        account: TribalAccount,
        targets: Dict[str, int],
        batch_sizes: Dict[str, int],
        min_free_pop: int = 10,
        village_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """
        Executa um ciclo inteligente de recrutamento:
        1. Valida população livre na fazenda.
        2. Inspeciona tropas na aldeia e em treino para calcular o défice exato até à meta.
        3. Recruta em lotes configuráveis sem exceder os recursos disponíveis.
        """
        recruited_summary: Dict[str, int] = {}
        v_id = village_id or account.current_village_id

        # 1. Validação de População Livre da Fazenda
        free_pop = 9999
        try:
            village = await account.refresh_state(village_id=v_id)
            free_pop = village.resources.free_pop
            if free_pop <= 0 or (min_free_pop > 0 and free_pop < min_free_pop):
                logger.info(
                    f"[{account.world}] População livre ({free_pop}) < limite de segurança "
                    f"({min_free_pop}). Recrutamento suspenso para preservar melhorias de edifícios."
                )
                return recruited_summary
        except Exception as e:
            logger.warning(f"Não foi possível verificar população antes de recrutar: {e}")

        # Orçamento de população disponível para este ciclo
        pop_budget = max(0, free_pop - min_free_pop) if min_free_pop > 0 else free_pop

        # 2. Leitura de tropas existentes na aldeia ativa
        try:
            place_state = await self.place_manager.get_state(account, village_id=v_id)
            troops_home = place_state.units.to_dict()
        except Exception as e:
            logger.warning(f"Falha ao ler tropas na aldeia para cálculo de metas: {e}")
            troops_home = {}

        # Obtém níveis de edifícios conhecidos da aldeia
        village_buildings: Dict[str, int] = {}
        if village and hasattr(village, "buildings") and village.buildings:
            village_buildings = village.buildings
        elif v_id in account.villages and account.villages[v_id].buildings:
            village_buildings = account.villages[v_id].buildings

        # 3. Auto-pesquisa no Ferreiro para unidades necessárias cujos requisitos de edifícios foram atingidos
        needed_target_units = [u for u, target in targets.items() if target > 0]
        if needed_target_units and self.smith_manager:
            try:
                await self.smith_manager.auto_research_needed_units(
                    account=account,
                    village_id=v_id,
                    needed_units=needed_target_units,
                )
            except Exception as e:
                logger.debug(f"Erro suave ao auto-pesquisar tropas no Ferreiro: {e}")

        # 4. Processamento por edifício militar
        buildings_to_check = set()
        for u, target in targets.items():
            if target > 0 and u in UNIT_TO_BUILDING:
                buildings_to_check.add(UNIT_TO_BUILDING[u])

        for building in ("barracks", "stable", "garage"):
            if building not in buildings_to_check:
                continue

            # Verificação 1: Se os edifícios da aldeia são conhecidos e o edifício principal de treino não existe (nível 0)
            if village_buildings and village_buildings.get(building, 0) < 1:
                logger.info(
                    f"[{account.world}] Edifício '{building}' ainda não construído na aldeia {v_id} (nível 0). "
                    f"Recrutamento ignorado para este edifício."
                )
                continue

            try:
                b_state = await self.get_building_state(account, building, village_id=v_id)
            except Exception as e:
                logger.warning(f"Falha ao consultar {building}: {e}")
                continue

            orders_for_building: Dict[str, int] = {}

            for unit in BUILDING_UNITS.get(building, []):
                target_count = targets.get(unit, 0)
                if target_count <= 0:
                    continue

                # Verificação 2: Pré-requisitos de edifícios da unidade (ex: Bárbaro requer Quartel 2 e Ferreiro 2)
                reqs = UNIT_BUILDING_REQUIREMENTS.get(unit, {})
                if village_buildings and reqs:
                    unmet = [
                        f"{req_b} nv{req_lvl} (atual: {village_buildings.get(req_b, 0)})"
                        for req_b, req_lvl in reqs.items()
                        if village_buildings.get(req_b, 0) < req_lvl
                    ]
                    if unmet:
                        logger.info(
                            f"[{account.world}] Pré-requisitos não cumpridos para {unit.capitalize()} na aldeia {v_id}: "
                            f"{', '.join(unmet)}. Ignorando."
                        )
                        continue

                # Verificação 3: Unidade desbloqueada/pesquisada no ecrã de treino
                if unit not in b_state.available_units:
                    logger.info(
                        f"[{account.world}] {unit.capitalize()} não está pesquisado ou desbloqueado no {building.capitalize()} "
                        f"da aldeia {v_id}. Ignorando."
                    )
                    continue

                home_count = troops_home.get(unit, 0)
                in_queue_count = b_state.total_in_queue.get(unit, 0)
                needed = target_count - (home_count + in_queue_count)

                if needed <= 0:
                    logger.debug(f"Meta de {unit} atingida ({home_count} na aldeia + {in_queue_count} na fila >= {target_count}).")
                    continue

                # Quantidade máxima que os recursos da aldeia permitem treinar no momento
                max_recruitable = b_state.available_units.get(unit, 0)
                if max_recruitable <= 0:
                    logger.debug(f"Recursos insuficientes no momento para recrutar {unit}.")
                    continue

                # Limita pela população livre disponível
                pop_per_unit = UNIT_POP_COST.get(unit, 1)
                max_by_pop = pop_budget // pop_per_unit if pop_per_unit > 0 else needed
                if max_by_pop <= 0:
                    continue

                # Lote configurado (padrão de 10 unidades por ciclo)
                batch_limit = batch_sizes.get(unit, 10)
                to_recruit = min(needed, batch_limit, max_recruitable, max_by_pop)

                if to_recruit > 0:
                    orders_for_building[unit] = to_recruit
                    pop_budget -= to_recruit * pop_per_unit

            if orders_for_building:
                success = await self.train_units(
                    account=account,
                    building=building,
                    orders=orders_for_building,
                    village_id=v_id,
                )
                if success:
                    recruited_summary.update(orders_for_building)

        return recruited_summary

    def schedule_auto_recruit(
        self,
        scheduler: TaskScheduler,
        account: TribalAccount,
        recruit_config: Any,
        village_id: Optional[int] = None,
        enabled_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        """
        Agenda no TaskScheduler a rotina periódica contínua de Recrutamento Militar.
        """
        interval_minutes = getattr(recruit_config, "interval_minutes", 5.0)
        interval_seconds = interval_minutes * 60.0

        async def auto_recruit_task():
            if enabled_check and not enabled_check():
                return

            try:
                targets = getattr(recruit_config, "targets", {})
                batch_sizes = getattr(recruit_config, "batch_sizes", {})
                min_free_pop = getattr(recruit_config, "min_free_pop", 10)

                await self.run_recruitment_cycle(
                    account=account,
                    targets=targets,
                    batch_sizes=batch_sizes,
                    min_free_pop=min_free_pop,
                    village_id=village_id,
                )
            except Exception as e:
                logger.warning(f"Erro na rotina de recrutamento: {e}")
            finally:
                if scheduler.is_running and not scheduler.is_paused:
                    if not enabled_check or enabled_check():
                        scheduler.schedule_human_like(
                            name=f"AutoRecruit-Village-{village_id or 'active'}",
                            priority=TaskPriority.RECRUIT,
                            action=auto_recruit_task,
                            base_seconds=interval_seconds,
                            std_dev=interval_seconds * 0.15,
                            min_seconds=max(30.0, interval_seconds * 0.5),
                            max_seconds=interval_seconds * 1.5,
                        )

        # Agenda a primeira execução após 10 segundos
        scheduler.schedule(
            name=f"AutoRecruit-Village-{village_id or 'active'}",
            priority=TaskPriority.RECRUIT,
            action=auto_recruit_task,
            delay_seconds=10.0,
        )
        logger.info(f"Recrutamento Militar agendado a cada ~{interval_minutes:.1f} minutos.")
