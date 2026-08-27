"""
Tribal Wars Mobile Automation Engine - Modelos de Dados
Estruturas de dados fortemente tipadas para representar recursos, aldeias, jogadores e tarefas.
"""

from dataclasses import dataclass, field
from enum import IntEnum
import time
from typing import Any, Callable, Coroutine, Dict, Optional


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
        return (
            self.wood >= wood
            and self.stone >= stone
            and self.iron >= iron
            and self.free_pop >= pop
        )


@dataclass
class VillageData:
    """Representação de uma aldeia associada à conta."""

    id: int
    name: str = ""
    x: int = 0
    y: int = 0
    points: int = 0
    resources: Resources = field(default_factory=Resources)

    @property
    def coordinates(self) -> str:
        return f"{self.x}|{self.y}"


@dataclass
class PlayerData:
    """Informações básicas do jogador autenticado."""

    id: int = 0
    name: str = ""
    points: int = 0
    villages_count: int = 0


@dataclass(order=True)
class Task:
    """
    Representação de uma tarefa na fila de prioridades (asyncio.PriorityQueue).
    A ordenação é baseada em:
    1. Prioridade (menor número tem precedência).
    2. scheduled_at (timestamp de execução com delay humano).
    """

    priority: int
    scheduled_at: float
    name: str = field(compare=False)
    id: str = field(compare=False, default="")
    action: Optional[Callable[..., Coroutine[Any, Any, Any]]] = field(
        compare=False, default=None
    )
    args: tuple = field(compare=False, default_factory=tuple)
    kwargs: Dict[str, Any] = field(compare=False, default_factory=dict)
    retry_count: int = field(compare=False, default=0)
    max_retries: int = field(compare=False, default=3)
    metadata: Dict[str, Any] = field(compare=False, default_factory=dict)

    def is_due(self) -> bool:
        """Indica se a tarefa está pronta para execução imediata."""
        return time.monotonic() >= self.scheduled_at

    def time_until_due(self) -> float:
        """Tempo restante em segundos até a execução agendada."""
        return max(0.0, self.scheduled_at - time.monotonic())
