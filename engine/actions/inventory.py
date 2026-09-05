"""
Tribal Wars Mobile Automation Engine - Inventory Manager (screen=inventory)
Módulo responsável por:
1. Listagem de itens acumulados no inventário da conta.
2. Ativação manual e segura de bónus e consumíveis (sob confirmação explícita do utilizador).
"""

from dataclasses import dataclass
import logging
import time
from typing import Any, Dict, List, Optional

from engine.core.account import TribalAccount
from engine.utils.parsers import parse_inventory_screen

logger = logging.getLogger(__name__)


@dataclass
class InventoryItem:
    """Item guardado no inventário da conta."""
    id: str
    title: str
    description: str = ""
    count: int = 1
    icon_url: str = ""
    can_use: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "count": self.count,
            "icon_url": self.icon_url,
            "can_use": self.can_use,
        }


class InventoryManager:
    """Gestor do Inventário e Ativação Segura de Itens."""

    def __init__(self):
        self._cached_items: List[InventoryItem] = []
        self._last_fetched: float = 0.0

    async def get_inventory_items(
        self,
        account: TribalAccount,
        force_refresh: bool = False,
    ) -> List[InventoryItem]:
        """Carrega a lista de itens guardados no inventário."""
        now = time.time()
        if not force_refresh and self._cached_items and (now - self._last_fetched < 120.0):
            return self._cached_items

        try:
            html = await account.get_screen(
                screen="inventory",
                apply_jitter=True,
            )
            raw_items = parse_inventory_screen(html)
            self._cached_items = [
                InventoryItem(
                    id=item["id"],
                    title=item["title"],
                    description=item.get("description", ""),
                    count=item.get("count", 1),
                    icon_url=item.get("icon_url", ""),
                    can_use=item.get("can_use", False),
                )
                for item in raw_items
            ]
            self._last_fetched = now
            logger.info(f"[{account.world}] 🎒 Inventário atualizado: {len(self._cached_items)} item(ns) encontrado(s).")
            return self._cached_items
        except Exception as e:
            logger.warning(f"[{account.world}] Erro ao carregar inventário: {e}")
            return self._cached_items

    async def use_item(
        self,
        account: TribalAccount,
        item_id: str,
        village_id: Optional[int] = None,
    ) -> bool:
        """
        Ativa um item consumível do inventário.
        ATENÇÃO: Requer chamada explícita do utilizador via interface ou API.
        """
        if not item_id:
            return False

        data = {
            "item_id": str(item_id),
            "h": account.csrf_token or "",
        }
        if village_id:
            data["village_id"] = str(village_id)

        try:
            await account.post_action(
                screen="inventory",
                action="use",
                village_id=village_id,
                data=data,
                apply_jitter=True,
            )
            logger.info(f"[{account.world}] 🎒 Item {item_id} ativado com sucesso!")
            # Invalida cache local
            self._last_fetched = 0.0
            return True
        except Exception as e:
            logger.warning(f"[{account.world}] Falha ao utilizar item {item_id}: {e}")
            return False
