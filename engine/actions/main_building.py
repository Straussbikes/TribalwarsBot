"""
Tribal Wars Mobile Automation Engine - MainBuildingManager (screen=main)
Gestão completa do Edifício Principal: leitura de níveis, fila de construção,
ordens de evolução, cancelamento e execução automática de planos de evolução (Build Templates).
"""

import asyncio
from dataclasses import dataclass, field
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.parse

from engine.core.account import TribalAccount
from engine.core.exceptions import BotProtectionError, SessionExpiredError
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

# Custos base e multiplicador padrão por nível de edifício
BASE_BUILDING_COSTS: Dict[str, Dict[str, Any]] = {
    BuildingType.WOOD: {"wood": 90, "stone": 80, "iron": 70, "pop": 5, "factor": 1.25},
    BuildingType.STONE: {"wood": 65, "stone": 100, "iron": 40, "pop": 10, "factor": 1.275},
    BuildingType.IRON: {"wood": 75, "stone": 65, "iron": 100, "pop": 10, "factor": 1.25},
    BuildingType.MAIN: {"wood": 90, "stone": 80, "iron": 70, "pop": 5, "factor": 1.26},
    BuildingType.BARRACKS: {"wood": 200, "stone": 170, "iron": 90, "pop": 7, "factor": 1.26},
    BuildingType.STABLE: {"wood": 270, "stone": 240, "iron": 260, "pop": 8, "factor": 1.26},
    BuildingType.GARAGE: {"wood": 300, "stone": 240, "iron": 260, "pop": 8, "factor": 1.26},
    BuildingType.CHURCH: {"wood": 16000, "stone": 20000, "iron": 5000, "pop": 5000, "factor": 1.26},
    BuildingType.CHURCH_F: {"wood": 160, "stone": 200, "iron": 50, "pop": 5, "factor": 1.0},
    BuildingType.SNOB: {"wood": 15000, "stone": 25000, "iron": 10000, "pop": 80, "factor": 2.0},
    BuildingType.SMITH: {"wood": 220, "stone": 180, "iron": 240, "pop": 20, "factor": 1.26},
    BuildingType.PLACE: {"wood": 10, "stone": 40, "iron": 10, "pop": 0, "factor": 1.0},
    BuildingType.STATUE: {"wood": 220, "stone": 220, "iron": 220, "pop": 10, "factor": 1.0},
    BuildingType.MARKET: {"wood": 100, "stone": 100, "iron": 100, "pop": 20, "factor": 1.2},
    BuildingType.FARM: {"wood": 45, "stone": 40, "iron": 30, "pop": 0, "factor": 1.3},
    BuildingType.STORAGE: {"wood": 60, "stone": 50, "iron": 40, "pop": 0, "factor": 1.265},
    BuildingType.HIDE: {"wood": 50, "stone": 60, "iron": 50, "pop": 2, "factor": 1.25},
    BuildingType.WALL: {"wood": 50, "stone": 100, "iron": 20, "pop": 5, "factor": 1.26},
}


def estimate_building_cost(building: str, target_level: int) -> Tuple[int, int, int, int]:
    """Calcula os custos estimados (madeira, argila, ferro, população) para o nível pretendido."""
    base = BASE_BUILDING_COSTS.get(building, {"wood": 100, "stone": 100, "iron": 100, "pop": 5, "factor": 1.25})
    factor = float(base.get("factor", 1.25))
    lvl_exp = max(0, target_level - 1)
    wood = int(round(base["wood"] * (factor ** lvl_exp)))
    stone = int(round(base["stone"] * (factor ** lvl_exp)))
    iron = int(round(base["iron"] * (factor ** lvl_exp)))
    pop = int(round(base.get("pop", 5) * (1.17 ** lvl_exp)))
    return wood, stone, iron, pop


@dataclass
class QueueOrder:
    """Representação de uma construção em andamento na fila do Edifício Principal."""
    order_id: str
    building: str
    building_name: str
    target_level: int
    timer_str: str = ""
    timer_seconds: Optional[int] = None
    cancel_url: str = ""
    instant_build_url: Optional[str] = None

    @property
    def is_instant_free_ready(self) -> bool:
        """Verifica se a ordem pode ser concluída gratuitamente (< 3 min = 180s ou link presente)."""
        if self.instant_build_url:
            return True
        if self.timer_seconds is not None and 0 < self.timer_seconds <= 180:
            return True
        return False


