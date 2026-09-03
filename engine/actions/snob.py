"""
Tribal Wars Mobile Automation Engine - Snob / Academy Manager (screen=snob)
Módulo responsável por:
1. Inspeção de moedas cunhadas, custos e nobres disponíveis.
2. Cunhagem manual e automática de moedas (quando o armazém estiver próximo de encher).
3. Recrutamento automático de Nobres.
"""

from dataclasses import dataclass, field
import logging
import time
from typing import Any, Dict, Optional

from engine.core.account import TribalAccount
from engine.utils.parsers import parse_snob_screen

logger = logging.getLogger(__name__)


@dataclass
class SnobState:
    """Estado do ecrã da Academia."""
    village_id: int
    coins_minted: int = 0
    coins_next_noble: int = 1
    nobles_count: int = 0
    nobles_in_production: int = 0
    can_mint: bool = False
    max_mintable: int = 0
    coin_cost: Dict[str, int] = field(default_factory=lambda: {"wood": 28000, "stone": 30000, "iron": 25000})
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "village_id": self.village_id,
            "coins_minted": self.coins_minted,
            "coins_next_noble": self.coins_next_noble,
            "nobles_count": self.nobles_count,
            "nobles_in_production": self.nobles_in_production,
            "can_mint": self.can_mint,
            "max_mintable": self.max_mintable,
            "coin_cost": self.coin_cost,
            "last_updated": self.last_updated,
        }


class SnobManager:
    """Gestor de automação da Academia e Cunhador de Moedas."""

    def __init__(self):
        self._states: Dict[int, SnobState] = {}

    async def get_snob_state(
        self,
        account: TribalAccount,
        village_id: Optional[int] = None,
    ) -> SnobState:
        """Carrega a Academia e analisa o estado de moedas e nobres."""
        v_id = village_id or account.current_village_id or 0
        html = await account.get_screen(
            screen="snob",
            village_id=village_id,
            apply_jitter=True,
        )
        parsed = parse_snob_screen(html)
        state = SnobState(
            village_id=v_id,
            coins_minted=parsed.get("coins_minted", 0),
            coins_next_noble=parsed.get("coins_next_noble", 1),
            nobles_count=parsed.get("nobles_count", 0),
            nobles_in_production=parsed.get("nobles_in_production", 0),
            can_mint=parsed.get("can_mint", False),
            max_mintable=parsed.get("max_mintable", 0),
            coin_cost=parsed.get("coin_cost", {"wood": 28000, "stone": 30000, "iron": 25000}),
        )
        self._states[v_id] = state
        return state

    async def mint_coins(
        self,
        account: TribalAccount,
        count: int = 1,
        village_id: Optional[int] = None,
    ) -> bool:
        """Cunha a quantidade especificada de moedas de ouro."""
        if count <= 0:
            return False

        v_id = village_id or account.current_village_id or 0
        data = {
            "count": str(count),
            "h": account.csrf_token or "",
        }
        try:
            await account.post_action(
                screen="snob",
                action="coin",
                village_id=village_id,
                data=data,
                apply_jitter=True,
            )
            logger.info(f"[{account.world}] 👑 {count} moeda(s) de ouro cunhada(s) com sucesso na aldeia {v_id}!")
            return True
        except Exception as e:
            logger.warning(f"[{account.world}] Falha ao cunhar moedas na aldeia {v_id}: {e}")
            return False

    async def recruit_nobleman(
        self,
        account: TribalAccount,
        village_id: Optional[int] = None,
    ) -> bool:
        """Inicia o treino de 1 Nobre na Academia."""
        v_id = village_id or account.current_village_id or 0
        data = {
            "action": "train",
            "h": account.csrf_token or "",
        }
        try:
            await account.post_action(
                screen="snob",
                action="train",
                village_id=village_id,
                data=data,
                apply_jitter=True,
            )
            logger.info(f"[{account.world}] 👑 Nobre colocado em formação na aldeia {v_id}!")
            return True
        except Exception as e:
            logger.warning(f"[{account.world}] Falha ao recrutar Nobre na aldeia {v_id}: {e}")
            return False

    async def evaluate_auto_mint(
        self,
        account: TribalAccount,
        config: Any,
        village_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Avalia se os recursos no armazém estão prestes a transbordar e cunha moedas preventivamente.
        """
        v_id = village_id or account.current_village_id or 0
        if not getattr(config, "auto_mint_enabled", False):
            return {"status": "skipped", "reason": "auto_mint_disabled"}

        state = await self.get_snob_state(account, village_id=v_id)
        if not state.can_mint or state.max_mintable <= 0:
            return {"status": "skipped", "reason": "no_resources_or_cannot_mint"}

        # Avalia a capacidade do armazém da aldeia
        vill_data = account.game_data.get("village", {}) if hasattr(account, "game_data") else {}
        storage = vill_data.get("storage_max", 400000)
        wood = vill_data.get("wood", 0)
        stone = vill_data.get("stone", 0)
        iron = vill_data.get("iron", 0)

        threshold_pct = getattr(config, "storage_threshold_percent", 85.0) / 100.0
        is_near_overflow = (
            (wood / max(1, storage)) >= threshold_pct or
            (stone / max(1, storage)) >= threshold_pct or
            (iron / max(1, storage)) >= threshold_pct
        )

        if not is_near_overflow:
            return {"status": "skipped", "reason": "storage_below_threshold"}

        to_mint = min(state.max_mintable, 5)  # Cunhagem segura em lotes de até 5
        ok = await self.mint_coins(account, count=to_mint, village_id=v_id)
        return {
            "status": "success" if ok else "failed",
            "minted_count": to_mint if ok else 0,
            "village_id": v_id,
        }
