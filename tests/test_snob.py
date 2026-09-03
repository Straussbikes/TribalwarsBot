"""
Testes unitários para o módulo da Academia & Cunha de Moedas (Ponto 2.6 & Fase 4).
"""

import unittest
from unittest.mock import AsyncMock, MagicMock

from engine.actions.snob import SnobManager, SnobState
from engine.config.settings import BotConfig, SnobConfig
from engine.utils.parsers import parse_snob_screen

SAMPLE_SNOB_HTML = """
<!DOCTYPE html>
<html>
<body>
<div id="snob_screen">
    <table class="vis">
        <tr>
            <td>Total de moedas de ouro:</td>
            <td><span id="coins_total">42</span></td>
        </tr>
        <tr>
            <td>Moedas para o próximo nobre:</td>
            <td>5</td>
        </tr>
        <tr>
            <td>Nobres ainda disponíveis:</td>
            <td>2</td>
        </tr>
        <tr>
            <td>Nobres em formação:</td>
            <td>1</td>
        </tr>
    </table>
    <form action="/game.php?village=12345&screen=snob&action=coin" method="post">
        <input type="text" name="count" max="8" value="1" />
        <input class="btn" type="submit" value="Cunhar" />
    </form>
</div>
</body>
</html>
"""


class TestSnob(unittest.IsolatedAsyncioTestCase):

    def test_parse_snob_screen(self):
        parsed = parse_snob_screen(SAMPLE_SNOB_HTML)
        self.assertEqual(parsed["coins_minted"], 42)
        self.assertEqual(parsed["coins_next_noble"], 5)
        self.assertEqual(parsed["nobles_count"], 2)
        self.assertEqual(parsed["nobles_in_production"], 1)
        self.assertTrue(parsed["can_mint"])
        self.assertEqual(parsed["max_mintable"], 8)

    async def test_snob_manager_get_state(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345
        account.get_screen = AsyncMock(return_value=SAMPLE_SNOB_HTML)

        mgr = SnobManager()
        state = await mgr.get_snob_state(account, village_id=12345)
        self.assertEqual(state.coins_minted, 42)
        self.assertEqual(state.nobles_count, 2)
        self.assertEqual(state.max_mintable, 8)
        self.assertTrue(state.can_mint)

    async def test_mint_coins_and_recruit(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.csrf_token = "csrf_123"
        account.post_action = AsyncMock(return_value="<html>ok</html>")

        mgr = SnobManager()
        mint_ok = await mgr.mint_coins(account, count=3, village_id=12345)
        self.assertTrue(mint_ok)

        train_ok = await mgr.recruit_nobleman(account, village_id=12345)
        self.assertTrue(train_ok)
        self.assertEqual(account.post_action.call_count, 2)

    async def test_evaluate_auto_mint_overflow(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345
        account.get_screen = AsyncMock(return_value=SAMPLE_SNOB_HTML)
        account.post_action = AsyncMock(return_value="<html>ok</html>")
        account.game_data = {
            "village": {
                "storage_max": 100000,
                "wood": 90000,  # 90% do armazém -> acima de 85%
                "stone": 90000,
                "iron": 90000,
            }
        }

        mgr = SnobManager()
        cfg = SnobConfig(auto_mint_enabled=True, storage_threshold_percent=85.0)
        res = await mgr.evaluate_auto_mint(account, cfg, village_id=12345)
        self.assertEqual(res["status"], "success")
        self.assertGreater(res["minted_count"], 0)


class TestSnobApi(unittest.TestCase):

    def setUp(self):
        from fastapi.testclient import TestClient
        from engine.api.server import create_app
        from engine.api.context import EngineContext

        self.cfg = BotConfig(world="pt117")
        self.ctx = EngineContext(config=self.cfg)
        self.token = "test_token_snob"
        self.app = create_app(self.ctx, token=self.token, attach_log_handler=False)
        self.client = TestClient(self.app, headers={"X-Engine-Token": self.token})

    def test_snob_config_endpoint(self):
        res = self.client.post("/api/snob/config", json={
            "auto_mint_enabled": True,
            "storage_threshold_percent": 80.0,
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(self.ctx.config.snob.auto_mint_enabled)
        self.assertEqual(self.ctx.config.snob.storage_threshold_percent, 80.0)


if __name__ == "__main__":
    unittest.main()
