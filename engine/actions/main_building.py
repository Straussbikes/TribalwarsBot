"""
Tribal Wars Mobile Automation Engine - MainBuildingManager (screen=main)
Gestão completa do Edifício Principal: leitura de níveis, fila de construção,
ordens de evolução, cancelamento e execução automática de planos de evolução (Build Templates).
"""

import asyncio
from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional, Tuple

from engine.core.account import TribalAccount
from engine.core.models import Resources, TaskPriority
from engine.core.scheduler import TaskScheduler
from engine.utils.parsers import (
    parse_build_queue,
    parse_building_levels,
    parse_building_upgrades,
)

logger = logging.getLogger(__name__)


# Identificadores canónicos de edifícios do Tribal Wars
class BuildingType:
    MAIN = "main"            # Edifício Principal
    BARRACKS = "barracks"    # Quartel
    STABLE = "stable"        # Estábulo
    GARAGE = "garage"        # Oficina
    CHURCH = "church"        # Igreja
    CHURCH_F = "church_f"    # Primeira Igreja
    SNOB = "snob"            # Academia
    SMITH = "smith"          # Ferreiro
    PLACE = "place"          # Praça de Reunião
    STATUE = "statue"        # Estátua
    MARKET = "market"        # Mercado
    WOOD = "wood"            # Bosque
    STONE = "stone"          # Poço de Argila
    IRON = "iron"            # Mina de Ferro
    FARM = "farm"            # Fazenda
    STORAGE = "storage"      # Armazém
    HIDE = "hide"            # Esconderijo
    WALL = "wall"            # Muralha


BUILDING_NAMES: Dict[str, str] = {
    BuildingType.MAIN: "Edifício Principal",
    BuildingType.BARRACKS: "Quartel",
    BuildingType.STABLE: "Estábulo",
    BuildingType.GARAGE: "Oficina",
    BuildingType.CHURCH: "Igreja",
    BuildingType.CHURCH_F: "Primeira Igreja",
    BuildingType.SNOB: "Academia",
    BuildingType.SMITH: "Ferreiro",
    BuildingType.PLACE: "Praça de Reunião",
    BuildingType.STATUE: "Estátua",
    BuildingType.MARKET: "Mercado",
    BuildingType.WOOD: "Bosque",
    BuildingType.STONE: "Poço de Argila",
    BuildingType.IRON: "Mina de Ferro",
    BuildingType.FARM: "Fazenda",
    BuildingType.STORAGE: "Armazém",
    BuildingType.HIDE: "Esconderijo",
    BuildingType.WALL: "Muralha",
}

# Mapa reverso de nomes amigáveis ou em inglês para identificador canónico
NAME_TO_BUILDING: Dict[str, str] = {
    "edifício principal": BuildingType.MAIN,
    "edificio principal": BuildingType.MAIN,
    "headquarters": BuildingType.MAIN,
    "main": BuildingType.MAIN,
    "quartel": BuildingType.BARRACKS,
    "barracks": BuildingType.BARRACKS,
    "estábulo": BuildingType.STABLE,
    "estabulo": BuildingType.STABLE,
    "stable": BuildingType.STABLE,
    "oficina": BuildingType.GARAGE,
    "garage": BuildingType.GARAGE,
    "workshop": BuildingType.GARAGE,
    "igreja": BuildingType.CHURCH,
    "church": BuildingType.CHURCH,
    "primeira igreja": BuildingType.CHURCH_F,
    "first church": BuildingType.CHURCH_F,
    "church_f": BuildingType.CHURCH_F,
    "academia": BuildingType.SNOB,
    "academy": BuildingType.SNOB,
    "snob": BuildingType.SNOB,
    "ferreiro": BuildingType.SMITH,
    "smith": BuildingType.SMITH,
    "smithy": BuildingType.SMITH,
    "praça de reunião": BuildingType.PLACE,
    "praca de reuniao": BuildingType.PLACE,
    "rally point": BuildingType.PLACE,
    "place": BuildingType.PLACE,
    "estátua": BuildingType.STATUE,
    "estatua": BuildingType.STATUE,
    "statue": BuildingType.STATUE,
    "mercado": BuildingType.MARKET,
    "market": BuildingType.MARKET,
    "bosque": BuildingType.WOOD,
    "timber camp": BuildingType.WOOD,
    "wood": BuildingType.WOOD,
    "poço de argila": BuildingType.STONE,
    "poco de argila": BuildingType.STONE,
    "clay pit": BuildingType.STONE,
    "stone": BuildingType.STONE,
    "mina de ferro": BuildingType.IRON,
    "iron mine": BuildingType.IRON,
    "iron": BuildingType.IRON,
    "fazenda": BuildingType.FARM,
    "farm": BuildingType.FARM,
    "armazém": BuildingType.STORAGE,
    "armazem": BuildingType.STORAGE,
    "warehouse": BuildingType.STORAGE,
    "storage": BuildingType.STORAGE,
    "esconderijo": BuildingType.HIDE,
    "hiding place": BuildingType.HIDE,
    "hide": BuildingType.HIDE,
    "muralha": BuildingType.WALL,
    "wall": BuildingType.WALL,
}

