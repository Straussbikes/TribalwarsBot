"""
Tribal Wars Mobile Automation Engine - Scavenging (Coleta de Recursos)
Módulo responsável por:
1. Inspecionar o estado das 4 categorias de coleta (Lazy, Humble, Clever, Great).
2. Monitorizar expedições ativas e temporizadores de retorno.
3. Desbloquear categorias de coleta de forma inteligente.
4. Otimizar a distribuição proporcional de tropas para retorno simultâneo.
"""

from dataclasses import dataclass, field
import logging
import time
from typing import Dict, List, Optional

from engine.core.account import TribalAccount
from engine.utils.parsers import (
    parse_scavenge_available_troops,
    parse_scavenge_options,
)

logger = logging.getLogger(__name__)


@dataclass
class ScavengeOption:
    """Representação de uma das 4 categorias de Coleta de Recursos."""

    id: int  # 1: Lazy, 2: Humble, 3: Clever, 4: Great
    name: str
    description: str = ""
    is_unlocked: bool = False
    is_locked: bool = True
    is_scavenging: bool = False
    unlock_cost: Dict[str, int] = field(default_factory=lambda: {"wood": 0, "stone": 0, "iron": 0})
    unlock_time_seconds: int = 0
    time_remaining_seconds: int = 0
    return_time_iso: Optional[str] = None
    loot_ratio: float = 0.10
    duration_factor: float = 1.0

    @property
    def is_available_for_send(self) -> bool:
        """Indica se a categoria está pronta para receber uma nova expedição."""
        return self.is_unlocked and not self.is_scavenging


@dataclass
class ScavengeState:
    """Estado consolidado do ecrã de Coleta de Recursos da aldeia."""

    village_id: int
    options: List[ScavengeOption] = field(default_factory=list)
    available_troops: Dict[str, int] = field(default_factory=dict)
    active_expeditions_count: int = 0
    min_return_time_seconds: Optional[int] = None
    last_updated: float = field(default_factory=time.time)

    @property
    def unlocked_options(self) -> List[ScavengeOption]:
        return [opt for opt in self.options if opt.is_unlocked]

    @property
    def ready_options(self) -> List[ScavengeOption]:
        return [opt for opt in self.options if opt.is_available_for_send]


class ScavengeManager:
    """
    Controlador de automação da Coleta de Recursos (Scavenging).
    """

    def __init__(self):
        pass

    async def get_scavenge_state(
        self,
        account: TribalAccount,
        village_id: Optional[int] = None,
    ) -> ScavengeState:
        """
        Carrega o ecrã de Coleta (screen=place&mode=scavenge) e devolve o estado consolidado.
        """
        v_id = village_id or account.current_village_id or 0
        html = await account.get_screen(
            screen="place",
            mode="scavenge",
            village_id=village_id,
            apply_jitter=True,
        )

        raw_options = parse_scavenge_options(html)
        options: List[ScavengeOption] = []
        active_count = 0
        min_return: Optional[int] = None

        for raw in raw_options:
            opt = ScavengeOption(
                id=raw["id"],
                name=raw["name"],
                description=raw["description"],
                is_unlocked=raw["is_unlocked"],
                is_locked=raw["is_locked"],
                is_scavenging=raw["is_scavenging"],
                unlock_cost=raw.get("unlock_cost", {"wood": 0, "stone": 0, "iron": 0}),
                unlock_time_seconds=raw.get("unlock_time_seconds", 0),
                time_remaining_seconds=raw.get("time_remaining_seconds", 0),
                return_time_iso=raw.get("return_time_iso"),
                loot_ratio=raw.get("loot_ratio", 0.10),
                duration_factor=raw.get("duration_factor", 1.0),
            )
            if opt.is_scavenging:
                active_count += 1
                if opt.time_remaining_seconds > 0:
                    if min_return is None or opt.time_remaining_seconds < min_return:
                        min_return = opt.time_remaining_seconds

            options.append(opt)

        troops = parse_scavenge_available_troops(html)

        return ScavengeState(
            village_id=v_id,
            options=options,
            available_troops=troops,
            active_expeditions_count=active_count,
            min_return_time_seconds=min_return,
        )

    async def unlock_scavenge_option(
        self,
        account: TribalAccount,
        option_id: int,
        village_id: Optional[int] = None,
    ) -> bool:
        """
        Envia ordem de desbloqueio para a categoria de coleta indicada (2, 3 ou 4).
        """
        if option_id <= 1 or option_id > 4:
            return False

        try:
            data = {
                "option_id": str(option_id),
                "action": "unlock",
                "h": account.csrf_token or "",
            }
            await account.post_action(
                screen="place",
                mode="scavenge",
                action="unlock",
                village_id=village_id,
                data=data,
                apply_jitter=True,
            )
            logger.info(f"[{account.world}] Ordem de desbloqueio da Coleta Categoria {option_id} enviada.")
            return True
        except Exception as e:
            logger.warning(f"[{account.world}] Falha ao desbloquear Coleta Categoria {option_id}: {e}")
            return False
