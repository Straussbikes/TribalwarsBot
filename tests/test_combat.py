"""
Suíte de testes unitários para Táticas de Combate & Sincronização ao Milissegundo (Item 2.9).
Abrange ClockSynchronizer, Noble Train com Fail-Safe, Backtime, Sniper e API REST.
"""

import asyncio
import email.utils
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from engine.actions.combat_sync import ClockSynchronizer, ClockSyncStats
from engine.actions.combat_tactics import (
    CombatManager,
    NobleTrainPlan,
    BacktimePlan,
    SnipePlan,
    TacticalOperationStatus,
    TacticalOperationType,
    calculate_euclidean_distance,
    calculate_travel_duration,
)
from engine.actions.place import UnitType, UnitsCount
from engine.config.settings import BotConfig, CombatConfig


class TestClockSynchronizer(unittest.TestCase):
    """Testes unitários do ClockSynchronizer e medição de RTT/drift."""

    def setUp(self):
        self.sync = ClockSynchronizer(ewma_alpha=0.5)

    def test_record_sample_and_stats(self):
        t0 = 1000.0
        t1 = 1000.080  # 80ms RTT
        server_ts = 1000.040  # Servidor perfeitamente em sincronia com o ponto médio
        self.sync.record_sample(t0, t1, server_ts)

        stats = self.sync.get_stats()
        self.assertAlmostEqual(stats.rtt_ms, 80.0, places=1)
        self.assertAlmostEqual(stats.clock_offset_seconds, 0.0, places=3)
        self.assertTrue(stats.is_synchronized)
        self.assertEqual(stats.samples_count, 1)

    def test_clock_offset_calculation(self):
        # Local t0=100.0, t1=100.100 (midpoint=100.050). Servidor relata 105.050 (offset=+5s)
        self.sync.record_sample(100.0, 100.100, 105.050)
        self.assertAlmostEqual(self.sync.clock_offset, 5.0, places=3)

        # Testa conversões
        self.assertAlmostEqual(self.sync.local_to_server_time(200.0), 205.0, places=3)
        self.assertAlmostEqual(self.sync.server_to_local_time(205.0), 200.0, places=3)

    def test_parse_server_time_from_headers_and_html(self):
        # 1. Header HTTP Date
        now_dt = email.utils.formatdate(usegmt=True)
        headers = {"Date": now_dt}
        ts_hdr = self.sync.parse_server_time_from_headers_or_html(headers=headers)
        self.assertIsNotNone(ts_hdr)
        self.assertAlmostEqual(ts_hdr, time.time(), delta=2.0)

        # 2. Timing.initial_server_time em milissegundos
        html = '<script>Timing.initial_server_time = 1756840000000;</script>'
        ts_html = self.sync.parse_server_time_from_headers_or_html(html=html)
        self.assertEqual(ts_html, 1756840000.0)

        # 3. Elementos HTML serverTime / serverDate
        html_dom = '<div><span id="serverTime">14:30:00</span> <span id="serverDate">15/08/2026</span></div>'
        ts_dom = self.sync.parse_server_time_from_headers_or_html(html=html_dom)
        self.assertIsNotNone(ts_dom)

    def test_calculate_launch_time(self):
        # Servidor está adiantado em 2 segundos, RTT = 100ms (50ms one-way)
        self.sync.clock_offset = 2.0
        self.sync.rtt_ms = 100.0

        # Alvo: impacto no servidor em 1000s. Duração da marcha: 100s.
        # Partida no servidor: 900s.
        # Partida local: 900s - 2s (offset) - 0.05s (one-way latency) = 897.95s
        launch_local = self.sync.calculate_launch_time(
            target_impact_server_ts=1000.0,
            travel_duration_seconds=100.0,
        )
        self.assertAlmostEqual(launch_local, 897.95, places=2)

    def test_spin_wait_until(self):
        async def run_wait():
            target = time.time() + 0.020  # 20ms no futuro
            drift = await self.sync.spin_wait_until(target)
            self.assertGreaterEqual(time.time(), target)
            self.assertLess(drift, 0.015)  # Drift inferior a 15ms

        asyncio.run(run_wait())