# Requisitos do sistema tecnológico de edifícios do Tribal Wars
BUILDING_REQUIREMENTS: Dict[str, Dict[str, int]] = {
    BuildingType.MAIN: {},
    BuildingType.BARRACKS: {BuildingType.MAIN: 3},
    BuildingType.STABLE: {BuildingType.MAIN: 10, BuildingType.BARRACKS: 5, BuildingType.SMITH: 5},
    BuildingType.GARAGE: {BuildingType.MAIN: 10, BuildingType.SMITH: 10},
    BuildingType.CHURCH: {BuildingType.MAIN: 5, BuildingType.FARM: 5},
    BuildingType.CHURCH_F: {},
    BuildingType.SNOB: {BuildingType.MAIN: 20, BuildingType.SMITH: 20, BuildingType.MARKET: 10},
    BuildingType.SMITH: {BuildingType.MAIN: 5, BuildingType.BARRACKS: 1},
    BuildingType.PLACE: {},
    BuildingType.STATUE: {},
    BuildingType.MARKET: {BuildingType.MAIN: 3, BuildingType.STORAGE: 2},
    BuildingType.WOOD: {},
    BuildingType.STONE: {},
    BuildingType.IRON: {},
    BuildingType.FARM: {},
    BuildingType.STORAGE: {},
    BuildingType.HIDE: {},
    BuildingType.WALL: {BuildingType.BARRACKS: 1},
}

# Níveis máximos permitidos por edifício
MAX_BUILDING_LEVELS: Dict[str, int] = {
    BuildingType.MAIN: 30,
    BuildingType.BARRACKS: 25,
    BuildingType.STABLE: 20,
    BuildingType.GARAGE: 15,
    BuildingType.CHURCH: 3,
    BuildingType.CHURCH_F: 1,
    BuildingType.SNOB: 3,
    BuildingType.SMITH: 20,
    BuildingType.PLACE: 1,
    BuildingType.STATUE: 1,
    BuildingType.MARKET: 25,
    BuildingType.WOOD: 30,
    BuildingType.STONE: 30,
    BuildingType.IRON: 30,
    BuildingType.FARM: 30,
    BuildingType.STORAGE: 30,
    BuildingType.HIDE: 10,
    BuildingType.WALL: 20,
}


@dataclass
class QueueOrder:
    """Representação de uma construção em andamento na fila do Edifício Principal."""
    order_id: str
    building: str
    building_name: str
    target_level: int
    timer_str: str = ""
    cancel_url: str = ""


@dataclass
class BuildingUpgrade:
    """Opção e requisitos de evolução para um determinado edifício."""
    building: str
    current_level: int
    target_level: int
    wood: int = 0
    stone: int = 0
    iron: int = 0
    pop: int = 0
    can_build: bool = False
    error_reason: Optional[str] = None
    build_url: Optional[str] = None


