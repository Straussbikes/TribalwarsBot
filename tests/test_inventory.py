"""
Testes unitários para o módulo de Visualização de Inventário & Gestão de Itens (Ponto 2.10 & Fase 4).
"""

import unittest
from unittest.mock import AsyncMock

from engine.actions.inventory import InventoryItem, InventoryManager
from engine.config.settings import BotConfig
from engine.utils.parsers import parse_inventory_screen

SAMPLE_INVENTORY_HTML = """
<!DOCTYPE html>
<html>
<body>
<div id="inventory">
    <div class="inventory_item" data-item-id="res_pack_10">
        <div class="title">Pacote de Recursos 10%</div>
        <div class="description">Adiciona 10% da capacidade do armazém em recursos.</div>
        <span class="count">x3</span>
        <img src="/graphic/items/res_pack.png" />
        <a class="btn-use" href="javascript:void(0)">Utilizar</a>
    </div>
    <div class="inventory_item" data-item-id="boost_attack">
        <div class="title">Bónus de Ataque +5%</div>
        <div class="description">Aumenta o ataque das tropas em 5% por 24h.</div>
        <span class="count">x1</span>
        <img src="/graphic/items/boost_attack.png" />
        <a class="btn-use" href="javascript:void(0)">Utilizar</a>
    </div>
</div>
</body>
</html>
"""


class TestInventory(unittest.IsolatedAsyncioTestCase):

    def test_parse_inventory_screen(self):
        items = parse_inventory_screen(SAMPLE_INVENTORY_HTML)
        self.assertEqual(len(items), 2)

        it1 = items[0]
        self.assertEqual(it1["id"], "res_pack_10")
        self.assertEqual(it1["title"], "Pacote de Recursos 10%")
        self.assertEqual(it1["count"], 3)
        self.assertTrue(it1["can_use"])

        it2 = items[1]
        self.assertEqual(it2["id"], "boost_attack")
        self.assertEqual(it2["count"], 1)

    async def test_inventory_manager_get_items(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.get_screen = AsyncMock(return_value=SAMPLE_INVENTORY_HTML)

        mgr = InventoryManager()
        items = await mgr.get_inventory_items(account, force_refresh=True)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].id, "res_pack_10")

    async def test_inventory_manager_use_item(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.csrf_token = "csrf_inv"
        account.post_action = AsyncMock(return_value="<html>ok</html>")

        mgr = InventoryManager()
        ok = await mgr.use_item(account, item_id="res_pack_10", village_id=12345)
        self.assertTrue(ok)
        account.post_action.assert_called_once()


class TestInventoryApi(unittest.TestCase):

    def setUp(self):
        from fastapi.testclient import TestClient
        from engine.api.server import create_app
        from engine.api.context import EngineContext

        self.cfg = BotConfig(world="pt117")
        self.ctx = EngineContext(config=self.cfg)
        self.token = "test_token_inv"
        self.app = create_app(self.ctx, token=self.token, attach_log_handler=False)
        self.client = TestClient(self.app, headers={"X-Engine-Token": self.token})

    def test_use_item_validation(self):
        res = self.client.post("/api/inventory/use", json={})
        self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