class TestCombatManager(unittest.TestCase):
    """Testes unitários da lógica de combate, Noble Train, Backtime e Sniper."""

    def setUp(self):
        self.mock_place = MagicMock()
        self.mock_clock = MagicMock()
        self.mock_clock.server_to_local_time.side_effect = lambda t: t
        self.mock_clock.get_server_time.side_effect = lambda: time.time()
        self.mock_clock.calculate_launch_time.side_effect = lambda tgt, dur: tgt - dur - 0.05
        self.mock_clock.spin_wait_until = AsyncMock(return_value=0.001)

        self.manager = CombatManager(place_manager=self.mock_place, clock_sync=self.mock_clock)

        self.mock_account = MagicMock()
        self.mock_account.world = "pt117"
        self.mock_account.current_village_id = 1234
        self.mock_account.villages = {
            1234: MagicMock(id=1234, x=500, y=500, name="Aldeia Alpha"),
            5678: MagicMock(id=5678, x=503, y=504, name="Aldeia Beta"),
        }

    def test_euclidean_distance_and_travel_duration(self):
        dist = calculate_euclidean_distance("500|500", "503|504")
        self.assertAlmostEqual(dist, 5.0, places=3)  # sqrt(3^2 + 4^2) = 5.0

        # Nobre (35 min/campo = 2100s/campo em speed 1.0)
        dur_snob = calculate_travel_duration("500|500", "503|504", UnitType.SNOB, 1.0, 1.0)
        self.assertAlmostEqual(dur_snob, 5.0 * 35.0 * 60.0, places=1)

        # Cavalaria Leve (10 min/campo = 600s/campo)
        dur_light = calculate_travel_duration("500|500", "503|504", UnitType.LIGHT, 1.0, 1.0)
        self.assertAlmostEqual(dur_light, 5.0 * 10.0 * 60.0, places=1)

    def test_execute_noble_train_success(self):
        async def run_test():
            # Mock de preparação e confirmação
            self.mock_place.prepare_command = AsyncMock(return_value={
                "success": True,
                "hidden_fields": {"chck": "token123", "action_id": "456"},
            })
            self.mock_account.post_action = AsyncMock(return_value="""
                <div class="command_id">12345</div>
            """)

            plan = NobleTrainPlan(
                target_coords="503|504",
                train_size=4,
                nuke_units=UnitsCount(axe=1000, light=500, ram=50),
                escort_units=UnitsCount(axe=50, light=20),
                gap_ms=50,
                failsafe_enabled=True,
                failsafe_max_spread_ms=500,
            )

            op = await self.manager.execute_noble_train(self.mock_account, plan, village_id=1234)
            self.assertEqual(op.status, TacticalOperationStatus.COMPLETED)
            self.assertEqual(len(op.sub_commands), 4)
            for cmd in op.sub_commands:
                self.assertTrue(cmd.success)
                self.assertFalse(cmd.is_cancelled)

        asyncio.run(run_test())

    def test_execute_noble_train_failsafe_triggered(self):
        async def run_test():
            self.mock_place.prepare_command = AsyncMock(return_value={
                "success": True,
                "hidden_fields": {"chck": "token123"},
            })
            self.mock_place.cancel_command = AsyncMock(return_value=True)

            # Simula que o 3º ataque falha
            call_count = 0
            async def mock_post_action(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 3:
                    raise Exception("Network Timeout on Attack #3")
                return '<div class="command_id">cmd_999</div>'

            self.mock_account.post_action = mock_post_action

            plan = NobleTrainPlan(
                target_coords="503|504",
                train_size=4,
                gap_ms=50,
                failsafe_enabled=True,
            )

            op = await self.manager.execute_noble_train(self.mock_account, plan, village_id=1234)
            self.assertEqual(op.status, TacticalOperationStatus.CANCELLED_FAILSAFE)
            self.assertTrue(op.details.get("failsafe_triggered"))
            # Garante que place.cancel_command foi chamado para resgatar os nobres que saíram
            self.assertGreaterEqual(self.mock_place.cancel_command.call_count, 1)

        asyncio.run(run_test())

    def test_calculate_and_schedule_backtime(self):
        async def run_test():
            now = time.time()
            # Inimigo regressa em 10 minutos (600s). Duração da nossa CL para 5 campos = 3000s (5 * 600s)
            # Para o backtime ser viável, inimigo regressa em 5000s
            enemy_ret = now + 5000.0

            calc = self.manager.calculate_backtime(
                origin_coords="500|500",
                target_coords="503|504",
                enemy_return_server_ts=enemy_ret,
                slowest_unit=UnitType.LIGHT,
            )
            self.assertTrue(calc["is_feasible"])
            self.assertGreater(calc["time_until_launch_seconds"], 0)

            plan = BacktimePlan(
                target_coords="503|504",
                enemy_return_server_ts=enemy_ret,
                units=UnitsCount(light=200),
                slowest_unit=UnitType.LIGHT,
            )
            op = await self.manager.schedule_backtime(self.mock_account, plan, village_id=1234)
            self.assertEqual(op.status, TacticalOperationStatus.SCHEDULED)
            self.assertEqual(op.operation_type, TacticalOperationType.BACKTIME)

        asyncio.run(run_test())

    def test_analyze_snipes(self):
        now = time.time()
        # Simula 2 ataques a chegar à nossa aldeia (500|500):
        # 1. Nuke chega em now + 1000s
        # 2. Nobre chega em now + 1000.150s (gap = 150ms)
        incomings = [
            {
                "command_id": "atk_nuke_1",
                "origin_coords": "510|510",
                "target_coords": "500|500",
                "arrival_timestamp": now + 1000.0,
            },
            {
                "command_id": "atk_noble_2",
                "origin_coords": "510|510",
                "target_coords": "500|500",
                "arrival_timestamp": now + 1000.150,
            },
        ]
        own_villages = [
            {"id": 1234, "x": 500, "y": 500},
            {"id": 5678, "x": 501, "y": 501},
        ]

        suggestions = self.manager.analyze_snipes(incomings, own_villages)
        self.assertGreaterEqual(len(suggestions), 1)

        # Deve haver sugestão de Return Snipe na aldeia alvo
        return_snipes = [s for s in suggestions if s["snipe_type"] == "cancel_return"]
        self.assertEqual(len(return_snipes), 1)
        self.assertAlmostEqual(return_snipes[0]["window_gap_ms"], 150.0, delta=1.0)


class TestCombatApiRoutes(unittest.TestCase):
    """Testes dos endpoints REST /api/combat/*."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from engine.api.server import create_app
        from engine.api.context import EngineContext

        self.cfg = BotConfig(world="pt117")
        self.ctx = EngineContext(config=self.cfg)
        self.token = "test_token_combat"
        self.app = create_app(self.ctx, token=self.token, attach_log_handler=False)
        self.client = TestClient(self.app, headers={"X-Engine-Token": self.token})

    def test_combat_status_endpoint(self):
        res = self.client.get("/api/combat/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("clock_stats", data)
        self.assertIn("operations", data)
        self.assertIn("noble_train_gap_ms", data["config"])

    def test_backtime_calculate_endpoint(self):
        payload = {
            "origin_coords": "500|500",
            "target_coords": "503|504",
            "enemy_return_server_ts": time.time() + 10000,
            "slowest_unit": "light",
        }
        res = self.client.post("/api/combat/backtime/calculate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("calculation", data)
        self.assertAlmostEqual(data["calculation"]["distance_fields"], 5.0, places=1)

    def test_snipe_analyze_endpoint(self):
        res = self.client.post("/api/combat/snipe/analyze", json={})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("suggestions", data)

    def test_combat_config_endpoint(self):
        payload = {
            "noble_train_gap_ms": 75,
            "failsafe_enabled": True,
            "failsafe_max_spread_ms": 350,
        }
        res = self.client.post("/api/combat/config", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["combat_config"]["noble_train_gap_ms"], 75)
        self.assertEqual(data["combat_config"]["failsafe_max_spread_ms"], 350)


if __name__ == "__main__":
    unittest.main()