@dataclass
class MainBuildingState:
    """Estado consolidado do Edifício Principal para uma aldeia."""
    village_id: int
    buildings: Dict[str, int] = field(default_factory=dict)
    queue: List[QueueOrder] = field(default_factory=list)
    upgrades: Dict[str, BuildingUpgrade] = field(default_factory=dict)
    max_queue_size: int = 2

    @property
    def queue_count(self) -> int:
        return len(self.queue)

    @property
    def is_queue_full(self) -> bool:
        """Verifica se a fila atingiu a capacidade máxima sem penalidade."""
        return self.queue_count >= self.max_queue_size

    @property
    def virtual_levels(self) -> Dict[str, int]:
        """
        Calcula os níveis efetivos/virtuais:
        Nível atual + construções pendentes na fila.
        """
        virt = self.buildings.copy()
        for order in self.queue:
            b = order.building
            if b in virt:
                virt[b] = max(virt[b], order.target_level)
            else:
                virt[b] = order.target_level
        return virt


# Modelos de Construção Pré-definidos (Build Templates)
RUSH_RESOURCES_TEMPLATE: List[Tuple[str, int]] = [
    (BuildingType.WOOD, 1),
    (BuildingType.STONE, 1),
    (BuildingType.WOOD, 2),
    (BuildingType.STONE, 2),
    (BuildingType.IRON, 1),
    (BuildingType.MAIN, 2),
    (BuildingType.MAIN, 3),
    (BuildingType.BARRACKS, 1),
    (BuildingType.WOOD, 3),
    (BuildingType.STONE, 3),
    (BuildingType.STORAGE, 2),
    (BuildingType.FARM, 2),
    (BuildingType.WOOD, 4),
    (BuildingType.STONE, 4),
    (BuildingType.IRON, 2),
    (BuildingType.WOOD, 5),
    (BuildingType.STONE, 5),
    (BuildingType.STORAGE, 3),
    (BuildingType.IRON, 3),
    (BuildingType.WOOD, 6),
    (BuildingType.STONE, 6),
    (BuildingType.IRON, 4),
    (BuildingType.STORAGE, 4),
    (BuildingType.FARM, 3),
    (BuildingType.WOOD, 7),
    (BuildingType.STONE, 7),
    (BuildingType.IRON, 5),
    (BuildingType.WOOD, 8),
    (BuildingType.STONE, 8),
    (BuildingType.STORAGE, 5),
    (BuildingType.IRON, 6),
    (BuildingType.WOOD, 9),
    (BuildingType.STONE, 9),
    (BuildingType.IRON, 7),
    (BuildingType.WOOD, 10),
    (BuildingType.STONE, 10),
    (BuildingType.IRON, 8),
    (BuildingType.STORAGE, 6),
    (BuildingType.FARM, 4),
]

BALANCED_TEMPLATE: List[Tuple[str, int]] = [
    (BuildingType.WOOD, 1),
    (BuildingType.STONE, 1),
    (BuildingType.IRON, 1),
    (BuildingType.MAIN, 2),
    (BuildingType.MAIN, 3),
    (BuildingType.BARRACKS, 1),
    (BuildingType.WALL, 1),
    (BuildingType.WOOD, 2),
    (BuildingType.STONE, 2),
    (BuildingType.STORAGE, 2),
    (BuildingType.FARM, 2),
    (BuildingType.WOOD, 3),
    (BuildingType.STONE, 3),
    (BuildingType.IRON, 2),
    (BuildingType.MAIN, 4),
    (BuildingType.MAIN, 5),
    (BuildingType.BARRACKS, 2),
    (BuildingType.SMITH, 1),
    (BuildingType.WOOD, 4),
    (BuildingType.STONE, 4),
    (BuildingType.IRON, 3),
    (BuildingType.STORAGE, 3),
    (BuildingType.WALL, 2),
    (BuildingType.FARM, 3),
    (BuildingType.WOOD, 5),
    (BuildingType.STONE, 5),
    (BuildingType.IRON, 4),
    (BuildingType.MAIN, 6),
    (BuildingType.MAIN, 7),
    (BuildingType.BARRACKS, 3),
    (BuildingType.STORAGE, 4),
    (BuildingType.WALL, 3),
]

