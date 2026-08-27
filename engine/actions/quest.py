"""
Tribal Wars Mobile Automation Engine - QuestManager (screen=quest, daily_bonus, inventory)
Gestão de Missões do Sistema, Baú Diário de Login e Leitura de Inventário.
Inclui validação de segurança económica (impede perda de recursos por armazém cheio ou falta de pop).
NOTA: Itens do inventário só podem ser utilizados mediante acionamento manual do utilizador.
"""

import asyncio
from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from engine.config.settings import QuestConfig
from engine.core.account import TribalAccount
from engine.core.models import Resources
from engine.utils.parsers import (
    parse_daily_bonus_screen,
    parse_inventory_screen,
    parse_quest_screen,
)
from engine.utils.timing import get_click_jitter

logger = logging.getLogger(__name__)


@dataclass
class QuestReward:
    """Recompensas oferecidas por uma missão."""
    wood: int = 0
    stone: int = 0
    iron: int = 0
    pop: int = 0
    flags: List[str] = field(default_factory=list)
    items: List[str] = field(default_factory=list)
    description: str = ""

    @property
    def total_resources(self) -> int:
        return self.wood + self.stone + self.iron

    @property
    def has_resources(self) -> bool:
        return self.total_resources > 0


@dataclass
class QuestItem:
    """Representação de uma missão do sistema."""
    id: str
    title: str
    description: str = ""
    finishable: bool = False
    rewards: QuestReward = field(default_factory=QuestReward)
    claim_url: Optional[str] = None


@dataclass
class QuestState:
    """Estado consolidado das missões de uma aldeia."""
    village_id: int
    quests: List[QuestItem] = field(default_factory=list)
    finishable_count: int = 0


@dataclass
class DailyBonusState:
    """Estado do Bónus Diário / Baú de Login."""
    can_open: bool = False
    open_url: Optional[str] = None
    is_opened_today: bool = False
    chests: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class InventoryItem:
    """Representação de um item no inventário do jogador."""
    id: str
    name: str
    count: int = 1
    description: str = ""
    can_use: bool = False
    use_url: Optional[str] = None


@dataclass
class InventoryState:
    """Estado consolidado do inventário."""
    items: List[InventoryItem] = field(default_factory=list)


