"""
Testes unitários para a rotina de Priorização Automática da Fazenda em População Crítica (Emergência de Fazenda).
"""

import unittest
from engine.actions.main_building import (
    BuildingType,
    BuildingUpgrade,
    MainBuildingManager,
    MainBuildingState,
    QueueOrder,
)
from engine.config.settings import BuildingConfig
from engine.core.models import Resources


class TestEmergencyFarmPriority(unittest.TestCase):
    def setUp(self):
        self.manager = MainBuildingManager()
        self.default_plan = [
            (BuildingType.MAIN, 15),
            (BuildingType.WOOD, 20),
            (BuildingType.STONE, 20),
        ]

    def test_emergency_farm_triggers_when_free_pop_below_threshold(self):
        """Valida que quando free_pop <= threshold (ex: 40 <= 50), prioriza a Fazenda antes do plano regular."""
        state = MainBuildingState(
            village_id=12345,
            buildings={"main": 10, "farm": 12, "storage": 15},
            queue=[],
            upgrades={
                "farm": BuildingUpgrade(
                    building="farm",
                    current_level=12,
                    target_level=13,
                    wood=450,
                    stone=400,
                    iron=300,
                    pop=0,
                    can_build=True,
                ),
                "main": BuildingUpgrade(
                    building="main",
                    current_level=10,
                    target_level=11,
                    wood=1000,
                    stone=900,
                    iron=800,
                    pop=15,
                    can_build=True,
                ),
            },
            max_queue_size=2,
        )

        # População livre crítica: 1000 - 960 = 40 (limiar = 50)
        resources = Resources(
            wood=2000,
            stone=2000,
            iron=2000,
            storage_max=5000,
            pop=960,
            pop_max=1000,
        )

        bld_cfg = BuildingConfig(auto_farm_priority=True, farm_threshold_pop=50)

        candidate = self.manager.get_next_build_candidate(
            state=state,
            plan=self.default_plan,
            resources=resources,
            building_config=bld_cfg,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.building, BuildingType.FARM)
        self.assertEqual(candidate.target_level, 13)
        self.assertTrue(candidate.is_rush)

    def test_emergency_farm_ignored_when_free_pop_above_threshold(self):
        """Valida que quando a população livre é suficiente (> 50), segue o plano normal."""
        state = MainBuildingState(
            village_id=12345,
            buildings={"main": 10, "farm": 12, "storage": 15},
            queue=[],
            upgrades={
                "main": BuildingUpgrade(
                    building="main",
                    current_level=10,
                    target_level=11,
                    wood=1000,
                    stone=900,
                    iron=800,
                    pop=15,
                    can_build=True,
                ),
            },
            max_queue_size=2,
        )

        # População livre abundante: 1000 - 800 = 200 (> 50)
        resources = Resources(
            wood=5000,
            stone=5000,
            iron=5000,
            storage_max=10000,
            pop=800,
            pop_max=1000,
        )

        bld_cfg = BuildingConfig(auto_farm_priority=True, farm_threshold_pop=50)

        candidate = self.manager.get_next_build_candidate(
            state=state,
            plan=self.default_plan,
            resources=resources,
            building_config=bld_cfg,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.building, BuildingType.MAIN)
        self.assertEqual(candidate.target_level, 11)

    def test_emergency_farm_disabled_when_auto_farm_priority_false(self):
        """Valida que com auto_farm_priority = False, mesmo em pop crítica o plano regular corre."""
        state = MainBuildingState(
            village_id=12345,
            buildings={"main": 10, "farm": 12, "storage": 15},
            queue=[],
            upgrades={
                "main": BuildingUpgrade(
                    building="main",
                    current_level=10,
                    target_level=11,
                    wood=500,
                    stone=500,
                    iron=500,
                    pop=5,
                    can_build=True,
                ),
            },
            max_queue_size=2,
        )

        # População crítica: 1000 - 990 = 10 habitantes livres
        resources = Resources(
            wood=2000,
            stone=2000,
            iron=2000,
            storage_max=5000,
            pop=990,
            pop_max=1000,
        )

        # Priorização de fazenda desativada
        bld_cfg = BuildingConfig(auto_farm_priority=False, farm_threshold_pop=50)

        candidate = self.manager.get_next_build_candidate(
            state=state,
            plan=self.default_plan,
            resources=resources,
            building_config=bld_cfg,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.building, BuildingType.MAIN)

    def test_emergency_farm_skipped_if_already_in_queue(self):
        """Valida que se a Fazenda já estiver em construção na fila, não a duplica desnecessariamente."""
        state = MainBuildingState(
            village_id=12345,
            buildings={"main": 10, "farm": 12, "storage": 15},
            queue=[
                QueueOrder(
                    order_id="order_1",
                    building=BuildingType.FARM,
                    building_name="Fazenda",
                    target_level=13,
                )
            ],
            upgrades={
                "main": BuildingUpgrade(
                    building="main",
                    current_level=10,
                    target_level=11,
                    wood=500,
                    stone=500,
                    iron=500,
                    pop=5,
                    can_build=True,
                ),
            },
            max_queue_size=2,
        )

        # População livre crítica
        resources = Resources(
            wood=2000,
            stone=2000,
            iron=2000,
            storage_max=5000,
            pop=970,
            pop_max=1000,
        )

        bld_cfg = BuildingConfig(auto_farm_priority=True, farm_threshold_pop=50)

        candidate = self.manager.get_next_build_candidate(
            state=state,
            plan=self.default_plan,
            resources=resources,
            building_config=bld_cfg,
        )

        # Como a fazenda já está na fila, o próximo candidato é o plano regular (main)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.building, BuildingType.MAIN)

    def test_emergency_farm_waiting_for_resources_blocks_other_buildings(self):
        """Valida que se a população for crítica e faltarem recursos para a Fazenda, bloqueia outros edifícios para poupar recursos."""
        state = MainBuildingState(
            village_id=12345,
            buildings={"main": 10, "farm": 12, "storage": 15},
            queue=[],
            upgrades={
                "farm": BuildingUpgrade(
                    building="farm",
                    current_level=12,
                    target_level=13,
                    wood=1500,
                    stone=1400,
                    iron=1200,
                    pop=0,
                    can_build=False,
                ),
                "main": BuildingUpgrade(
                    building="main",
                    current_level=10,
                    target_level=11,
                    wood=200,
                    stone=200,
                    iron=200,
                    pop=5,
                    can_build=True,
                ),
            },
            max_queue_size=2,
        )

        # Recursos suficientes para o Edifício Principal (200), mas insuficientes para a Fazenda (1500)
        resources = Resources(
            wood=300,
            stone=300,
            iron=300,
            storage_max=5000,
            pop=980,
            pop_max=1000,
        )

        bld_cfg = BuildingConfig(auto_farm_priority=True, farm_threshold_pop=50)

        candidate = self.manager.get_next_build_candidate(
            state=state,
            plan=self.default_plan,
            resources=resources,
            building_config=bld_cfg,
        )

        # Deve retornar None (bloqueando o avanço de 'main' para não queimar recursos da Fazenda)
        self.assertIsNone(candidate)

    def test_emergency_farm_respects_max_level_limit(self):
        """Valida que se a Fazenda já atingiu o nível máximo (30 ou limite configurado), não tenta evoluir além."""
        state = MainBuildingState(
            village_id=12345,
            buildings={"main": 10, "farm": 30, "storage": 15},
            queue=[],
            upgrades={
                "main": BuildingUpgrade(
                    building="main",
                    current_level=10,
                    target_level=11,
                    wood=500,
                    stone=500,
                    iron=500,
                    pop=5,
                    can_build=True,
                ),
            },
            max_queue_size=2,
        )

        resources = Resources(
            wood=2000,
            stone=2000,
            iron=2000,
            storage_max=5000,
            pop=23980,
            pop_max=24000,
        )

        bld_cfg = BuildingConfig(auto_farm_priority=True, farm_threshold_pop=50, farm_max_level_limit=30)

        candidate = self.manager.get_next_build_candidate(
            state=state,
            plan=self.default_plan,
            resources=resources,
            building_config=bld_cfg,
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.building, BuildingType.MAIN)


if __name__ == "__main__":
    unittest.main()