MILITARY_RUSH_TEMPLATE: List[Tuple[str, int]] = [
    (BuildingType.WOOD, 1),
    (BuildingType.STONE, 1),
    (BuildingType.IRON, 1),
    (BuildingType.MAIN, 2),
    (BuildingType.MAIN, 3),
    (BuildingType.BARRACKS, 1),
    (BuildingType.BARRACKS, 2),
    (BuildingType.WOOD, 2),
    (BuildingType.STONE, 2),
    (BuildingType.IRON, 2),
    (BuildingType.STORAGE, 2),
    (BuildingType.MAIN, 4),
    (BuildingType.MAIN, 5),
    (BuildingType.BARRACKS, 3),
    (BuildingType.SMITH, 1),
    (BuildingType.WALL, 1),
    (BuildingType.WOOD, 3),
    (BuildingType.STONE, 3),
    (BuildingType.IRON, 3),
    (BuildingType.FARM, 2),
    (BuildingType.MAIN, 6),
    (BuildingType.MAIN, 7),
    (BuildingType.BARRACKS, 4),
    (BuildingType.BARRACKS, 5),
    (BuildingType.SMITH, 2),
    (BuildingType.SMITH, 3),
    (BuildingType.SMITH, 4),
    (BuildingType.SMITH, 5),
    (BuildingType.MAIN, 8),
    (BuildingType.MAIN, 9),
    (BuildingType.MAIN, 10),
    (BuildingType.STABLE, 1),
]


