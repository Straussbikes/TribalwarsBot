"""
Suíte de Testes Unitários para o Módulo de Missões, Bónus Diário e Inventário (Item 2.10).
Cobre: parsing de missões (HTML e game_data), validação de segurança económica (armazém/população),
leitura e abertura de baú diário, listagem e utilização manual de itens do inventário, e ciclo orquestrado.
"""

import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, patch

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from engine.actions.quest import (
    DailyBonusState,
    InventoryItem,
    InventoryState,
    QuestItem,
    QuestManager,
    QuestReward,
    QuestState,
)
from engine.config.settings import BotConfig, QuestConfig
from engine.core.models import Resources, VillageData
from engine.utils.parsers import (
    parse_daily_bonus_screen,
    parse_inventory_screen,
    parse_quest_screen,
)


SAMPLE_QUEST_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div id="quest_list">
        <!-- Missão 1: Concluída com recursos -->
        <div class="quest_item" data-quest-id="101">
            <span class="quest_name">Evoluir Bosque para nível 1</span>
            <div class="quest_rewards">
                <span class="icon header wood"></span> 200
                <span class="icon header stone"></span> 150
                <span class="icon header iron"></span> 100
            </div>
            <a class="btn btn-confirm-yes" href="/game.php?village=12345&screen=quest&action=claim_reward&quest_id=101&h=csrf_abc">Receber recompensa</a>
        </div>

        <!-- Missão 2: Em andamento -->
        <div class="quest_item" data-quest-id="102">
            <span class="quest_name">Construir Quartel</span>
            <div class="quest_rewards">
                <span class="icon header wood"></span> 500
                <span class="icon header pop"></span> 15
            </div>
        </div>

        <!-- Missão 3: Concluída com tropas -->
        <div class="quest_item" data-quest-id="103">
            <span class="quest_name">Recrutar 10 Lanceiros</span>
            <div class="quest_rewards">
                <span class="icon header pop"></span> 10
            </div>
            <a class="btn btn-confirm-yes" href="/game.php?village=12345&screen=quest&action=claim_reward&quest_id=103&h=csrf_abc">Receber recompensa</a>
        </div>
    </div>
</body>
</html>
"""

SAMPLE_DAILY_BONUS_HTML_AVAILABLE = """
<!DOCTYPE html>
<html>
<body>
    <div id="daily_bonus" class="daily-reward-container">
        <h2>Bónus Diário de Login</h2>
        <div class="chest chest-unopened">
            <a class="btn btn-default" href="/game.php?village=12345&screen=daily_bonus&action=open_chest&chest_id=1&h=csrf_abc">Abrir Baú Gratuito</a>
        </div>
    </div>
</body>
</html>
"""

SAMPLE_DAILY_BONUS_HTML_OPENED = """
<!DOCTYPE html>
<html>
<body>
    <div id="daily_bonus" class="daily-reward-container">
        <h2>Bónus Diário de Login</h2>
        <div class="chest chest-opened">
            <p>Já recolheste o teu bónus hoje. Volta amanhã para abrir um novo baú!</p>
        </div>
    </div>
</body>
</html>
"""

SAMPLE_INVENTORY_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div id="inventory_items">
        <div class="inventory_item" data-item-id="boost_wood_20">
            <h3 class="item_name">Pacote de Madeira +20%</h3>
            <span class="badge">2x</span>
            <p class="description">Aumenta a produção de madeira em 20% durante 7 dias.</p>
            <a class="btn" href="/game.php?village=12345&screen=inventory&action=use_item&item_id=boost_wood_20&h=csrf_abc">Usar</a>
        </div>
        <div class="inventory_item" data-item-id="instant_finish_10">
            <h3 class="item_name">Conclusão Instantânea (10 min)</h3>
            <span class="badge">5x</span>
            <p class="description">Conclui instantaneamente uma construção com menos de 10 minutos restantes.</p>
            <a class="btn" href="/game.php?village=12345&screen=inventory&action=use_item&item_id=instant_finish_10&h=csrf_abc">Usar</a>
        </div>
    </div>
</body>
</html>
"""


