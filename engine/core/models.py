"""
Tribal Wars Mobile Automation Engine - Modelos de Dados
Estruturas de dados fortemente tipadas para representar recursos, aldeias, jogadores e tarefas.
"""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
import time
from typing import Any, Callable, Coroutine, Dict, Optional, Tuple


class TaskPriority(IntEnum):
    """
    Níveis de prioridade para a fila de tarefas (menor valor = maior prioridade).
    Alertas/Defesa > Farm > Scavenging > Construção/Recrutamento > Polling.
    """

    ALERT = 0        # Emergências (ataques a chegar, alarme, desvio de tropas)
    DEFENSE = 10     # Apoios e snipes com timing crítico
    FARM = 20        # Micro-farming automatizado
    SCAVENGE = 30    # Envio de coletas (Scavenging)
    BUILD = 40       # Construção de edifícios (Edifício Principal)
    RECRUIT = 50     # Recrutamento de tropas (Quartel/Estábulo/Oficina)
    QUEST = 60       # Missões, bónus diário e inventário
    REFRESH = 90     # Atualização periódica de recursos / estado
    IDLE = 100       # Tarefas de manutenção em segundo plano
    BACKGROUND = 100 # Tarefas de fundo / keep-alive da sessão


@dataclass
class Resources:
    """Representação dos recursos atuais e capacidades da aldeia."""

    wood: int = 0
    stone: int = 0
    iron: int = 0
    storage_max: int = 0
    pop: int = 0
    pop_max: int = 0
    last_updated: float = field(default_factory=time.time)

    @property
    def free_pop(self) -> int:
        """População disponível para recrutamento/construção."""
        return max(0, self.pop_max - self.pop)

    @property
    def is_storage_full(self) -> bool:
        """Verifica se algum recurso atingiu o limite do armazém."""
        return (
            self.wood >= self.storage_max
            or self.stone >= self.storage_max
            or self.iron >= self.storage_max
        )

    def can_afford(self, wood: int = 0, stone: int = 0, iron: int = 0, pop: int = 0) -> bool:
        """Valida se a aldeia dispõe dos recursos e população necessários."""
        has_res = self.wood >= wood and self.stone >= stone and self.iron >= iron
        if not has_res:
            return False
        # Se pop_max é conhecido (> 0), valida população livre
        if self.pop_max > 0 and pop > 0:
            return self.free_pop >= pop
        return True


class VillageCategory(str, Enum):
    """Categorias de especialização tática de aldeias."""
    ATTACK = "attack"      # Aldeia ofensiva (Machados, Leves, Aríetes)
    DEFENSE = "defense"    # Aldeia defensiva (Lanças, Espadas, Pesadas, Muralha)
    BALANCED = "balanced"  # Aldeia equilibrada / mista / inicial (Recursos e misto de tropas)


# Arquétipos padrão de templates de construção por categoria
CATEGORY_BUILDING_TEMPLATES = {
    VillageCategory.ATTACK: "military_rush",
    VillageCategory.DEFENSE: "wall_focus",
    VillageCategory.BALANCED: "balanced",
}

# Arquétipos padrão de metas de recrutamento por categoria
CATEGORY_RECRUITMENT_TARGETS = {
    VillageCategory.ATTACK: {
        "axe": 500,
        "light": 250,
        "ram": 30,
        "spy": 25,
    },
    VillageCategory.DEFENSE: {
        "spear": 400,
        "sword": 400,
        "heavy": 100,
        "spy": 25,
    },
    VillageCategory.BALANCED: {
        "spear": 150,
        "sword": 150,
        "axe": 150,
        "light": 75,
        "spy": 20,
    },
}


@dataclass
class VillageData:
    """Representação de uma aldeia associada à conta."""

    id: int
    name: str = ""
    x: int = 0
    y: int = 0
    points: int = 0
    category: VillageCategory = VillageCategory.BALANCED
    resources: Resources = field(default_factory=Resources)
    troops: Dict[str, int] = field(default_factory=dict)
    buildings: Dict[str, int] = field(default_factory=dict)

    @property
    def coordinates(self) -> str:
        return f"{self.x}|{self.y}"

    @property
    def coords_tuple(self) -> Tuple[int, int]:
        return (self.x, self.y)

    def to_dict(self) -> Dict[str, Any]:
        cat_val = self.category.value if isinstance(self.category, VillageCategory) else str(self.category)
        return {
            "id": self.id,
            "name": self.name,
            "coordinates": self.coordinates,
            "x": self.x,
            "y": self.y,
            "points": self.points,
            "category": cat_val,
            "resources": {
                "wood": self.resources.wood,
                "stone": self.resources.stone,
                "iron": self.resources.iron,
                "storage_max": self.resources.storage_max,
                "pop": self.resources.pop,
                "pop_max": self.resources.pop_max,
                "free_pop": self.resources.free_pop,
            },
            "troops": self.troops,
            "buildings": self.buildings,
        }


@dataclass
class PlayerData:
    """Informações básicas do jogador autenticado."""

    id: int = 0
    name: str = ""
    points: int = 0
    villages_count: int = 0


@dataclass
class Task:
    """
    Representação de uma tarefa na fila de prioridades (asyncio.PriorityQueue).
    Ordenação inteligente:
    1. Tarefas já vencidas (due) são ordenadas estritamente por prioridade (ALERT > FARM > BUILD).
    2. Tarefas prontas têm precedência sobre tarefas agendadas para o futuro.
    3. Tarefas futuras são ordenadas pelo tempo de execução mais próximo (evita que tarefas distantes bloqueiem a fila).
    """

    priority: int
    scheduled_at: float
    name: str = ""
    id: str = ""
    action: Optional[Callable[..., Coroutine[Any, Any, Any]]] = None
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Task):
            return NotImplemented
        now = time.monotonic()
        self_due = self.scheduled_at <= now
        other_due = other.scheduled_at <= now

        # 1. Se ambas já estão prontas para execução, a prioridade tem precedência absoluta
        if self_due and other_due:
            if self.priority != other.priority:
                return self.priority < other.priority
            return self.scheduled_at < other.scheduled_at

        # 2. Se uma já está pronta e a outra é futura, a pronta vem primeiro
        if self_due != other_due:
            return self_due

        # 3. Se ambas são futuras, a que executa mais cedo vem primeiro
        if abs(self.scheduled_at - other.scheduled_at) > 0.05:
            return self.scheduled_at < other.scheduled_at

        if self.priority != other.priority:
            return self.priority < other.priority
        return self.scheduled_at < other.scheduled_at

    def time_until_due(self) -> float:
        """Tempo restante em segundos até a execução agendada."""
        return max(0.0, self.scheduled_at - time.monotonic())