class QuestManager:
    """
    Controlador de automação para missões, bónus diário e inventário.
    Recolhe missões concluídas com salvaguarda de armazém/população e abre baús diários gratuitos.
    O uso de itens de inventário é estritamente manual.
    """

    async def get_quest_state(
        self, account: TribalAccount, village_id: Optional[int] = None
    ) -> QuestState:
        """Carrega 'screen=quest' e extrai o catálogo de missões e recompensas."""
        v_id = village_id or account.current_village_id or 0
        html = await account.get_screen("quest", village_id=v_id)

        raw = parse_quest_screen(html, account.last_game_data)
        quests: List[QuestItem] = []

        for q in raw.get("quests", []):
            rew_dict = q.get("rewards", {})
            reward = QuestReward(
                wood=rew_dict.get("wood", 0),
                stone=rew_dict.get("stone", 0),
                iron=rew_dict.get("iron", 0),
                pop=rew_dict.get("pop", 0),
                flags=rew_dict.get("flags", []),
                items=rew_dict.get("items", []),
                description=rew_dict.get("description", ""),
            )
            quests.append(
                QuestItem(
                    id=str(q.get("id", "")),
                    title=str(q.get("title", "")),
                    description=str(q.get("description", "")),
                    finishable=bool(q.get("finishable", False)),
                    rewards=reward,
                    claim_url=q.get("claim_url"),
                )
            )

        finishable_count = sum(1 for q in quests if q.finishable)
        logger.info(
            f"[{account.world}] Missões carregadas na aldeia {v_id}: "
            f"{len(quests)} no total, {finishable_count} prontas para entrega."
        )
        return QuestState(
            village_id=v_id,
            quests=quests,
            finishable_count=finishable_count,
        )

    def can_claim_safely(
        self, quest: QuestItem, resources: Resources, margin: float = 0.95
    ) -> Tuple[bool, str]:
        """
        Valida se os recursos ou tropas da recompensa podem ser recebidos sem desperdício.
        Verifica se a soma dos recursos atuais com a recompensa não excede a margem de segurança
        do armazém e se a população livre comporta eventuais tropas oferecidas.
        """
        storage_limit = int(resources.storage_max * margin)

        if quest.rewards.wood > 0 and (resources.wood + quest.rewards.wood) > storage_limit:
            return (
                False,
                f"Madeira excederia limite seguro ({resources.wood} + {quest.rewards.wood} > {storage_limit})",
            )

        if quest.rewards.stone > 0 and (resources.stone + quest.rewards.stone) > storage_limit:
            return (
                False,
                f"Argila excederia limite seguro ({resources.stone} + {quest.rewards.stone} > {storage_limit})",
            )

        if quest.rewards.iron > 0 and (resources.iron + quest.rewards.iron) > storage_limit:
            return (
                False,
                f"Ferro excederia limite seguro ({resources.iron} + {quest.rewards.iron} > {storage_limit})",
            )

        if quest.rewards.pop > 0 and resources.free_pop < quest.rewards.pop:
            return (
                False,
                f"População livre insuficiente ({resources.free_pop} < {quest.rewards.pop} necessárias)",
            )

        return True, "Seguro para recolha"

    async def claim_quest(
        self,
        account: TribalAccount,
        quest: QuestItem,
        village_id: Optional[int] = None,
        safe_mode: bool = True,
        safe_margin: float = 0.95,
    ) -> bool:
        """
        Resgata a recompensa de uma missão concluída.
        Se safe_mode=True, verifica primeiro as margens de armazém e população da aldeia.
        """
        v_id = village_id or account.current_village_id or 0

        if safe_mode:
            # Obtém recursos atuais da aldeia
            curr_res = None
            if v_id in account.villages and account.villages[v_id].resources:
                curr_res = account.villages[v_id].resources

            if curr_res is not None and curr_res.storage_max > 0:
                is_safe, reason = self.can_claim_safely(quest, curr_res, margin=safe_margin)
                if not is_safe:
                    logger.warning(
                        f"[{account.world}] Resgate da missão '{quest.title}' (ID {quest.id}) "
                        f"adiado por segurança: {reason}."
                    )
                    return False

        # Prepara requisição de claim
        logger.info(
            f"[{account.world}] A resgatar recompensa da missão '{quest.title}' (ID {quest.id})..."
        )
        try:
            extra_params = {
                "action": "claim_reward",
                "quest_id": quest.id,
                "h": account.csrf_token or "",
            }

            # Se houver claim_url específico, usa os parâmetros do link
            if quest.claim_url and "action=" in quest.claim_url:
                await account.get(f"https://{account.host}/{quest.claim_url.lstrip('/')}")
            else:
                await account.get_screen("quest", village_id=v_id, extra_params=extra_params)

            logger.info(
                f"[{account.world}] Recompensa da missão '{quest.title}' resgatada com sucesso!"
            )
            return True
        except Exception as e:
            logger.error(
                f"[{account.world}] Falha ao resgatar recompensa da missão {quest.id}: {e}"
            )
            return False

    async def claim_all_valid_quests(
        self,
        account: TribalAccount,
        village_id: Optional[int] = None,
        safe_mode: bool = True,
        safe_margin: float = 0.95,
    ) -> Dict[str, Any]:
        """
        Verifica todas as missões e resgata sequencialmente as que cumprem os critérios de segurança.
        """
        state = await self.get_quest_state(account, village_id=village_id)
        finishable = [q for q in state.quests if q.finishable]

        claimed_count = 0
        skipped_count = 0

        for q in finishable:
            success = await self.claim_quest(
                account, q, village_id=village_id, safe_mode=safe_mode, safe_margin=safe_margin
            )
            if success:
                claimed_count += 1
                # Pequeno jitter entre claims
                await asyncio.sleep(get_click_jitter(0.2, 0.4))
            else:
                skipped_count += 1

        return {
            "total_finishable": len(finishable),
            "claimed": claimed_count,
            "skipped": skipped_count,
        }

    async def get_daily_bonus_state(
        self, account: TribalAccount, village_id: Optional[int] = None
    ) -> DailyBonusState:
        """Carrega 'screen=daily_bonus' e verifica se há baú diário para abrir."""
        v_id = village_id or account.current_village_id or 0
        try:
            html = await account.get_screen("daily_bonus", village_id=v_id)
            raw = parse_daily_bonus_screen(html)
            return DailyBonusState(
                can_open=bool(raw.get("can_open", False)),
                open_url=raw.get("open_url"),
                is_opened_today=bool(raw.get("is_opened_today", False)),
                chests=raw.get("chests", []),
            )
        except Exception as e:
            logger.warning(f"[{account.world}] Não foi possível aceder a 'screen=daily_bonus': {e}")
            return DailyBonusState()

    async def open_daily_bonus(
        self, account: TribalAccount, village_id: Optional[int] = None
    ) -> bool:
        """Abre o baú de bónus diário gratuito se estiver disponível."""
        v_id = village_id or account.current_village_id or 0
        state = await self.get_daily_bonus_state(account, village_id=v_id)

        if not state.can_open:
            logger.info(f"[{account.world}] Baú diário não disponível ou já recolhido hoje.")
            return False

        logger.info(f"[{account.world}] A abrir baú gratuito de bónus diário...")
        try:
            if state.open_url:
                await account.get(f"https://{account.host}/{state.open_url.lstrip('/')}")
            else:
                extra_params = {
                    "action": "open_chest",
                    "h": account.csrf_token or "",
                }
                await account.get_screen("daily_bonus", village_id=v_id, extra_params=extra_params)

            logger.info(f"[{account.world}] Baú diário aberto com sucesso!")
            return True
        except Exception as e:
            logger.error(f"[{account.world}] Falha ao abrir baú diário: {e}")
            return False

    async def get_inventory_state(
        self, account: TribalAccount, village_id: Optional[int] = None
    ) -> InventoryState:
        """Carrega 'screen=inventory' e lista todos os itens disponíveis."""
        v_id = village_id or account.current_village_id or 0
        try:
            html = await account.get_screen("inventory", village_id=v_id)
            raw = parse_inventory_screen(html)
            items: List[InventoryItem] = [
                InventoryItem(
                    id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    count=int(item.get("count", 1)),
                    description=str(item.get("description", "")),
                    can_use=bool(item.get("can_use", False)),
                    use_url=item.get("use_url"),
                )
                for item in raw.get("items", [])
            ]
            logger.info(f"[{account.world}] Inventário carregado: {len(items)} tipos de itens.")
            return InventoryState(items=items)
        except Exception as e:
            logger.warning(f"[{account.world}] Não foi possível aceder a 'screen=inventory': {e}")
            return InventoryState()

    async def use_inventory_item(
        self, account: TribalAccount, item_id: str, village_id: Optional[int] = None
    ) -> bool:
        """
        Utiliza manualmente um item do inventário.
        ATENÇÃO: Este método só deve ser invocado via ação manual direta do utilizador.
        """
        v_id = village_id or account.current_village_id or 0
        logger.info(f"[{account.world}] A utilizar manualmente o item '{item_id}' do inventário...")

        try:
            extra_params = {
                "action": "use_item",
                "item_id": item_id,
                "h": account.csrf_token or "",
            }
            await account.get_screen("inventory", village_id=v_id, extra_params=extra_params)
            logger.info(f"[{account.world}] Item '{item_id}' utilizado com sucesso!")
            return True
        except Exception as e:
            logger.error(f"[{account.world}] Falha ao utilizar item '{item_id}': {e}")
            return False

    async def run_cycle(
        self,
        account: TribalAccount,
        village_id: Optional[int] = None,
        config: Optional["QuestConfig"] = None,
    ) -> Dict[str, Any]:
        """
        Executa o ciclo automatizado periódico:
        1. Auto-claim de missões concluídas com salvaguarda de armazém.
        2. Recolha do baú diário gratuito se disponível.
        NOTA: Itens do inventário NUNCA são ativados automaticamente.
        """
        if config is None:
            from engine.config.settings import QuestConfig
            cfg = QuestConfig()
        else:
            cfg = config
        if not cfg.enabled:
            return {"enabled": False}

        v_id = village_id or account.current_village_id or 0
        results: Dict[str, Any] = {
            "village_id": v_id,
            "quests_claimed": 0,
            "quests_skipped": 0,
            "daily_bonus_opened": False,
        }

        # 1. Missões
        if cfg.auto_claim_quests:
            q_res = await self.claim_all_valid_quests(
                account,
                village_id=v_id,
                safe_mode=True,
                safe_margin=cfg.safe_storage_margin,
            )
            results["quests_claimed"] = q_res.get("claimed", 0)
            results["quests_skipped"] = q_res.get("skipped", 0)

        # 2. Bónus Diário
        if cfg.auto_daily_bonus:
            opened = await self.open_daily_bonus(account, village_id=v_id)
            results["daily_bonus_opened"] = opened

        return results