class TestQuestParsers(unittest.TestCase):
    """Testes unitários dos parsers de dados de missões, bónus diário e inventário."""

    def test_parse_quest_screen_html(self):
        data = parse_quest_screen(SAMPLE_QUEST_HTML)
        quests = data["quests"]
        self.assertEqual(len(quests), 3)
        self.assertEqual(data["finishable_count"], 2)

        # Missão 1
        q1 = next(q for q in quests if q["id"] == "101")
        self.assertEqual(q1["title"], "Evoluir Bosque para nível 1")
        self.assertTrue(q1["finishable"])
        self.assertEqual(q1["rewards"]["wood"], 200)
        self.assertEqual(q1["rewards"]["stone"], 150)
        self.assertEqual(q1["rewards"]["iron"], 100)

        # Missão 2
        q2 = next(q for q in quests if q["id"] == "102")
        self.assertEqual(q2["title"], "Construir Quartel")
        self.assertFalse(q2["finishable"])

        # Missão 3
        q3 = next(q for q in quests if q["id"] == "103")
        self.assertEqual(q3["title"], "Recrutar 10 Lanceiros")
        self.assertTrue(q3["finishable"])
        self.assertEqual(q3["rewards"]["pop"], 10)

    def test_parse_quest_screen_game_data(self):
        mock_game_data = {
            "quest": {
                "quests": {
                    "201": {
                        "id": "201",
                        "title": "Explorar o Mundo",
                        "finishable": True,
                        "rewards": {"wood": 100, "stone": 100, "iron": 100, "pop": 0},
                    }
                }
            }
        }
        data = parse_quest_screen("<html></html>", game_data=mock_game_data)
        self.assertEqual(len(data["quests"]), 1)
        self.assertEqual(data["quests"][0]["id"], "201")
        self.assertEqual(data["quests"][0]["title"], "Explorar o Mundo")
        self.assertTrue(data["quests"][0]["finishable"])

    def test_parse_daily_bonus_available(self):
        data = parse_daily_bonus_screen(SAMPLE_DAILY_BONUS_HTML_AVAILABLE)
        self.assertTrue(data["can_open"])
        self.assertFalse(data["is_opened_today"])
        self.assertIn("action=open_chest", data["open_url"])

    def test_parse_daily_bonus_opened(self):
        data = parse_daily_bonus_screen(SAMPLE_DAILY_BONUS_HTML_OPENED)
        self.assertFalse(data["can_open"])
        self.assertTrue(data["is_opened_today"])

    def test_parse_inventory_screen(self):
        data = parse_inventory_screen(SAMPLE_INVENTORY_HTML)
        items = data["items"]
        self.assertEqual(len(items), 2)

        item1 = next(it for it in items if it["id"] == "boost_wood_20")
        self.assertEqual(item1["name"], "Pacote de Madeira +20%")
        self.assertEqual(item1["count"], 2)
        self.assertTrue(item1["can_use"])
        self.assertIn("action=use_item", item1["use_url"])

        item2 = next(it for it in items if it["id"] == "instant_finish_10")
        self.assertEqual(item2["name"], "Conclusão Instantânea (10 min)")
        self.assertEqual(item2["count"], 5)


class TestQuestManagerSafety(unittest.TestCase):
    """Testes unitários das regras de segurança económica para resgate de missões."""

    def setUp(self):
        self.manager = QuestManager()

    def test_safe_claim_allowed(self):
        resources = Resources(wood=1000, stone=1000, iron=1000, storage_max=5000, pop=100, pop_max=200)
        quest = QuestItem(
            id="1",
            title="Missão Segura",
            rewards=QuestReward(wood=300, stone=300, iron=300, pop=0),
        )
        is_safe, reason = self.manager.can_claim_safely(quest, resources, margin=0.95)
        self.assertTrue(is_safe)
        self.assertEqual(reason, "Seguro para recolha")

    def test_overflow_storage_wood_prevented(self):
        # 4600 + 300 = 4900 > 4750 (5000 * 0.95)
        resources = Resources(wood=4600, stone=1000, iron=1000, storage_max=5000, pop=100, pop_max=200)
        quest = QuestItem(
            id="2",
            title="Missão com Excesso de Madeira",
            rewards=QuestReward(wood=300, stone=100, iron=100, pop=0),
        )
        is_safe, reason = self.manager.can_claim_safely(quest, resources, margin=0.95)
        self.assertFalse(is_safe)
        self.assertIn("Madeira excederia limite seguro", reason)

    def test_insufficient_population_prevented(self):
        # Pop livre: 200 - 195 = 5. A missão oferece 10 tropas/pop.
        resources = Resources(wood=1000, stone=1000, iron=1000, storage_max=5000, pop=195, pop_max=200)
        quest = QuestItem(
            id="3",
            title="Missão com Excesso de Tropas",
            rewards=QuestReward(wood=0, stone=0, iron=0, pop=10),
        )
        is_safe, reason = self.manager.can_claim_safely(quest, resources, margin=0.95)
        self.assertFalse(is_safe)
        self.assertIn("População livre insuficiente", reason)


