"""
Testes Unitários para o Módulo de Estatísticas & Métricas de Rendimento (engine/core/stats.py).
Validação de agregação de baldes horários, taxas de saque, comandos, persistência e rotas REST.
"""

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from engine.core.stats import StatsTracker, HourlyBucket, LootEvent, RecruitmentEvent, CommandEvent
from engine.config.settings import BotConfig, BuildingConfig, FarmConfig, RecruitmentConfig, QuestConfig, MarketConfig
from engine.api.context import EngineContext
from engine.api.routes import create_api_router
from fastapi.testclient import TestClient
from fastapi import FastAPI


class TestStatsTracker(unittest.TestCase):
    """Testes para o motor de rastreio de estatísticas e séries temporais."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / ".stats_cache"
        self.tracker = StatsTracker(world="pt_test_99", cache_dir=self.cache_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initial_state(self):
        summary = self.tracker.get_summary()
        self.assertEqual(summary["world"], "pt_test_99")
        self.assertEqual(summary["totals_all_time"]["total"], 0)
        self.assertEqual(summary["totals_all_time"]["villages_farmed"], 0)
        self.assertEqual(summary["totals_all_time"]["attacks_sent"], 0)
        self.assertEqual(summary["totals_all_time"]["success_rate"], 100.0)
        self.assertEqual(summary["last_24h"]["total"], 0)
        self.assertEqual(summary["last_24h"]["hourly_rate"], 0)

    def test_record_farm_loot(self):
        # Regista 3 saques
        self.tracker.record_farm_loot(wood=100, stone=200, iron=150, target_x=500, target_y=500)
        self.tracker.record_farm_loot(wood=50, stone=50, iron=50, target_x=501, target_y=501)
        self.tracker.record_farm_loot(wood=300, stone=100, iron=200, target_x=502, target_y=502, losses=True)

        summary = self.tracker.get_summary()
        tot = summary["totals_all_time"]
        self.assertEqual(tot["wood"], 450)
        self.assertEqual(tot["stone"], 350)
        self.assertEqual(tot["iron"], 400)
        self.assertEqual(tot["total"], 1200)
        self.assertEqual(tot["villages_farmed"], 3)

        l24 = summary["last_24h"]
        self.assertEqual(l24["total"], 1200)
        self.assertEqual(l24["villages_farmed"], 3)
        self.assertGreater(l24["hourly_rate"], 0)

    def test_record_recruitment(self):
        self.tracker.record_recruitment(unit="spear", count=10)
        self.tracker.record_recruitment(unit="sword", count=5)
        self.tracker.record_recruitment(unit="spear", count=15)

        summary = self.tracker.get_summary()
        self.assertEqual(summary["totals_all_time"]["troops_recruited"], 30)
        self.assertEqual(summary["recruitment_by_unit"]["spear"], 25)
        self.assertEqual(summary["recruitment_by_unit"]["sword"], 5)

    def test_record_commands_and_success_rate(self):
        self.tracker.record_command("attack", "500|500", {"spear": 10}, success=True)
        self.tracker.record_command("attack", "501|501", {"spear": 10}, success=True)
        self.tracker.record_command("attack", "502|502", {"spear": 10}, success=False)

        summary = self.tracker.get_summary()
        tot = summary["totals_all_time"]
        self.assertEqual(tot["attacks_sent"], 3)
        self.assertEqual(tot["attacks_successful"], 2)
        self.assertEqual(tot["attacks_failed"], 1)
        self.assertEqual(tot["success_rate"], 66.7)

    def test_record_building_upgrade(self):
        self.tracker.record_building_upgrade(village_id=123, building="main", from_level=1, to_level=2)
        summary = self.tracker.get_summary()
        self.assertEqual(summary["totals_all_time"]["buildings_constructed"], 1)

    def test_history_series_generation(self):
        self.tracker.record_farm_loot(wood=1000, stone=1000, iron=1000, target_x=500, target_y=500)
        
        history = self.tracker.get_history(hours=24, days=7)
        self.assertIn("hourly", history)
        self.assertIn("daily", history)
        self.assertEqual(len(history["hourly"]), 24)
        self.assertEqual(len(history["daily"]), 7)

        # O balde mais recente deve conter o saque
        latest_bucket = history["hourly"][-1]
        self.assertEqual(latest_bucket["total"], 3000)
        self.assertEqual(latest_bucket["wood"], 1000)

    def test_persistence_save_and_load(self):
        self.tracker.record_farm_loot(wood=500, stone=600, iron=700, target_x=510, target_y=510)
        self.tracker.record_recruitment("light", 20)
        self.tracker._save_to_disk()

        # Instancia novo tracker apontando para o mesmo ficheiro
        new_tracker = StatsTracker(world="pt_test_99", cache_dir=self.cache_dir)
        summary = new_tracker.get_summary()
        self.assertEqual(summary["totals_all_time"]["total"], 1800)
        self.assertEqual(summary["totals_all_time"]["troops_recruited"], 20)
        self.assertEqual(summary["recruitment_by_unit"]["light"], 20)

    def test_reset_stats(self):
        self.tracker.record_farm_loot(wood=500, stone=500, iron=500, target_x=500, target_y=500)
        self.tracker.reset_stats()

        summary = self.tracker.get_summary()
        self.assertEqual(summary["totals_all_time"]["total"], 0)
        self.assertEqual(summary["totals_all_time"]["villages_farmed"], 0)

    def test_legacy_stats_merging(self):
        # Simula criação de ficheiro legado stats_default_{world}.json
        legacy_file = self.cache_dir / f"stats_default_{self.tracker.world}.json"
        legacy_data = {
            "world": self.tracker.world,
            "created_at": time.time(),
            "last_updated": time.time(),
            "total_wood": 5000,
            "total_stone": 5000,
            "total_iron": 5000,
            "total_attacks_sent": 100,
            "total_attacks_successful": 100,
            "total_villages_farmed": 80,
            "hourly_buckets": {
                "2026-09-01 12:00": {
                    "hour_key": "2026-09-01 12:00",
                    "timestamp": 1788200000.0,
                    "wood": 5000,
                    "stone": 5000,
                    "iron": 5000,
                    "total": 15000,
                    "attacks_count": 100,
                    "attacks_successful": 100,
                    "villages_farmed": 80,
                    "troops_recruited": 0,
                }
            },
            "recent_loot_events": [
                {
                    "timestamp": 1788200000.0,
                    "village_id": 1,
                    "target_x": 500,
                    "target_y": 500,
                    "wood": 500,
                    "stone": 500,
                    "iron": 500,
                    "total": 1500,
                    "wall": 0,
                    "losses": False,
                    "village_name": "Barb",
                }
            ],
            "recent_commands": [],
        }
        legacy_file.write_text(json.dumps(legacy_data), encoding="utf-8")

        # Nova instância com account_id="profile_new" (ficheiro vazio inicialmente)
        new_tracker = StatsTracker(world=self.tracker.world, cache_dir=self.cache_dir, account_id="profile_new")
        self.assertEqual(new_tracker.total_looted, 15000)
        self.assertEqual(new_tracker.total_attacks_sent, 100)
        self.assertEqual(len(new_tracker.recent_loot_events), 1)


class TestStatsApiRoutes(unittest.TestCase):
    """Testes para as rotas REST de estatísticas no FastAPI Sidecar."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cfg_file = Path(self.temp_dir) / "config.json"
        
        self.config = BotConfig(
            world="pt_api_test",
            sid="test_sid",
            building=BuildingConfig(),
            farm=FarmConfig(),
            recruitment=RecruitmentConfig(),
            quest=QuestConfig(),
            market=MarketConfig(),
        )
        from engine.core.scheduler import TaskScheduler
        from engine.core.account import TribalAccount
        from engine.core.models import Resources, VillageData
        
        self.scheduler = TaskScheduler(name="TestStatsScheduler")
        self.account = TribalAccount(world="pt_api_test", sid="test_sid")
        self.account.current_village_id = 100
        self.account.villages[100] = VillageData(
            id=100,
            name="Aldeia Stats",
            x=500,
            y=500,
            points=100,
            resources=Resources(wood=500, stone=500, iron=500, storage_max=2000, pop=20, pop_max=240),
        )
        
        self.context = EngineContext(
            scheduler=self.scheduler,
            config=self.config,
            account=self.account,
            config_path=self.cfg_file,
        )
        # Override cache_dir dos stats trackers para usar o temp_dir
        tracker = self.context.get_stats_tracker("pt_api_test")
        tracker.cache_dir = Path(self.temp_dir) / ".stats_cache"
        tracker.cache_file = Path(self.temp_dir) / ".stats_cache" / "stats_pt_api_test.json"

        # Cria FastAPI e TestClient
        from engine.api.server import create_app
        self.token = "test_stats_token_123"
        self.app = create_app(self.context, token=self.token, attach_log_handler=False)
        self.client = TestClient(self.app)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_stats_summary_endpoint(self):
        # Simula um evento de saque no tracker
        self.context.get_stats_tracker("pt_api_test").record_farm_loot(wood=100, stone=200, iron=300, target_x=500, target_y=500)

        headers = {"Authorization": f"Bearer {self.token}"}
        response = self.client.get("/api/stats/summary", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["summary"]["totals_all_time"]["total"], 600)
        self.assertEqual(data["summary"]["totals_all_time"]["wood"], 100)

    def test_get_stats_history_endpoint(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        response = self.client.get("/api/stats/history?hours=12&days=3", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["history"]["hourly"]), 12)
        self.assertEqual(len(data["history"]["daily"]), 3)

    def test_reset_stats_endpoint(self):
        self.context.get_stats_tracker("pt_api_test").record_farm_loot(wood=1000, stone=1000, iron=1000, target_x=500, target_y=500)
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = self.client.post("/api/stats/reset", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

        # Verifica que o summary voltou a zero
        summary_resp = self.client.get("/api/stats/summary", headers=headers)
        self.assertEqual(summary_resp.json()["summary"]["totals_all_time"]["total"], 0)


if __name__ == "__main__":
    unittest.main()

