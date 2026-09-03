"""
Testes Unitários para o Módulo de Coleta de Recursos / Scavenging.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from engine.actions.scavenge import ScavengeManager, ScavengeOption, ScavengeState
from engine.utils.parsers import (
    parse_scavenge_available_troops,
    parse_scavenge_options,
)

SAMPLE_SCAVENGE_HTML = """
<!DOCTYPE html>
<html>
<body>
<div id="scavenge_screen">
    <div class="scavenge-option option-1" id="scavenge_option_1">
        <div class="title">Pequena Coleta</div>
        <div class="status">Pronto</div>
    </div>
    <div class="scavenge-option option-2" id="scavenge_option_2">
        <div class="title">Média Coleta</div>
        <span class="return-countdown" data-endtime="1788352800">01:15:30</span>
    </div>
    <div class="scavenge-option option-3" id="scavenge_option_3">
        <div class="title">Grande Coleta</div>
        <div class="unlock-cost">
            <span class="wood">1.000</span>
            <span class="stone">1.200</span>
            <span class="iron">1.000</span>
        </div>
        <a class="btn-unlock" href="javascript:void(0)">Desbloquear</a>
    </div>
    <div class="scavenge-option option-4" id="scavenge_option_4">
        <div class="title">Coleta Extrema</div>
        <div class="unlock-cost">
            <span class="wood">10.000</span>
            <span class="stone">12.000</span>
            <span class="iron">10.000</span>
        </div>
        <a class="btn-unlock" href="javascript:void(0)">Desbloquear</a>
    </div>

    <div class="candidate-squad">
        <input name="spear" data-all-count="120" value="0" />
        <input name="sword" data-all-count="85" value="0" />
        <input name="axe" data-all-count="40" value="0" />
        <input name="light" data-all-count="15" value="0" />
    </div>
