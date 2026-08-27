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

    def __init__(self, place_manager: Optional[PlaceManager] = None):
        self.place_manager = place_manager or PlaceManager()

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

        try:
            await account.post_action(
                screen=building,
                action="train",
                data=valid_orders,
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
        try:
            village = await account.refresh_state()
            if village.resources.free_pop <= min_free_pop:
                logger.info(
                    f"[{account.world}] População livre ({village.resources.free_pop}) <= limite de segurança "
                    f"({min_free_pop}). Recrutamento suspenso para preservar melhorias de edifícios."
                )
                return recruited_summary
        except Exception as e:
            logger.warning(f"Não foi possível verificar população antes de recrutar: {e}")

        # 2. Leitura de tropas existentes na aldeia ativa
        try:
            place_state = await self.place_manager.get_state(account, village_id=v_id)
            troops_home = place_state.units.to_dict()
        except Exception as e:
            logger.warning(f"Falha ao ler tropas na aldeia para cálculo de metas: {e}")
            troops_home = {}

        # 3. Processamento por edifício militar
        buildings_to_check = set()
        for u, target in targets.items():
            if target > 0 and u in UNIT_TO_BUILDING:
                buildings_to_check.add(UNIT_TO_BUILDING[u])

        for building in ("barracks", "stable", "garage"):
            if building not in buildings_to_check:
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

                # Lote configurado (padrão de 10 unidades por ciclo)
                batch_limit = batch_sizes.get(unit, 10)
                to_recruit = min(needed, batch_limit, max_recruitable)

                if to_recruit > 0:
                    orders_for_building[unit] = to_recruit

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
    ) -> None:
        """
        Agenda no TaskScheduler a rotina periódica contínua de Recrutamento Militar.
        """
        interval_minutes = getattr(recruit_config, "interval_minutes", 5.0)
        interval_seconds = interval_minutes * 60.0

        async def auto_recruit_task():
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