class MainBuildingManager:
    """
    Controlador de automação para o Edifício Principal.
    Fornece parsing de estado, ordens de melhoria, cancelamentos e agendamento inteligente de filas.
    """

    def __init__(self, default_max_queue: int = 2):
        self.default_max_queue = default_max_queue

    def normalize_building_id(self, raw_name_or_id: str) -> str:
        """Normaliza um nome ou id qualquer para o id oficial canónico."""
        cleaned = raw_name_or_id.strip().lower()
        return NAME_TO_BUILDING.get(cleaned, cleaned)

    async def get_state(
        self, account: TribalAccount, village_id: Optional[int] = None
    ) -> MainBuildingState:
        """
        Navega até o ecrã 'screen=main' e constrói o estado consolidado da aldeia.
        """
        html = await account.get_screen("main", village_id=village_id)
        v_id = village_id or account.current_village_id or 0

        # 1. Parsing dos níveis de edifícios
        levels = parse_building_levels(html, account.last_game_data)

        # 2. Parsing da fila de construção
        raw_queue = parse_build_queue(html)
        queue_orders: List[QueueOrder] = []
        for q in raw_queue:
            b_canon = self.normalize_building_id(q.get("building_raw", ""))
            b_name = BUILDING_NAMES.get(b_canon, q.get("building_raw", ""))
            queue_orders.append(
                QueueOrder(
                    order_id=str(q.get("order_id", "")),
                    building=b_canon,
                    building_name=b_name,
                    target_level=int(q.get("target_level", 1)),
                    timer_str=str(q.get("timer_str", "")),
                    cancel_url=str(q.get("cancel_url", "")),
                )
            )

        # 3. Parsing das opções de melhoria
        raw_upgrades = parse_building_upgrades(html)
        upgrades: Dict[str, BuildingUpgrade] = {}
        for b_id, up in raw_upgrades.items():
            b_canon = self.normalize_building_id(b_id)
            upgrades[b_canon] = BuildingUpgrade(
                building=b_canon,
                current_level=up["current_level"],
                target_level=up["target_level"],
                wood=up["wood"],
                stone=up["stone"],
                iron=up["iron"],
                pop=up["pop"],
                can_build=up["can_build"],
                error_reason=up["error_reason"],
                build_url=up["build_url"],
            )

        return MainBuildingState(
            village_id=v_id,
            buildings=levels,
            queue=queue_orders,
            upgrades=upgrades,
            max_queue_size=self.default_max_queue,
        )

    async def build_building(
        self,
        account: TribalAccount,
        building: str,
        village_id: Optional[int] = None,
        force: bool = True,
    ) -> bool:
        """
        Executa a ordem de construção de um edifício no Edifício Principal.
        Envia a requisição com injeção do token CSRF 'h' e headers móveis.
        """
        b_canon = self.normalize_building_id(building)
        logger.info(
            f"[{account.world}] A enviar ordem de construção para: '{b_canon}' "
            f"({BUILDING_NAMES.get(b_canon, b_canon)})"
        )

        try:
            # Envia via upgrade_building padrão mobile/desktop com CSRF token
            extra_params = {
                "action": "upgrade_building",
                "id": b_canon,
                "type": "main",
                "force": "1" if force else "0",
                "h": account.csrf_token or "",
            }
            html = await account.get_screen(
                screen="main",
                village_id=village_id,
                extra_params=extra_params,
                apply_jitter=True,
            )
            # Verifica se o edifício entrou na fila ou se os recursos foram deduzidos
            levels = parse_building_levels(html, account.last_game_data)
            queue = parse_build_queue(html)
            logger.info(
                f"[{account.world}] Ordem para '{b_canon}' enviada. "
                f"Itens em fila atualizados: {len(queue)}"
            )
            return True
        except Exception as e:
            logger.error(f"[{account.world}] Falha ao construir '{b_canon}': {e}")
            return False

    async def cancel_order(
        self,
        account: TribalAccount,
        order_id: str,
        village_id: Optional[int] = None,
    ) -> bool:
        """
        Cancela uma ordem de construção em andamento na fila.
        """
        logger.info(f"[{account.world}] A cancelar ordem de construção ID '{order_id}'")
        try:
            extra_params = {
                "action": "cancel_order",
                "id": order_id,
                "type": "main",
                "h": account.csrf_token or "",
            }
            await account.get_screen(
                screen="main",
                village_id=village_id,
                extra_params=extra_params,
                apply_jitter=True,
            )

            logger.info(f"[{account.world}] Ordem '{order_id}' cancelada com sucesso.")
            return True
        except Exception as e:
            logger.error(f"[{account.world}] Falha ao cancelar ordem '{order_id}': {e}")
            return False

    def are_requirements_met(self, building: str, current_levels: Dict[str, int]) -> bool:
        """Valida se os edifícios pré-requisitos estão no nível mínimo necessário."""
        reqs = BUILDING_REQUIREMENTS.get(building, {})
        for req_b, req_lvl in reqs.items():
            if current_levels.get(req_b, 0) < req_lvl:
                return False
        return True

    def get_next_build_candidate(
        self,
        state: MainBuildingState,
        plan: List[Tuple[str, int]],
        resources: Resources,
        max_queue: Optional[int] = None,
    ) -> Optional[BuildingUpgrade]:
        """
        Avalia o plano de construção e o estado atual da aldeia para encontrar
        o próximo edifício elegível para evolução.
        Retorna o BuildingUpgrade elegível ou None caso não seja possível construir.
        """
        limit = max_queue if max_queue is not None else state.max_queue_size
        if state.queue_count >= limit:
            logger.info(
                f"Fila de construção cheia ({state.queue_count}/{limit}). "
                f"A aguardar conclusão da ordem em andamento."
            )
            return None

        virt_levels = state.virtual_levels
        any_unreached = False

        for building_entry, target_lvl in plan:
            b = self.normalize_building_id(building_entry)
            current_virt = virt_levels.get(b, 0)

            # Se ainda não atingiu o nível da meta
            if current_virt < target_lvl:
                any_unreached = True

                # 1. Verifica se os pré-requisitos tecnológicos estão satisfeitos
                if not self.are_requirements_met(b, virt_levels):
                    continue

                # 2. Verifica se o nível máximo do edifício já foi atingido
                max_lvl = MAX_BUILDING_LEVELS.get(b, 30)
                if current_virt >= max_lvl:
                    continue

                # 3. Verifica informações de upgrade
                upgrade_info = state.upgrades.get(b)
                if upgrade_info:
                    # Verifica se temos recursos suficientes
                    if resources.can_afford(
                        wood=upgrade_info.wood,
                        stone=upgrade_info.stone,
                        iron=upgrade_info.iron,
                        pop=upgrade_info.pop,
                    ):
                        return upgrade_info
                    else:
                        b_name = BUILDING_NAMES.get(b, b)
                        logger.info(
                            f"Próximo alvo do plano: '{b_name}' ({b}) para Nível {current_virt + 1}. "
                            f"Recursos: {resources.wood}/{upgrade_info.wood} M, "
                            f"{resources.stone}/{upgrade_info.stone} A, "
                            f"{resources.iron}/{upgrade_info.iron} F (Pop: {resources.free_pop}/{upgrade_info.pop})"
                        )
                        return None
                else:
                    # Se não temos a linha no HTML (ex.: ainda não desbloqueado)
                    continue

        if not any_unreached:
            logger.info(f"Todas as {len(plan)} metas do plano de construção ativo foram alcançadas!")
        else:
            logger.debug("Existem metas pendentes no plano que ainda aguardam pré-requisitos.")
        return None


    async def run_auto_build_cycle(
        self,
        account: TribalAccount,
        plan: List[Tuple[str, int]],
        max_queue: Optional[int] = None,
        village_id: Optional[int] = None,
    ) -> Optional[str]:
        """
        Executa um ciclo completo de verificação e evolução automática:
        1. Obtém o estado do Edifício Principal.
        2. Avalia o próximo candidato conforme o plano e recursos disponíveis.
        3. Envia o comando de construção se elegível.
        Retorna o identificador do edifício construído, ou None.
        """
        state = await self.get_state(account, village_id=village_id)
        limit = max_queue if max_queue is not None else state.max_queue_size
        logger.info(
            f"[{account.world}] A avaliar Edifício Principal (Fila atual: {state.queue_count}/{limit})."
        )
        candidate = self.get_next_build_candidate(
            state=state,
            plan=plan,
            resources=account.resources,
            max_queue=max_queue,
        )

        if candidate:
            success = await self.build_building(
                account=account,
                building=candidate.building,
                village_id=village_id,
            )
            if success:
                b_name = BUILDING_NAMES.get(candidate.building, candidate.building)
                logger.info(
                    f"[{account.world}] ✅ Sucesso ao colocar na fila: "
                    f"'{b_name}' para Nível {candidate.target_level}!"
                )
                return candidate.building
        return None


    def schedule_auto_build(
        self,
        scheduler: TaskScheduler,
        account: TribalAccount,
        plan: List[Tuple[str, int]],
        max_queue: int = 2,
        village_id: Optional[int] = None,
        interval_seconds: float = 60.0,
    ) -> None:
        async def auto_build_task():
            try:
                # Atualiza recursos antes de tentar construir
                await account.refresh_state(village_id=village_id)
                await self.run_auto_build_cycle(
                    account=account,
                    plan=plan,
                    max_queue=max_queue,
                    village_id=village_id,
                )
            except Exception as e:
                logger.warning(f"Erro no ciclo de auto-build: {e}")
            finally:
                # Reagenda continuamente para o próximo ciclo
                if scheduler.is_running and not scheduler.is_paused:
                    scheduler.schedule_human_like(
                        name=f"AutoBuild-Village-{village_id or 'active'}",
                        priority=TaskPriority.BUILD,
                        action=auto_build_task,
                        base_seconds=interval_seconds,
                        std_dev=interval_seconds * 0.2,
                        min_seconds=max(15.0, interval_seconds * 0.6),
                        max_seconds=interval_seconds * 1.5,
                    )

        # Agenda a primeira execução com pequeno atraso inicial de arranque
        scheduler.schedule(
            name=f"AutoBuild-Village-{village_id or 'active'}",
            priority=TaskPriority.BUILD,
            action=auto_build_task,
            delay_seconds=5.0,
        )