</div>
</body>
</html>
"""


class TestScavenge(unittest.IsolatedAsyncioTestCase):

    def test_parse_scavenge_options(self):
        options = parse_scavenge_options(SAMPLE_SCAVENGE_HTML)
        self.assertEqual(len(options), 4)

        # Categoria 1 (Lazy): Desbloqueada e pronta
        opt1 = options[0]
        self.assertEqual(opt1["id"], 1)
        self.assertTrue(opt1["is_unlocked"])
        self.assertFalse(opt1["is_scavenging"])

        # Categoria 2 (Humble): Desbloqueada e em expedição
        opt2 = options[1]
        self.assertEqual(opt2["id"], 2)
        self.assertTrue(opt2["is_unlocked"])
        self.assertTrue(opt2["is_scavenging"])
        self.assertTrue(opt2["time_remaining_seconds"] > 0)

        # Categoria 3 (Clever): Bloqueada com custo
        opt3 = options[2]
        self.assertEqual(opt3["id"], 3)
        self.assertFalse(opt3["is_unlocked"])
        self.assertTrue(opt3["is_locked"])
        self.assertEqual(opt3["unlock_cost"]["wood"], 1000)
        self.assertEqual(opt3["unlock_cost"]["stone"], 1200)

        # Categoria 4 (Great): Bloqueada com custo
        opt4 = options[3]
        self.assertEqual(opt4["id"], 4)
        self.assertFalse(opt4["is_unlocked"])
        self.assertTrue(opt4["is_locked"])
        self.assertEqual(opt4["unlock_cost"]["wood"], 10000)

    def test_parse_scavenge_available_troops(self):
        troops = parse_scavenge_available_troops(SAMPLE_SCAVENGE_HTML)
        self.assertEqual(troops.get("spear"), 120)
        self.assertEqual(troops.get("sword"), 85)
        self.assertEqual(troops.get("axe"), 40)
        self.assertEqual(troops.get("light"), 15)

    async def test_scavenge_manager_get_state(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.csrf_token = "csrf_scav"
        account.current_village_id = 12345
        account.get_screen = AsyncMock(return_value=SAMPLE_SCAVENGE_HTML)

        mgr = ScavengeManager()
        state = await mgr.get_scavenge_state(account, village_id=12345)

        self.assertEqual(state.village_id, 12345)
        self.assertEqual(len(state.options), 4)
        self.assertEqual(len(state.unlocked_options), 2)  # 1 e 2
        self.assertEqual(len(state.ready_options), 1)     # apenas 1 (já que 2 está em expedição)
        self.assertEqual(state.active_expeditions_count, 1)
        self.assertEqual(state.available_troops.get("spear"), 120)

    async def test_scavenge_manager_unlock_option(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.csrf_token = "csrf_scav"
        account.post_action = AsyncMock(return_value="<html>ok</html>")

        mgr = ScavengeManager()
        success = await mgr.unlock_scavenge_option(account, option_id=3, village_id=12345)
        self.assertTrue(success)
        account.post_action.assert_called_once()

    def test_calculate_optimal_distribution(self):
        from engine.actions.scavenge import calculate_optimal_distribution

        ready_options = [
            ScavengeOption(id=1, name="Lazy", is_unlocked=True, is_scavenging=False, loot_ratio=0.10),
            ScavengeOption(id=2, name="Humble", is_unlocked=True, is_scavenging=False, loot_ratio=0.20),
            ScavengeOption(id=3, name="Clever", is_unlocked=True, is_scavenging=False, loot_ratio=0.50),
            ScavengeOption(id=4, name="Great", is_unlocked=True, is_scavenging=False, loot_ratio=0.75),
        ]
        available_troops = {"spear": 155, "sword": 155}
        dist = calculate_optimal_distribution(
            available_troops=available_troops,
            ready_options=ready_options,
            eligible_units=["spear", "sword"],
            min_reserved={"spear": 0, "sword": 0},
        )

        # Proporções: 10, 20, 50, 75
        self.assertEqual(dist[1]["spear"], 10)
        self.assertEqual(dist[2]["spear"], 20)
        self.assertEqual(dist[3]["spear"], 50)
        self.assertEqual(dist[4]["spear"], 75)

        self.assertEqual(dist[1]["sword"], 10)
        self.assertEqual(dist[2]["sword"], 20)
        self.assertEqual(dist[3]["sword"], 50)
        self.assertEqual(dist[4]["sword"], 75)

    async def test_execute_scavenge_cycle(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.csrf_token = "csrf_scav"
        account.current_village_id = 12345
        account.get_screen = AsyncMock(return_value=SAMPLE_SCAVENGE_HTML)
        account.post_action = AsyncMock(return_value="<html>ok</html>")

        mgr = ScavengeManager()
        from unittest.mock import MagicMock
        cfg = MagicMock()
        cfg.auto_unlock = True
        cfg.eligible_units = ["spear", "sword"]
        cfg.min_reserved_units = {"spear": 20}

        res = await mgr.execute_scavenge_cycle(account, cfg, village_id=12345)
        self.assertEqual(res["status"], "success")
        self.assertGreaterEqual(len(res["sent_expeditions"]), 1)
        account.post_action.assert_called()


class TestScavengeApi(unittest.TestCase):

    def setUp(self):
        from fastapi.testclient import TestClient
        from engine.api.server import create_app
        from engine.api.context import EngineContext
        from engine.config.settings import BotConfig
        from engine.core.account import TribalAccount

        self.account = TribalAccount(world="pt117", sid="test_sid")
        self.account.current_village_id = 12345
        self.account.get_screen = AsyncMock(return_value=SAMPLE_SCAVENGE_HTML)

        self.cfg = BotConfig(world="pt117")
        self.ctx = EngineContext(account=self.account, config=self.cfg)
        self.token = "test_token_scavenge"
        self.app = create_app(self.ctx, token=self.token, attach_log_handler=False)
        self.client = TestClient(self.app, headers={"X-Engine-Token": self.token})

    def test_get_scavenge_status_endpoint(self):
        res = self.client.get("/api/scavenge/status?village_id=12345")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["options"]), 4)


if __name__ == "__main__":
    unittest.main()