# Tabela canónica de cadeias de pré-requisitos para desbloqueio militar prioritário
MILITARY_PREREQUISITE_CHAINS: Dict[str, List[Tuple[str, int]]] = {
    "axe": [
        (BuildingType.MAIN, 3),
        (BuildingType.BARRACKS, 1),
        (BuildingType.MAIN, 5),
        (BuildingType.SMITH, 1),
        (BuildingType.BARRACKS, 2),
        (BuildingType.SMITH, 2),
    ],
    "light": [
        (BuildingType.MAIN, 3),
        (BuildingType.BARRACKS, 1),
        (BuildingType.MAIN, 5),
        (BuildingType.SMITH, 1),
        (BuildingType.BARRACKS, 5),
        (BuildingType.SMITH, 5),
        (BuildingType.MAIN, 10),
        (BuildingType.STABLE, 1),
        (BuildingType.STABLE, 2),
        (BuildingType.STABLE, 3),
    ],
    "spy": [
        (BuildingType.MAIN, 3),
        (BuildingType.BARRACKS, 1),
        (BuildingType.MAIN, 5),
        (BuildingType.SMITH, 1),
        (BuildingType.BARRACKS, 5),
        (BuildingType.SMITH, 5),
        (BuildingType.MAIN, 10),
        (BuildingType.STABLE, 1),
    ],
    "ram": [
        (BuildingType.MAIN, 3),
        (BuildingType.BARRACKS, 1),
        (BuildingType.MAIN, 5),
        (BuildingType.SMITH, 1),
        (BuildingType.MAIN, 10),
        (BuildingType.SMITH, 10),
        (BuildingType.GARAGE, 1),
    ],
    "catapult": [
        (BuildingType.MAIN, 3),
        (BuildingType.BARRACKS, 1),
        (BuildingType.MAIN, 5),
        (BuildingType.SMITH, 1),
        (BuildingType.MAIN, 10),
        (BuildingType.SMITH, 10),
        (BuildingType.GARAGE, 1),
        (BuildingType.GARAGE, 2),
        (BuildingType.SMITH, 12),
    ],
    "heavy": [
        (BuildingType.MAIN, 3),
        (BuildingType.BARRACKS, 1),
        (BuildingType.MAIN, 5),
        (BuildingType.SMITH, 1),
        (BuildingType.BARRACKS, 5),
        (BuildingType.SMITH, 5),
        (BuildingType.MAIN, 10),
        (BuildingType.STABLE, 1),
        (BuildingType.STABLE, 10),
        (BuildingType.SMITH, 15),
    ],
}


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
    is_rush: bool = False



# Aliases para compatibilidade
BuildingQueueItem = QueueOrder
BuildingUpgradeInfo = BuildingUpgrade


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