class TestQuestManagerActions(unittest.IsolatedAsyncioTestCase):
    """Testes assíncronos das ações de resgate, baú diário e ciclo orquestrado."""

    def setUp(self):
        self.manager = QuestManager()
        self.mock_account = AsyncMock()
        self.mock_account.world = "pt117"
        self.mock_account.host = "pt117.tribalwars.com.pt"
        self.mock_account.csrf_token = "csrf_token_test"
        self.mock_account.current_village_id = 12345
        self.mock_account.villages = {
            12345: VillageData(
                id=12345,
                name="Aldeia Teste",
                resources=Resources(wood=500, stone=500, iron=500, storage_max=4000, pop=50, pop_max=100),
            )
        }

    async def test_claim_quest_success(self):
        self.mock_account.get_screen.return_value = "<html>OK</html>"
        quest = QuestItem(
            id="101",
            title="Evoluir Bosque",
            finishable=True,
            rewards=QuestReward(wood=200, stone=200, iron=100),
        )

        success = await self.manager.claim_quest(self.mock_account, quest, safe_mode=True)
        self.assertTrue(success)
        self.mock_account.get_screen.assert_called_once()

    async def test_claim_quest_skips_when_unsafe(self):
        # Configura armazém quase cheio
        self.mock_account.villages[12345].resources = Resources(
            wood=3900, stone=500, iron=500, storage_max=4000, pop=50, pop_max=100
        )
        quest = QuestItem(
            id="101",
            title="Evoluir Bosque",
            finishable=True,
            rewards=QuestReward(wood=200, stone=200, iron=100),
        )

        success = await self.manager.claim_quest(self.mock_account, quest, safe_mode=True)
        self.assertFalse(success)
        self.mock_account.get_screen.assert_not_called()

    async def test_open_daily_bonus_success(self):
        self.mock_account.get_screen.return_value = SAMPLE_DAILY_BONUS_HTML_AVAILABLE
        success = await self.manager.open_daily_bonus(self.mock_account)
        self.assertTrue(success)
        self.mock_account.get.assert_called_once()

    async def test_use_inventory_item_manual_success(self):
        self.mock_account.get_screen.return_value = "<html>Item Usado</html>"
        success = await self.manager.use_inventory_item(self.mock_account, "boost_wood_20")
        self.assertTrue(success)
        self.mock_account.get_screen.assert_called_once()

    async def test_run_cycle_orchestration(self):
        # Mock get_quest_state
        self.mock_account.get_screen.side_effect = [
            SAMPLE_QUEST_HTML,                  # fetch_quest_state
            SAMPLE_DAILY_BONUS_HTML_AVAILABLE, # get_daily_bonus_state
        ]
        self.mock_account.get.return_value = "<html>Recompensa/Baú</html>"

        config = QuestConfig(
            enabled=True,
            auto_claim_quests=True,
            auto_daily_bonus=True,
            safe_storage_margin=0.95,
        )

        results = await self.manager.run_cycle(self.mock_account, config=config)
        self.assertEqual(results["village_id"], 12345)
        self.assertEqual(results["quests_claimed"], 2)
        self.assertTrue(results["daily_bonus_opened"])


if __name__ == "__main__":
    unittest.main()
