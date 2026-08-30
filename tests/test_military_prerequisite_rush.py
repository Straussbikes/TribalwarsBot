"""
Unit and Integration Tests for Military Prerequisite Rush (Vikings and Light Cavalry / CL).
Verifies that when Barracks or Stable are idle due to unmet requirements, the bot
rushes the required buildings and tech research with maximum priority over standard templates.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from engine.actions.main_building import (
    BuildingType,
    BuildingUpgrade,
    MainBuildingManager,
    MainBuildingState,
)
from engine.actions.recruitment import RecruitmentManager, RecruitmentState
from engine.actions.smith import SmithManager, SmithState, SmithUnitInfo
from engine.core.account import TribalAccount
from engine.core.models import Resources


class TestMilitaryPrerequisiteRush(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mb_manager = MainBuildingManager()
        self.smith_manager = SmithManager()
        self.rec_manager = RecruitmentManager(smith_manager=self.smith_manager)

    def test_viking_prerequisite_rush_steps_generation(self):
        """Valida que a cadeia de pré-requisitos para Vikings (axe) é gerada na ordem correta."""
        # Aldeia inicial: main 1, barracks 0, smith 0
        virt_levels = {"main": 1, "barracks": 0, "smith": 0, "wood": 5, "stone": 5, "iron": 5}
        rec_targets = {"axe": 50, "spear": 20}

        rush_steps = self.mb_manager.get_prerequisite_rush_steps(rec_targets, virt_levels)
        self.assertGreater(len(rush_steps), 0)

        # Deve conter main 3, barracks 1, main 5, smith 1, barracks 2, smith 2
        self.assertIn(("main", 3), rush_steps)
        self.assertIn(("barracks", 1), rush_steps)
        self.assertIn(("main", 5), rush_steps)
        self.assertIn(("smith", 1), rush_steps)
        self.assertIn(("barracks", 2), rush_steps)
        self.assertIn(("smith", 2), rush_steps)

    def test_viking_rush_takes_precedence_over_normal_building_plan(self):
        """Valida que o rush de Vikings substitui o plano padrão de edifícios mesmo se houver plano de recursos."""
        state = MainBuildingState(
            village_id=1001,
            buildings={"main": 1, "barracks": 0, "smith": 0, "wood": 1, "stone": 1, "iron": 1},
            queue=[],
            upgrades={
                "main": BuildingUpgrade(building="main", current_level=1, target_level=2, wood=100, stone=100, iron=100, pop=2, can_build=True),
                "wood": BuildingUpgrade(building="wood", current_level=1, target_level=2, wood=50, stone=50, iron=50, pop=1, can_build=True),
            },
        )
        # Plano padrão prioriza Bosque (wood) até ao nível 10
        normal_plan = [("wood", 10), ("stone", 10), ("iron", 10)]
        resources = Resources(wood=1000, stone=1000, iron=1000, storage_max=5000, pop=10, pop_max=100)

        # Sem metas de Vikings: escolhe Bosque do plano normal
        candidate_normal = self.mb_manager.get_next_build_candidate(
            state=state,
            plan=normal_plan,
            resources=resources,
            recruitment_targets={"spear": 10},
        )
        self.assertIsNotNone(candidate_normal)
        self.assertEqual(candidate_normal.building, "wood")

        # Com metas de Vikings (axe > 0): escolhe Edifício Principal para desbloquear Quartel
        candidate_rush = self.mb_manager.get_next_build_candidate(
            state=state,
            plan=normal_plan,
            resources=resources,
            recruitment_targets={"axe": 100},
        )
        self.assertIsNotNone(candidate_rush)
        self.assertEqual(candidate_rush.building, "main")
        self.assertTrue(candidate_rush.is_rush)

    def test_cl_light_prerequisite_rush_steps_generation(self):
        """Valida a cadeia de pré-requisitos para Cavalaria Leve (CL)."""
        # Aldeia com quartel 2 e ferreiro 2 (Vikings prontos, mas sem estábulo)
        virt_levels = {"main": 5, "barracks": 2, "smith": 2, "stable": 0}
        rec_targets = {"light": 30}

        rush_steps = self.mb_manager.get_prerequisite_rush_steps(rec_targets, virt_levels)
        self.assertGreater(len(rush_steps), 0)

        # Deve conter barracks 5, smith 5, main 10, stable 1, stable 2, stable 3
        self.assertIn(("barracks", 5), rush_steps)
        self.assertIn(("smith", 5), rush_steps)
        self.assertIn(("main", 10), rush_steps)
        self.assertIn(("stable", 1), rush_steps)
        self.assertIn(("stable", 2), rush_steps)
        self.assertIn(("stable", 3), rush_steps)

    def test_cl_rush_takes_precedence_over_normal_building_plan(self):
        """Valida que o rush de CL avança Quartel, Ferreiro, EP e Estábulo até ao nível 3."""
        state = MainBuildingState(
            village_id=1001,
            buildings={"main": 5, "barracks": 2, "smith": 2, "stable": 0, "wood": 10},
            queue=[],
            upgrades={
                "barracks": BuildingUpgrade(building="barracks", current_level=2, target_level=3, wood=200, stone=200, iron=200, pop=2, can_build=True),
                "wood": BuildingUpgrade(building="wood", current_level=10, target_level=11, wood=100, stone=100, iron=100, pop=1, can_build=True),
            },
        )
        normal_plan = [("wood", 20), ("stone", 20)]
        resources = Resources(wood=2000, stone=2000, iron=2000, storage_max=5000, pop=10, pop_max=100)

        candidate = self.mb_manager.get_next_build_candidate(
            state=state,
            plan=normal_plan,
            resources=resources,
            recruitment_targets={"light": 50},
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.building, "barracks")
        self.assertTrue(candidate.is_rush)

    async def test_smith_auto_research_priority_for_vikings_and_cl(self):
        """Valida que o Ferreiro prioriza a pesquisa de Vikings e CL quando disponíveis."""
        account = TribalAccount(world="pt117", sid="test_sid")
        account.csrf_token = "csrf_token_xyz"
        account.villages = {1001: MagicMock(buildings={"smith": 5, "stable": 3, "barracks": 5})}

        # Simula resposta do Ferreiro com spear, axe e light disponíveis para pesquisa
        smith_state = SmithState(
            village_id=1001,
            smith_level=5,
            units={
                "spear": SmithUnitInfo(unit="spear", status="researched", level=1),
                "sword": SmithUnitInfo(unit="sword", status="can_research", wood=500, stone=400, iron=300),
                "axe": SmithUnitInfo(unit="axe", status="can_research", wood=700, stone=600, iron=600),
                "light": SmithUnitInfo(unit="light", status="can_research", wood=2200, stone=2400, iron=2000),
            },
            queue=[],
        )

        self.smith_manager.get_smith_state = AsyncMock(return_value=smith_state)
        self.smith_manager.research_unit = AsyncMock(return_value=True)

        # Com metas de axe e light, deve priorizar axe ou light em vez de sword
        researched = await self.smith_manager.auto_research_needed_units(
            account=account,
            village_id=1001,
            needed_units=["sword", "axe", "light"],
        )

        self.assertEqual(len(researched), 1)
        self.assertEqual(researched[0], "axe")
        self.smith_manager.research_unit.assert_called_once_with(account, "axe", village_id=1001)


if __name__ == "__main__":
    unittest.main()