# Modelo Oficial Padrão de Construção (Baseado na estratégia otimizada do config.json - 268 passos)
DEFAULT_BUILD_PLAN: List[Tuple[str, int]] = [
    (BuildingType.WOOD, 1),
    (BuildingType.STONE, 1),
    (BuildingType.IRON, 1),
    (BuildingType.WOOD, 2),
    (BuildingType.STONE, 2),
    (BuildingType.WOOD, 3),
    (BuildingType.STONE, 3),
    (BuildingType.MAIN, 2),
    (BuildingType.MAIN, 3),
    (BuildingType.BARRACKS, 1),
    (BuildingType.WOOD, 4),
    (BuildingType.STONE, 4),
    (BuildingType.IRON, 2),
    (BuildingType.FARM, 2),
    (BuildingType.WOOD, 5),
    (BuildingType.STONE, 5),
    (BuildingType.IRON, 3),
    (BuildingType.STORAGE, 2),
    (BuildingType.WOOD, 6),
    (BuildingType.STONE, 6),
    (BuildingType.IRON, 4),
    (BuildingType.FARM, 3),
    (BuildingType.MAIN, 4),
    (BuildingType.MAIN, 5),
    (BuildingType.STORAGE, 3),
    (BuildingType.SMITH, 1),
    (BuildingType.WOOD, 7),
    (BuildingType.STONE, 7),
    (BuildingType.IRON, 5),
    (BuildingType.STORAGE, 4),
    (BuildingType.FARM, 4),
    (BuildingType.WOOD, 8),
    (BuildingType.STONE, 8),
    (BuildingType.WOOD, 9),
    (BuildingType.STONE, 9),
    (BuildingType.IRON, 6),
    (BuildingType.STORAGE, 5),
    (BuildingType.MAIN, 6),
    (BuildingType.MAIN, 7),
    (BuildingType.MAIN, 8),
    (BuildingType.SMITH, 2),
    (BuildingType.SMITH, 3),
    (BuildingType.FARM, 5),
    (BuildingType.STORAGE, 6),
    (BuildingType.MAIN, 9),
    (BuildingType.MAIN, 10),
    (BuildingType.SMITH, 4),
    (BuildingType.SMITH, 5),
    (BuildingType.STORAGE, 7),
    (BuildingType.STABLE, 1),
    (BuildingType.STABLE, 2),
    (BuildingType.STABLE, 3),
    (BuildingType.FARM, 6),
    (BuildingType.STORAGE, 8),
    (BuildingType.BARRACKS, 2),
    (BuildingType.BARRACKS, 3),
    (BuildingType.BARRACKS, 4),
    (BuildingType.BARRACKS, 5),
    (BuildingType.FARM, 7),
    (BuildingType.STORAGE, 9),
    (BuildingType.STORAGE, 10),
    (BuildingType.FARM, 8),
    (BuildingType.STABLE, 4),
    (BuildingType.STABLE, 5),
    (BuildingType.FARM, 9),
    (BuildingType.FARM, 10),
    (BuildingType.STORAGE, 11),
    (BuildingType.STORAGE, 12),
    (BuildingType.WOOD, 10),
    (BuildingType.STONE, 10),
    (BuildingType.IRON, 7),
    (BuildingType.IRON, 8),
    (BuildingType.WALL, 1),
    (BuildingType.WALL, 2),
    (BuildingType.WALL, 3),
    (BuildingType.WALL, 4),
    (BuildingType.WALL, 5),
    (BuildingType.MAIN, 11),
    (BuildingType.MAIN, 12),
    (BuildingType.MAIN, 13),
    (BuildingType.MAIN, 14),
    (BuildingType.MAIN, 15),
    (BuildingType.MAIN, 16),
    (BuildingType.MAIN, 17),
    (BuildingType.MAIN, 18),
    (BuildingType.MAIN, 19),
    (BuildingType.MAIN, 20),
    (BuildingType.GARAGE, 1),
    (BuildingType.GARAGE, 2),
    (BuildingType.GARAGE, 3),
    (BuildingType.GARAGE, 4),
    (BuildingType.GARAGE, 5),
    (BuildingType.MARKET, 1),
    (BuildingType.MARKET, 2),
    (BuildingType.MARKET, 3),
    (BuildingType.MARKET, 4),
    (BuildingType.MARKET, 5),
    (BuildingType.MARKET, 6),
    (BuildingType.MARKET, 7),
    (BuildingType.MARKET, 8),
    (BuildingType.MARKET, 9),
    (BuildingType.MARKET, 10),
    (BuildingType.SMITH, 6),
    (BuildingType.SMITH, 7),
    (BuildingType.SMITH, 8),
    (BuildingType.SMITH, 9),
    (BuildingType.SMITH, 10),
    (BuildingType.SMITH, 11),
    (BuildingType.SMITH, 12),
    (BuildingType.SMITH, 13),
    (BuildingType.SMITH, 14),
    (BuildingType.SMITH, 15),
    (BuildingType.SMITH, 16),
    (BuildingType.SMITH, 17),
    (BuildingType.SMITH, 18),
    (BuildingType.SMITH, 19),
    (BuildingType.SMITH, 20),
    (BuildingType.STORAGE, 13),
    (BuildingType.STORAGE, 14),
    (BuildingType.STORAGE, 15),
    (BuildingType.STORAGE, 16),
    (BuildingType.STORAGE, 17),
    (BuildingType.STORAGE, 18),
    (BuildingType.STORAGE, 19),
    (BuildingType.STORAGE, 20),
    (BuildingType.FARM, 11),
    (BuildingType.FARM, 12),
    (BuildingType.FARM, 13),
    (BuildingType.FARM, 14),
    (BuildingType.FARM, 15),
    (BuildingType.SNOB, 1),
    (BuildingType.BARRACKS, 6),
    (BuildingType.BARRACKS, 7),
    (BuildingType.BARRACKS, 8),
    (BuildingType.BARRACKS, 9),
    (BuildingType.BARRACKS, 10),
    (BuildingType.STABLE, 6),
    (BuildingType.STABLE, 7),
    (BuildingType.STABLE, 8),
    (BuildingType.STABLE, 9),
    (BuildingType.STABLE, 10),
    (BuildingType.FARM, 16),
    (BuildingType.FARM, 17),
    (BuildingType.FARM, 18),
    (BuildingType.FARM, 19),
    (BuildingType.FARM, 20),
    (BuildingType.WALL, 6),
    (BuildingType.WALL, 7),
    (BuildingType.WALL, 8),
    (BuildingType.WALL, 9),
    (BuildingType.WALL, 10),
    (BuildingType.WALL, 11),
    (BuildingType.WALL, 12),
    (BuildingType.WALL, 13),
    (BuildingType.WALL, 14),
    (BuildingType.WALL, 15),
    (BuildingType.WOOD, 11),
    (BuildingType.WOOD, 12),
    (BuildingType.WOOD, 13),
    (BuildingType.WOOD, 14),
    (BuildingType.WOOD, 15),
    (BuildingType.STONE, 11),
    (BuildingType.STONE, 12),
    (BuildingType.STONE, 13),
    (BuildingType.STONE, 14),
    (BuildingType.STONE, 15),
    (BuildingType.IRON, 9),
    (BuildingType.IRON, 10),
    (BuildingType.IRON, 11),
    (BuildingType.IRON, 12),
    (BuildingType.IRON, 13),
    (BuildingType.IRON, 14),
    (BuildingType.IRON, 15),
    (BuildingType.BARRACKS, 11),
    (BuildingType.BARRACKS, 12),
    (BuildingType.BARRACKS, 13),
    (BuildingType.BARRACKS, 14),
    (BuildingType.BARRACKS, 15),
    (BuildingType.BARRACKS, 16),
    (BuildingType.BARRACKS, 17),
    (BuildingType.BARRACKS, 18),
    (BuildingType.BARRACKS, 19),
    (BuildingType.BARRACKS, 20),
    (BuildingType.STABLE, 11),
    (BuildingType.STABLE, 12),
    (BuildingType.STABLE, 13),
    (BuildingType.STABLE, 14),
    (BuildingType.STABLE, 15),
    (BuildingType.FARM, 21),
    (BuildingType.FARM, 22),
    (BuildingType.FARM, 23),
    (BuildingType.FARM, 24),
    (BuildingType.FARM, 25),
    (BuildingType.STORAGE, 21),
    (BuildingType.STORAGE, 22),
    (BuildingType.STORAGE, 23),
    (BuildingType.STORAGE, 24),
    (BuildingType.STORAGE, 25),
    (BuildingType.WOOD, 16),
    (BuildingType.WOOD, 17),
    (BuildingType.WOOD, 18),
    (BuildingType.WOOD, 19),
    (BuildingType.WOOD, 20),
    (BuildingType.WOOD, 21),
    (BuildingType.WOOD, 22),
    (BuildingType.WOOD, 23),
    (BuildingType.WOOD, 24),
    (BuildingType.WOOD, 25),
    (BuildingType.STONE, 16),
    (BuildingType.STONE, 17),
    (BuildingType.STONE, 18),
    (BuildingType.STONE, 19),
    (BuildingType.STONE, 20),
    (BuildingType.STONE, 21),
    (BuildingType.STONE, 22),
    (BuildingType.STONE, 23),
    (BuildingType.STONE, 24),
    (BuildingType.STONE, 25),
    (BuildingType.IRON, 16),
    (BuildingType.IRON, 17),
    (BuildingType.IRON, 18),
    (BuildingType.IRON, 19),
    (BuildingType.IRON, 20),
    (BuildingType.IRON, 21),
    (BuildingType.IRON, 22),
    (BuildingType.IRON, 23),
    (BuildingType.IRON, 24),
    (BuildingType.IRON, 25),
    (BuildingType.WALL, 16),
    (BuildingType.WALL, 17),
    (BuildingType.WALL, 18),
    (BuildingType.WALL, 19),
    (BuildingType.WALL, 20),
    (BuildingType.BARRACKS, 21),
    (BuildingType.BARRACKS, 22),
    (BuildingType.BARRACKS, 23),
    (BuildingType.BARRACKS, 24),
    (BuildingType.BARRACKS, 25),
    (BuildingType.STABLE, 16),
    (BuildingType.STABLE, 17),
    (BuildingType.STABLE, 18),
    (BuildingType.STABLE, 19),
    (BuildingType.STABLE, 20),
    (BuildingType.WOOD, 26),
    (BuildingType.WOOD, 27),
    (BuildingType.WOOD, 28),
    (BuildingType.WOOD, 29),
    (BuildingType.WOOD, 30),
    (BuildingType.STONE, 26),
    (BuildingType.STONE, 27),
    (BuildingType.STONE, 28),
    (BuildingType.STONE, 29),
    (BuildingType.STONE, 30),
    (BuildingType.IRON, 26),
    (BuildingType.IRON, 27),
    (BuildingType.IRON, 28),
    (BuildingType.IRON, 29),
    (BuildingType.IRON, 30),
    (BuildingType.STORAGE, 26),
    (BuildingType.STORAGE, 27),
    (BuildingType.STORAGE, 28),
    (BuildingType.STORAGE, 29),
    (BuildingType.STORAGE, 30),
    (BuildingType.FARM, 26),
    (BuildingType.FARM, 27),
    (BuildingType.FARM, 28),
    (BuildingType.FARM, 29),
    (BuildingType.FARM, 30),
]

