"""
Testes Unitários para o MultiVillageCoordinator e Categorização de Aldeias.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock

from engine.actions.village_coordinator import MultiVillageCoordinator
from engine.config.settings import BotConfig, VillageConfig
from engine.core.account import TribalAccount
from engine.core.models import (
    CATEGORY_BUILDING_TEMPLATES,
    CATEGORY_RECRUITMENT_TARGETS,
    Resources,
    VillageCategory,
    VillageData,
)


class TestVillageCoordinator(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.coordinator = MultiVillageCoordinator()
        self.config = BotConfig(
            world="pt117",
            villages={
                "101": VillageConfig(category="attack"),
                "102": VillageConfig(category="defense"),
            },
        )
        self.account = TribalAccount(world="pt117", sid="test_sid")

        # Configura duas aldeias simuladas
        v1 = VillageData(
            id=101,
            name="Aldeia Ataque",
            x=500,
            y=500,
            category=VillageCategory.ATTACK,
            resources=Resources(wood=8000, stone=7000, iron=9000, storage_max=10000, pop=1200, pop_max=2000),
        )
        v2 = VillageData(
            id=102,
            name="Aldeia Defesa",
            x=502,
            y=501,
            category=VillageCategory.DEFENSE,
            resources=Resources(wood=1000, stone=1200, iron=800, storage_max=10000, pop=800, pop_max=2000),
        )
        self.account.villages = {101: v1, 102: v2}
        self.account.current_village_id = 101

    def test_get_and_set_village_category(self):
        """Testa consulta e alteração dinâmica da categoria de uma aldeia."""
        cat1 = self.coordinator.get_village_category(self.account, self.config, 101)
        self.assertEqual(cat1, VillageCategory.ATTACK)

        cat2 = self.coordinator.get_village_category(self.account, self.config, 102)
        self.assertEqual(cat2, VillageCategory.DEFENSE)

        # Altera categoria da aldeia 102 para attack
        self.coordinator.set_village_category(self.account, self.config, 102, "attack")
        self.assertEqual(self.coordinator.get_village_category(self.account, self.config, 102), VillageCategory.ATTACK)

    def test_category_building_plans(self):
        """Testa se o plano de construção reflete a categoria da aldeia."""
        plan_atk = self.config.get_active_build_plan(village_id="101")
        # Template military_rush deve conter quartel (barracks) ou estábulo (stable)
        buildings_in_plan = [b[0] for b in plan_atk]
        self.assertIn("barracks", buildings_in_plan)

        # Aldeia 102 (defesa)
        plan_def = self.config.get_active_build_plan(village_id="102")
        self.assertTrue(len(plan_def) > 0)

    def test_category_recruitment_targets(self):
        """Testa se as metas de recrutamento correspondem aos arquétipos da categoria."""
        targets_atk = self.config.get_village_recruitment_targets(village_id="101")
        self.assertIn("axe", targets_atk)
        self.assertIn("light", targets_atk)

        targets_def = self.config.get_village_recruitment_targets(village_id="102")
        self.assertIn("spear", targets_def)
        self.assertIn("sword", targets_def)

    def test_calculate_resource_balance(self):
        """Testa cálculo de balanceamento de recursos entre aldeias (doadoras vs recetoras)."""
        balance = self.coordinator.calculate_resource_balance(self.account)
        self.assertEqual(balance["total_villages"], 2)
        self.assertIn("averages", balance)

        # Aldeia 101 tem recursos elevados -> doadora
        donor_ids = [d["village_id"] for d in balance["donors"]]
        self.assertIn(101, donor_ids)

        # Aldeia 102 tem recursos baixos -> recetora
        receiver_ids = [r["village_id"] for r in balance["receivers"]]
        self.assertIn(102, receiver_ids)

    async def test_run_coordinated_cycle(self):
        """Testa execução do ciclo coordenado chamando as rotinas para cada aldeia."""
        self.coordinator.main_building_manager = MagicMock()
        self.coordinator.main_building_manager.run_build_cycle = AsyncMock(return_value={"upgraded": "barracks"})

        self.coordinator.recruitment_manager = MagicMock()
        self.coordinator.recruitment_manager.run_recruitment_cycle = AsyncMock(return_value={"axe": 15})

        self.config.recruitment.enabled = True
        res = await self.coordinator.run_coordinated_cycle(self.account, self.config)

        self.assertEqual(res["villages_processed"], 2)
        self.assertEqual(res["building_actions"], 2)
        self.assertEqual(res["recruitment_actions"], 2)
        self.assertEqual(len(res["details"]), 2)


if __name__ == "__main__":
    unittest.main()
