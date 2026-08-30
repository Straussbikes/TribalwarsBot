"""
Testes Unitários para o Sistema de Configurações (engine/config).
"""

import json
import os
import tempfile
import unittest

from engine.actions.main_building import (
    DEFAULT_BUILD_PLAN,
    DEFAULT_BUILDING_TEMPLATE,
)
from engine.config.settings import BotConfig, BuildingConfig, load_config


class TestConfig(unittest.TestCase):
    def test_default_config_templates(self):
        cfg = BotConfig(building=BuildingConfig(template="default_plan"))
        self.assertEqual(cfg.get_active_build_plan(), DEFAULT_BUILD_PLAN)

        custom = [("wood", 1), ("stone", 1)]
        cfg.building.template = "custom"
        cfg.building.custom_plan = custom
        self.assertEqual(cfg.get_active_build_plan(), custom)

    def test_load_from_json_file(self):
        payload = {
            "world": "pt999",
            "sid": "cookie_xyz_123",
            "building": {
                "template": "custom",
                "max_queue": 3,
                "interval_seconds": 90.0,
                "custom_plan": [
                    ["wood", 5],
                    ["stone", 5],
                    ["iron", 3]
                ]
            }
        }
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as tmp:
            json.dump(payload, tmp)
            tmp_path = tmp.name

        try:
            cfg = load_config(tmp_path)
            self.assertEqual(cfg.world, "pt999")
            self.assertEqual(cfg.sid, "cookie_xyz_123")
            self.assertEqual(cfg.building.template, "custom")
            self.assertEqual(cfg.building.max_queue, 3)
            self.assertEqual(cfg.building.interval_seconds, 90.0)
            self.assertEqual(
                cfg.get_active_build_plan(),
                [("wood", 5), ("stone", 5), ("iron", 3)]
            )
        finally:
            os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