# Alias canónico para o modelo padrão
DEFAULT_BUILDING_TEMPLATE = DEFAULT_BUILD_PLAN


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
                    timer_seconds=q.get("timer_seconds"),
                    cancel_url=str(q.get("cancel_url", "")),
                    instant_build_url=q.get("instant_build_url"),
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
        build_url: Optional[str] = None,
    ) -> bool:
        """
        Executa a ordem de construção de um edifício no Edifício Principal.
        Envia a requisição com injeção do token CSRF 'h', 'page=mobile' e headers móveis.
        Verifica rigorosamente se a ordem foi adicionada à fila do jogo.
        """
        b_canon = self.normalize_building_id(building)
        b_name = BUILDING_NAMES.get(b_canon, b_canon)
        logger.info(
            f"[{account.world}] 🔨 A enviar ordem de construção para: '{b_name}' ({b_canon})"
        )

        try:
            # 1. Parâmetros padrão de melhoria (action=build é o padrão nativo do Tribal Wars)
            extra_params: Dict[str, Any] = {
                "action": "build",
                "id": b_canon,
                "force": "1" if force else "0",
            }
            if account.csrf_token:
                extra_params["h"] = account.csrf_token

            # Se build_url fornecido pelo parser contiver parâmetros específicos (ex: extraído do jogo)
            if build_url and "?" in build_url:
                try:
                    parsed_url = urllib.parse.urlparse(build_url)
                    parsed_qs = urllib.parse.parse_qs(parsed_url.query)
                    for k, v in parsed_qs.items():
                        if v and k not in ("village", "screen"):
                            extra_params[k] = v[0]
                except Exception as parse_err:
                    logger.debug(f"[{account.world}] Erro ao parsear build_url '{build_url}': {parse_err}")

            if account.csrf_token and "h" not in extra_params:
                extra_params["h"] = account.csrf_token

            html = await account.get_screen(
                screen="main",
                village_id=village_id,
                extra_params=extra_params,
                apply_jitter=True,
            )

            # Verifica se o edifício entrou na fila
            queue = parse_build_queue(html)
            in_queue = any(
                q.get("building") == b_canon
                or self.normalize_building_id(q.get("building_raw", "")) == b_canon
                or q.get("building_raw") == b_name
                for q in queue
            )

            if not in_queue:
                # 2. Fallback resiliente: alguns mundos/versões utilizam action=upgrade_building
                alt_action = "upgrade_building" if extra_params.get("action") == "build" else "build"
                logger.debug(
                    f"[{account.world}] Ordem não confirmada na fila com action={extra_params.get('action')}. "
                    f"A tentar fallback com action={alt_action} para '{b_canon}'..."
                )
                extra_params["action"] = alt_action
                html = await account.get_screen(
                    screen="main",
                    village_id=village_id,
                    extra_params=extra_params,
                    apply_jitter=True,
                )
                queue = parse_build_queue(html)
                in_queue = any(
                    q.get("building") == b_canon
                    or self.normalize_building_id(q.get("building_raw", "")) == b_canon
                    or q.get("building_raw") == b_name
                    for q in queue
                )

            if not in_queue:
                # 3. Fallback POST: mundos com proteção CSRF estrita via requisição POST
                logger.debug(
                    f"[{account.world}] A tentar envio de ordem de construção via POST para '{b_canon}'..."
                )
                post_data = {
                    "action": "build",
                    "id": b_canon,
                    "force": "1" if force else "0",
                }
                if account.csrf_token:
                    post_data["h"] = account.csrf_token
                try:
                    html = await account.post_action(
                        screen="main",
                        action="build",
                        post_data=post_data,
                        village_id=village_id,
                    )
                    queue = parse_build_queue(html)
                    in_queue = any(
                        q.get("building") == b_canon
                        or self.normalize_building_id(q.get("building_raw", "")) == b_canon
                        or q.get("building_raw") == b_name
                        for q in queue
                    )
                except Exception as post_err:
                    logger.debug(f"[{account.world}] Fallback POST falhou: {post_err}")

            if in_queue or len(queue) > 0:
                logger.info(
                    f"[{account.world}] ✅ Ordem para '{b_name}' ({b_canon}) confirmada na fila! "
                    f"Itens em fila: {len(queue)}"
                )
                return True
            else:
                # Deteção de mensagens de erro do jogo no HTML
                err_msg = "Não entrou na fila de construção"
                if "Não há recursos suficientes" in html or "Recursos insuficientes" in html:
                    err_msg = "Recursos insuficientes"
                elif "Armazém muito pequeno" in html:
                    err_msg = "Armazém muito pequeno"
                elif "Fila de construção cheia" in html:
                    err_msg = "Fila de construção cheia"
                elif "População máxima atingida" in html or "precisa de mais fazenda" in html.lower():
                    err_msg = "População insuficiente"
                elif "Edifício totalmente construído" in html:
                    err_msg = "Nível máximo já atingido"
                elif "Requisitos não preenchidos" in html:
                    err_msg = "Requisitos tecnológicos não preenchidos"

                logger.warning(
                    f"[{account.world}] ⚠️ Ordem para '{b_name}' ({b_canon}) NÃO foi colocada na fila. Motivo: {err_msg}."
                )
                return False

        except Exception as e:
            logger.error(f"[{account.world}] ❌ Falha ao construir '{b_canon}': {e}")
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

    def get_prerequisite_rush_steps(
        self,
        recruitment_targets: Optional[Dict[str, int]],
        virtual_levels: Dict[str, int],
    ) -> List[Tuple[str, int]]:
        """
        Gera a lista de passos de construção prioritários necessários para desbloquear
        as unidades ativas configuradas no recrutamento (ex: Vikings e Cavalaria Leve / CL).
        Se o Quartel ou Estábulo estiverem parados por falta de requisitos, estes passos
        assumem prioridade máxima sobre o plano normal de construção.
        """
        if not recruitment_targets:
            return []

        rush_steps: List[Tuple[str, int]] = []
        seen = set()

        # Priorização máxima: Vikings (axe) e Cavalaria Leve (light)
        priority_units = []
        if recruitment_targets.get("axe", 0) > 0 or recruitment_targets.get("viking", 0) > 0 or recruitment_targets.get("bárbaro", 0) > 0:
            priority_units.append("axe")
        if recruitment_targets.get("light", 0) > 0 or recruitment_targets.get("cavalaria leve", 0) > 0 or recruitment_targets.get("cav_leve", 0) > 0:
            priority_units.append("light")

        for u, count in recruitment_targets.items():
            u_clean = u.lower().strip()
            if count > 0 and u_clean in MILITARY_PREREQUISITE_CHAINS and u_clean not in priority_units:
                priority_units.append(u_clean)

        for u in priority_units:
            chain = MILITARY_PREREQUISITE_CHAINS.get(u, [])
            for b_name, req_lvl in chain:
                b_canon = self.normalize_building_id(b_name)
                curr_virt = virtual_levels.get(b_canon, 0)
                if curr_virt < req_lvl:
                    step_key = (b_canon, req_lvl)
                    if step_key not in seen:
                        seen.add(step_key)
                        rush_steps.append(step_key)

        return rush_steps

    def get_next_build_candidate(
        self,
        state: MainBuildingState,
        plan: List[Tuple[str, int]],
        resources: Resources,
        max_queue: Optional[int] = None,
        recruitment_targets: Optional[Dict[str, int]] = None,
    ) -> Optional[BuildingUpgrade]:
        """
        Avalia o plano de construção e o estado atual da aldeia para encontrar
        o próximo edifício elegível para evolução.
        Prioriza com prioridade máxima o Rush de Pré-Requisitos Militares se houver
        tropas configuradas (ex: Vikings e CL) com requisitos em falta.
        """
        limit = max_queue if max_queue is not None else state.max_queue_size
        if state.queue_count >= limit:
            logger.info(
                f"Fila de construção cheia ({state.queue_count}/{limit}). "
                f"A aguardar conclusão da ordem em andamento."
            )
            return None

        virt_levels = state.virtual_levels

        # 1. RUSH DE PRÉ-REQUISITOS MILITARES (Prioridade Máxima)
        rush_steps = self.get_prerequisite_rush_steps(recruitment_targets, virt_levels)
        if rush_steps:
            for b_raw, target_lvl in rush_steps:
                b = self.normalize_building_id(b_raw)
                current_virt = virt_levels.get(b, 0)

                if current_virt < target_lvl:
                    # Verifica se os pré-requisitos para este degrau estão satisfeitos
                    if not self.are_requirements_met(b, virt_levels):
                        continue

                    max_lvl = MAX_BUILDING_LEVELS.get(b, 30)
                    if current_virt >= max_lvl:
                        continue

                    curr_real = state.buildings.get(b, 0)
                    if current_virt > curr_real or b not in state.upgrades:
                        e_wood, e_stone, e_iron, e_pop = estimate_building_cost(b, current_virt + 1)
                        upgrade_info = BuildingUpgrade(
                            building=b,
                            current_level=current_virt,
                            target_level=current_virt + 1,
                            wood=e_wood,
                            stone=e_stone,
                            iron=e_iron,
                            pop=e_pop,
                            can_build=True,
                            is_rush=True,
                        )
                    else:
                        upgrade_info = state.upgrades[b]
                        upgrade_info.is_rush = True

                    b_name = BUILDING_NAMES.get(b, b)
                    # Verifica se armazém suporta o custo
                    if (
                        resources.storage_max > 0
                        and (
                            upgrade_info.wood > resources.storage_max
                            or upgrade_info.stone > resources.storage_max
                            or upgrade_info.iron > resources.storage_max
                        )
                    ):
                        logger.warning(
                            f"[{state.village_id}] ⚠️ Armazém ({resources.storage_max}) insuficiente para "
                            f"RUSH de '{b_name}' Nível {current_virt + 1}."
                        )
                        continue

                    if resources.can_afford(
                        wood=upgrade_info.wood,
                        stone=upgrade_info.stone,
                        iron=upgrade_info.iron,
                        pop=upgrade_info.pop,
                    ):
                        logger.info(
                            f"[{state.village_id}] ⚡ [RUSH MILITAR ATIVADO] Prioridade máxima: "
                            f"'{b_name}' ({b}) para Nível {current_virt + 1} para desbloquear tropas!"
                        )
                        return upgrade_info
                    else:
                        logger.info(
                            f"[{state.village_id}] ⏳ [RUSH MILITAR EM ESPERA] A aguardar recursos para "
                            f"'{b_name}' ({b}) Nível {current_virt + 1} (Requisitos de recrutamento prioritário). "
                            f"Recursos: {resources.wood}/{upgrade_info.wood} M, "
                            f"{resources.stone}/{upgrade_info.stone} A, {resources.iron}/{upgrade_info.iron} F."
                        )
                        return None

        # 2. PLANO REGULAR DE CONSTRUÇÃO
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
                curr_real = state.buildings.get(b, 0)
                if current_virt > curr_real or b not in state.upgrades:
                    e_wood, e_stone, e_iron, e_pop = estimate_building_cost(b, current_virt + 1)
                    upgrade_info = BuildingUpgrade(
                        building=b,
                        current_level=current_virt,
                        target_level=current_virt + 1,
                        wood=e_wood,
                        stone=e_stone,
                        iron=e_iron,
                        pop=e_pop,
                        can_build=True,
                    )
                else:
                    upgrade_info = state.upgrades[b]

                # Verifica se a capacidade máxima de armazém comporta o custo
                if (
                    resources.storage_max > 0
                    and (
                        upgrade_info.wood > resources.storage_max
                        or upgrade_info.stone > resources.storage_max
                        or upgrade_info.iron > resources.storage_max
                    )
                ):
                    b_name = BUILDING_NAMES.get(b, b)
                    logger.warning(
                        f"[{state.village_id}] Armazém ({resources.storage_max}) insuficiente para "
                        f"'{b_name}' Nível {current_virt + 1} (Custo máx: {max(upgrade_info.wood, upgrade_info.stone, upgrade_info.iron)})."
                    )
                    continue

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

        if not any_unreached:
            logger.info(f"Todas as {len(plan)} metas do plano de construção ativo foram alcançadas!")
        else:
            logger.debug("Existem metas pendentes no plano que ainda aguardam pré-requisitos.")
        return None

    def get_upcoming_plan(
        self,
        state: MainBuildingState,
        plan: List[Tuple[str, int]],
        resources: Optional[Resources] = None,
    ) -> List[Dict[str, Any]]:
        """
        Calcula a lista detalhada de passos do plano de construção,
        indicando para cada um se está concluído, em andamento na fila,
        se é o próximo alvo imediato ou pendente.
        """
        items: List[Dict[str, Any]] = []
        virt_levels = state.virtual_levels.copy()
        found_next = False

        # Mapeia ordens da fila para consulta rápida: (building, target_level)
        queue_map = {(q.building, q.target_level): q for q in state.queue}

        for idx, (b_raw, target_lvl) in enumerate(plan):
            b = self.normalize_building_id(b_raw)
            b_name = BUILDING_NAMES.get(b, b)
            curr_lvl = state.buildings.get(b, 0)
            virt_lvl = virt_levels.get(b, 0)

            status = "pending"
            missing_reqs = []
            upgrade_info = state.upgrades.get(b)

            if curr_lvl >= target_lvl:
                status = "completed"
            elif (b, target_lvl) in queue_map:
                status = "in_progress"
            else:
                # Verifica pré-requisitos com base nos níveis virtuais
                reqs = BUILDING_REQUIREMENTS.get(b, {})
                for req_b, req_lvl in reqs.items():
                    if virt_levels.get(req_b, 0) < req_lvl:
                        req_name = BUILDING_NAMES.get(req_b, req_b)
                        missing_reqs.append(f"{req_name} Nível {req_lvl}")

                if missing_reqs:
                    status = "blocked"
                elif not found_next:
                    status = "next"
                    found_next = True

            # Custos estimados
            if upgrade_info and curr_lvl == target_lvl - 1:
                wood = upgrade_info.wood
                stone = upgrade_info.stone
                iron = upgrade_info.iron
                pop = upgrade_info.pop
            else:
                wood, stone, iron, pop = estimate_building_cost(b, target_lvl)

            can_afford = False
            if resources:
                can_afford = resources.can_afford(wood, stone, iron, pop)

            items.append({
                "step": idx + 1,
                "building": b,
                "building_name": b_name,
                "target_level": target_lvl,
                "current_level": curr_lvl,
                "virtual_level": virt_lvl,
                "status": status,
                "wood": wood,
                "stone": stone,
                "iron": iron,
                "pop": pop,
                "can_afford": can_afford,
                "missing_requirements": missing_reqs,
            })

        return items

    async def check_and_complete_instant_builds(
        self, account: TribalAccount, village_id: Optional[int] = None
    ) -> List[str]:
        """
        Verifica a fila de construção e executa a conclusão gratuita imediata
        para qualquer ordem com menos de 3 minutos restantes (180s) ou botão de conclusão grátis.
        """
        completed: List[str] = []
        v_id = village_id or account.current_village_id or 0
        try:
            state = await self.get_state(account, village_id=v_id)
            for order in state.queue:
                if order.is_instant_free_ready:
                    logger.info(
                        f"[{account.world}] ⚡ A executar conclusão gratuita (< 3 min) para '{order.building_name}' (Ordem #{order.order_id}, Restante: {order.timer_str or f'{order.timer_seconds}s'})..."
                    )
                    success = False
                    if order.instant_build_url:
                        url = order.instant_build_url
                        if "h=" not in url and account.csrf_token:
                            sep = "&" if "?" in url else "?"
                            url = f"{url}{sep}h={account.csrf_token}"
                        full_url = url if url.startswith("http") else f"https://{account.host}/{url.lstrip('/')}"
                        try:
                            await account.get(full_url, apply_jitter=True)
                            success = True
                        except Exception as e:
                            logger.debug(f"Erro ao concluir via URL: {e}")

                    if not success:
                        try:
                            extra_params = {
                                "action": "instant_build",
                                "id": order.order_id,
                                "h": account.csrf_token or "",
                            }
                            await account.get_screen("main", village_id=v_id, extra_params=extra_params, apply_jitter=True)
                            success = True
                        except Exception as e2:
                            logger.debug(f"Erro ao concluir via action=instant_build: {e2}")

                    if success:
                        completed.append(order.building)
                        logger.info(
                            f"[{account.world}] ✅ Construção de '{order.building_name}' concluída instantaneamente com sucesso!"
                        )
                        await asyncio.sleep(0.3)
        except Exception as e:
            logger.debug(f"Erro ao verificar conclusões instantâneas: {e}")
        return completed

    async def run_auto_build_cycle(
        self,
        account: TribalAccount,
        plan: List[Tuple[str, int]],
        max_queue: Optional[int] = None,
        village_id: Optional[int] = None,
        recruitment_targets: Optional[Dict[str, int]] = None,
    ) -> Optional[str]:
        """
        Executa um ciclo completo de verificação e evolução automática:
        1. Executa conclusão gratuita (< 3 min) se houver ordens prontas.
        2. Obtém o estado do Edifício Principal.
        3. Avalia o próximo candidato conforme o plano e recursos disponíveis,
           priorizando com máxima urgência os pré-requisitos de tropas configuradas (Vikings, CL).
        4. Envia o comando de construção e avança na fila até ao limite configurado.
        Retorna o identificador do último edifício colocado na fila, ou None.
        """
        v_id = village_id or account.current_village_id or 0

        # Se não foram fornecidas metas explícitas, tenta obter da configuração da aldeia
        if recruitment_targets is None:
            if hasattr(account, "config") and account.config:
                try:
                    recruitment_targets = account.config.get_village_recruitment_targets(v_id)
                except Exception as e:
                    logger.debug(f"Aviso ao obter metas de recrutamento para auto-build rush: {e}")
            if recruitment_targets is None:
                try:
                    from engine.config.settings import load_config
                    cfg = load_config()
                    recruitment_targets = cfg.get_village_recruitment_targets(v_id)
                except Exception as e:
                    logger.debug(f"Aviso ao carregar config para rush militar: {e}")

        # 1. Verifica e conclui ordens gratuitas (< 3 min)
        await self.check_and_complete_instant_builds(account, village_id=v_id)

        state = await self.get_state(account, village_id=v_id)
        limit = max_queue if max_queue is not None else state.max_queue_size
        logger.info(
            f"[{account.world}] A avaliar Edifício Principal (Aldeia {v_id}, Fila: {state.queue_count}/{limit})."
        )

        last_built = None
        while state.queue_count < limit:
            curr_v = account.villages.get(v_id) if v_id else account.current_village
            resources = curr_v.resources if curr_v else account.resources

            candidate = self.get_next_build_candidate(
                state=state,
                plan=plan,
                resources=resources,
                max_queue=limit,
                recruitment_targets=recruitment_targets,
            )

            if not candidate:
                break

            success = await self.build_building(
                account=account,
                building=candidate.building,
                village_id=v_id,
                build_url=getattr(candidate, "build_url", None),
            )

            if success:
                last_built = candidate.building
                b_name = BUILDING_NAMES.get(candidate.building, candidate.building)
                logger.info(
                    f"[{account.world}] ✅ Sucesso ao colocar na fila: "
                    f"'{b_name}' para Nível {candidate.target_level}!"
                )
                # Se ainda houver vagas, re-lê o estado para avançar com o próximo do plano
                if state.queue_count + 1 < limit:
                    state = await self.get_state(account, village_id=v_id)
                else:
                    break
            else:
                break

        # Se os requisitos de tropas foram concluídos e o Ferreiro existe, dispara auto-pesquisa imediata
        if recruitment_targets and state.levels.get("smith", 0) >= 1:
            try:
                from engine.actions.smith import SmithManager
                smith_mgr = getattr(self, "smith_manager", None) or SmithManager()
                await smith_mgr.auto_research_needed_units(
                    account=account,
                    village_id=v_id,
                    needed_units=[u for u, cnt in recruitment_targets.items() if cnt > 0],
                )
            except Exception as e:
                logger.debug(f"Aviso ao verificar auto-pesquisa no ciclo de construção: {e}")

        return last_built

    # Alias para compatibilidade de API
    run_build_cycle = run_auto_build_cycle

    def schedule_auto_build(
        self,
        scheduler: TaskScheduler,
        account: TribalAccount,
        plan: List[Tuple[str, int]],
        max_queue: int = 2,
        village_id: Optional[int] = None,
        interval_seconds: float = 60.0,
        enabled_check: Optional[Callable[[], bool]] = None,
        bot_config: Optional[Any] = None,
    ) -> None:
        logger.info(
            f"[{account.world}] Construção Automática agendada a cada ~{interval_seconds}s "
            f"(Aldeia: {village_id or 'ativa'}, {len(plan)} passos no plano)."
        )

        async def auto_build_task():
            if enabled_check and not enabled_check():
                return

            try:
                # Atualiza recursos antes de tentar construir
                await account.refresh_state(village_id=village_id)
                v_id = village_id or account.current_village_id or 0
                rec_targets = None
                if bot_config and hasattr(bot_config, "get_village_recruitment_targets"):
                    rec_targets = bot_config.get_village_recruitment_targets(v_id)
                elif hasattr(account, "config") and account.config:
                    rec_targets = account.config.get_village_recruitment_targets(v_id)

                await self.run_auto_build_cycle(
                    account=account,
                    plan=plan,
                    max_queue=max_queue,
                    village_id=village_id,
                    recruitment_targets=rec_targets,
                )
            except (BotProtectionError, SessionExpiredError):
                raise
            except Exception as e:
                logger.warning(f"Erro no ciclo de auto-build: {e}")
            finally:
                # Reagenda continuamente para o próximo ciclo se o motor estiver em execução
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
            delay_seconds=3.0,
        )

