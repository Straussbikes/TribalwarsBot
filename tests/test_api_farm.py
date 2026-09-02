"""
Suíte de Testes Automatizados para os Endpoints REST de Farm & Radar de Inativos (Fase 3).
"""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from engine.api.context import EngineContext
from engine.api.server import create_app
from engine.config.settings import BotConfig, FarmConfig
from engine.actions.place import UnitsCount
from engine.core.account import TribalAccount
from engine.core.models import Resources, VillageData
from engine.core.scheduler import TaskScheduler
from engine.storage.world_database import WorldDatabase, WorldVillageRecord, WorldPlayerRecord, WorldAllyRecord


class TestApiFarmAndRadar(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_world.db"
        self.world_db = WorldDatabase(db_path=self.db_path)

        self.config = BotConfig(
            world="pt117",
            sid="test_token_sid",
            farm=FarmConfig(enabled=False, default_template="A", max_distance=20.0),
        )

        self.scheduler = TaskScheduler(name="TestFarmApiScheduler")
        self.account = TribalAccount(world="pt117", sid="test_sid")
        self.account.current_village_id = 6810
        self.account.villages[6810] = VillageData(
            id=6810,
            name="Aldeia Teste",
            x=450,
            y=550,
            points=150,
            resources=Resources(wood=500, stone=500, iron=500, storage_max=1000, pop=40, pop_max=240),
            troops=UnitsCount(spear=50, sword=20, axe=100, spy=10, light=40),
        )

        self.context = EngineContext(
            scheduler=self.scheduler,
            config=self.config,
            account=self.account,
            config_path=Path(self.temp_dir.name) / "config.json",
        )
        self.context.world_database = self.world_db
        self.context.inactivity_tracker.db = self.world_db

        self.token = "test_token_farm_radar_999"
        self.app = create_app(self.context, token=self.token, attach_log_handler=False)
        self.client = TestClient(self.app)
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_farm_status_endpoint(self):
        response = self.client.get("/api/farm/status", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["world"], "pt117")
        self.assertEqual(data["village_coords"], "450|550")
        self.assertFalse(data["enabled"])
        self.assertEqual(data["available_troops"]["light"], 40)

    def test_farm_status_with_dict_troops(self):
        # Garante resiliência quando v.troops é um dict puro
        self.account.villages[6810].troops = {"spear": 12, "light": 8}
        response = self.client.get("/api/farm/status", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["available_troops"]["light"], 8)
        self.assertEqual(data["available_troops"]["spear"], 12)

    def test_farm_toggle_endpoint(self):
        response = self.client.post(
            "/api/farm/toggle",
            json={"enabled": True},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(self.config.farm.enabled)

    def test_farm_config_endpoint(self):
        response = self.client.post(
            "/api/farm/config",
            json={"default_template": "B", "max_distance": 35.0, "min_interval_seconds": 60.0},
            headers=self.auth_headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["farm"]["default_template"], "B")
        self.assertEqual(data["farm"]["max_distance"], 35.0)
        self.assertEqual(self.config.farm.default_template, "B")

    def test_farm_trigger_endpoint(self):
        mock_run = AsyncMock(return_value={"attacks_sent": 5, "targets_count": 8})
        with patch.object(self.context.farm_manager, "run_comprehensive_radius_farm_cycle", mock_run):
            response = self.client.post(
                "/api/farm/trigger",
                json={"force": True},
                headers=self.auth_headers,
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["results"]["attacks_sent"], 5)

    def test_farm_targets_endpoint(self):
        from engine.actions.farm import FarmAssistantState, FarmTarget
        mock_am_state = FarmAssistantState(
            village_id=6810,
            targets=[
                FarmTarget(
                    target_id="101",
                    target_name="Aldeia Bárbara",
                    target_coords="451|551",
                    distance=1.4,
                    report_color="green",
                    loot_status="full",
                    wall_level=0,
                    template_a_available=True,
                )
            ],
            template_a_troops={"light": 5},
            template_b_troops={"light": 10},
        )
        with patch.object(self.context.farm_manager, "get_am_farm_state", AsyncMock(return_value=mock_am_state)), \
             patch.object(self.context.farm_manager, "discover_all_radius_barbarians", AsyncMock(return_value=mock_am_state.targets)):
            response = self.client.get("/api/farm/targets", headers=self.auth_headers)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["targets"][0]["coordinates"], "451|551")
            self.assertTrue(data["targets"][0]["can_attack_a"])

    def test_update_farm_template_endpoint(self):
        mock_save = AsyncMock(return_value={
            "status": "success",
            "template": "A",
            "units": {"light": 4, "spy": 1},
            "haul_capacity": 320,
        })
        with patch.object(self.context.farm_manager, "save_am_farm_template", mock_save):
            response = self.client.post(
                "/api/farm/templates",
                json={"template": "A", "units": {"light": 4, "spy": 1}},
                headers=self.auth_headers,
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["template"], "A")
            self.assertEqual(data["haul_capacity"], 320)

    def test_radar_endpoints_flow(self):
        # 1. Popula base de dados com snapshot
        self.world_db.save_world_snapshot(
            world="pt117",
            villages=[
                WorldVillageRecord(id=10, name="Aldeia Inativa 1", x=452, y=552, player_id=201, points=800, rank=1),
                WorldVillageRecord(id=11, name="Aldeia Inativa 2", x=455, y=555, player_id=202, points=1200, rank=2),
            ],
            players=[
                WorldPlayerRecord(id=201, name="Inativo Um", ally_id=0, villages_count=1, points=800, rank=1),
                WorldPlayerRecord(id=202, name="Inativo Dois", ally_id=0, villages_count=1, points=1200, rank=2),
            ],
            allies=[],
            custom_timestamp=1700000000.0,
        )

        # 2. Testa GET /api/radar/sync-status
        res_sync = self.client.get("/api/radar/sync-status", headers=self.auth_headers)
        self.assertEqual(res_sync.status_code, 200)
        sync_data = res_sync.json()
        self.assertTrue(sync_data["has_snapshot"])
        self.assertEqual(sync_data["total_villages"], 2)

        # 3. Testa GET /api/radar/inactives
        res_inactives = self.client.get(
            "/api/radar/inactives?max_distance=25.0&only_tribeless=true",
            headers=self.auth_headers,
        )
        self.assertEqual(res_inactives.status_code, 200)
        inact_data = res_inactives.json()
        self.assertEqual(inact_data["status"], "success")
        self.assertEqual(inact_data["total_targets_found"], 2)
        self.assertEqual(inact_data["targets"][0]["coordinates"], "452|552")
        self.assertTrue("light_travel_time_str" in inact_data["targets"][0])

        # 4. Testa POST /api/radar/targets/add
        res_add = self.client.post(
            "/api/radar/targets/add",
            json={"coords": "452|552"},
            headers=self.auth_headers,
        )
        self.assertEqual(res_add.status_code, 200)
        self.assertIn("452|552", self.config.farm.custom_targets)


if __name__ == "__main__":
    unittest.main()
