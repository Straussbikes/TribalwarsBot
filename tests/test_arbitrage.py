"""
Suíte de Testes Unitários para o Módulo de Arbitragem Económica & Filosofia 'Fila Sempre Ativa' (Item 2.12).
Cobre: conversão de temporizadores, cálculo de produção horária, projeção de fluxo de caixa,
árvore de decisão de concorrência (Construção vs. Recrutamento), micro-lotes de emergência,
prevenção de transbordamento de armazém e integração Sidecar API.
"""

import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from engine.actions.economic_arbitrage import (
    ArbitrageActionType,
    ArbitrageDecision,
    CashFlowProjection,
    EconomicArbitrageManager,
    parse_timer_to_seconds,
)
from engine.actions.main_building import (
    BuildingUpgrade,
    MainBuildingState,
    QueueOrder,
)
from engine.actions.place import CommandMovement, PlaceState, UnitsCount
from engine.actions.recruitment import RecruitmentState, TrainingOrder
from engine.core.account import TribalAccount
from engine.core.models import Resources
from engine.core.scheduler import TaskScheduler


class TestTimerParsers(unittest.TestCase):
    def test_parse_timer_to_seconds(self):
        self.assertEqual(parse_timer_to_seconds("0:15:30"), 930.0)
        self.assertEqual(parse_timer_to_seconds("1:04:12"), 3852.0)
        self.assertEqual(parse_timer_to_seconds("45:10"), 2710.0)
        self.assertEqual(parse_timer_to_seconds("0:45"), 45.0)
        self.assertEqual(parse_timer_to_seconds("59"), 59.0)
        self.assertEqual(parse_timer_to_seconds(""), 0.0)
        self.assertEqual(parse_timer_to_seconds(None), 0.0)
        self.assertEqual(parse_timer_to_seconds("invalid"), 0.0)


class TestCashFlowProjection(unittest.TestCase):
    def test_calculate_hourly_production(self):
        buildings = {"wood": 10, "stone": 8, "iron": 5}
        prod = EconomicArbitrageManager.calculate_hourly_production(buildings, speed_factor=1.0)
        # Nível 10 madeira = 117, nível 8 argila = 86, nível 5 ferro = 55
        self.assertEqual(prod["wood"], 117.0)
        self.assertEqual(prod["stone"], 86.0)
        self.assertEqual(prod["iron"], 55.0)
        self.assertEqual(prod["total"], 258.0)

    def test_project_resources(self):
        curr = Resources(wood=1000, stone=1000, iron=1000, storage_max=5000)
        hourly_prod = {"wood": 360.0, "stone": 180.0, "iron": 0.0}
        returning_loot = {"wood": 100, "stone": 50, "iron": 20}

        # Projeção a 1 hora (3600s)
        p_1h = EconomicArbitrageManager.project_resources(curr, hourly_prod, returning_loot, 3600.0)
        self.assertEqual(p_1h["wood"], 1460)   # 1000 + 360 + 100
        self.assertEqual(p_1h["stone"], 1230)  # 1000 + 180 + 50
        self.assertEqual(p_1h["iron"], 1020)   # 1000 + 0 + 20

    def test_project_resources_storage_clamping(self):
        curr = Resources(wood=4800, stone=4900, iron=4000, storage_max=5000)
        hourly_prod = {"wood": 600.0, "stone": 600.0, "iron": 600.0}
        returning_loot = {"wood": 500, "stone": 500, "iron": 500}

        p_1h = EconomicArbitrageManager.project_resources(curr, hourly_prod, returning_loot, 3600.0)
        # Não pode ultrapassar storage_max (5000)
        self.assertEqual(p_1h["wood"], 5000)
        self.assertEqual(p_1h["stone"], 5000)


class TestArbitrageDecisions(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.account = TribalAccount(world="pt117", sid="test_sid")
        self.account.current_village_id = 12345
        self.account.resources = Resources(wood=2000, stone=2000, iron=2000, storage_max=10000, pop=50, pop_max=200)

        self.main_manager = MagicMock()
        self.recruitment_manager = MagicMock()
        self.place_manager = MagicMock()

        self.arbitrage_mgr = EconomicArbitrageManager(
            main_building_manager=self.main_manager,
            recruitment_manager=self.recruitment_manager,
            place_manager=self.place_manager,
        )

    async def test_decision_build_priority_when_queue_empty(self):
        # 1. Fila de construção vazia
        main_state = MainBuildingState(
            village_id=12345,
            buildings={"main": 3, "wood": 5, "stone": 5, "iron": 3},
            queue=[],
            upgrades={},
        )
        self.main_manager.get_state = AsyncMock(return_value=main_state)
        self.place_manager.get_state = AsyncMock(return_value=PlaceState(village_id=12345))

        upgrade_candidate = BuildingUpgrade(
            building="wood",
            current_level=5,
            target_level=6,
            wood=200,
            stone=180,
            iron=150,
            pop=2,
            can_build=True,
        )
        self.main_manager.get_next_build_candidate = MagicMock(return_value=upgrade_candidate)

        decision = await self.arbitrage_mgr.evaluate_village_arbitrage(
            account=self.account,
            village_id=12345,
        )

        self.assertEqual(decision.action_type, ArbitrageActionType.BUILD)
        self.assertEqual(decision.target_building.building, "wood")
        self.assertIn("Prioridade evolução", decision.reason)

    async def test_decision_emergency_military_when_queue_expiring(self):
        # Fila de construção tem 2 horas restantes (7200s), mas o Quartel tem apenas 3 minutos (180s < 900s)
        main_state = MainBuildingState(
            village_id=12345,
            buildings={"main": 5, "barracks": 3, "wood": 5, "stone": 5},
            queue=[QueueOrder(order_id="1", building="wood", building_name="Bosque", target_level=6, timer_str="2:00:00")],
        )
        self.main_manager.get_state = AsyncMock(return_value=main_state)

        barracks_state = RecruitmentState(
            building="barracks",
            available_units={"spear": 100, "sword": 100},
            queue=[TrainingOrder(unit="spear", count=2, timer_str="0:03:00")],
        )
        self.recruitment_manager.get_building_state = AsyncMock(return_value=barracks_state)
        self.place_manager.get_state = AsyncMock(return_value=PlaceState(village_id=12345))
        self.main_manager.get_next_build_candidate = MagicMock(return_value=None)

        decision = await self.arbitrage_mgr.evaluate_village_arbitrage(
            account=self.account,
            village_id=12345,
            emergency_queue_seconds=900.0,
            min_military_batch=2,
        )

        self.assertEqual(decision.action_type, ArbitrageActionType.RECRUIT_MICRO)
        self.assertIn("spear", decision.target_recruitment)
        self.assertEqual(decision.target_recruitment["spear"], 2)

    async def test_decision_storage_overflow_spend(self):
        # Armazém quase cheio (9800/10000)
        self.account.resources = Resources(wood=9800, stone=9800, iron=9800, storage_max=10000, pop=50, pop_max=500)
        main_state = MainBuildingState(
            village_id=12345,
            buildings={"main": 5, "barracks": 3, "wood": 10},
            queue=[QueueOrder(order_id="1", building="wood", building_name="Bosque", target_level=11, timer_str="1:00:00")],
            max_queue_size=1,
        )
        self.main_manager.get_state = AsyncMock(return_value=main_state)
        barracks_state = RecruitmentState(
            building="barracks",
            available_units={"spear": 50},
            queue=[TrainingOrder(unit="spear", count=10, timer_str="1:00:00")],
        )
        self.recruitment_manager.get_building_state = AsyncMock(return_value=barracks_state)
        self.place_manager.get_state = AsyncMock(return_value=PlaceState(village_id=12345))
        self.main_manager.get_next_build_candidate = MagicMock(return_value=None)

        decision = await self.arbitrage_mgr.evaluate_village_arbitrage(
            account=self.account,
            village_id=12345,
        )

        self.assertEqual(decision.action_type, ArbitrageActionType.SPEND_SURPLUS)
        self.assertGreater(len(decision.target_recruitment), 0)

    async def test_execute_arbitrage_cycle_build(self):
        decision = ArbitrageDecision(
            village_id=12345,
            action_type=ArbitrageActionType.BUILD,
            reason="Construção priorizada",
            target_building=BuildingUpgrade(building="main", current_level=3, target_level=4, wood=100, stone=100, iron=100, pop=1, can_build=True),
        )
        self.arbitrage_mgr.evaluate_village_arbitrage = AsyncMock(return_value=decision)
        self.main_manager.build_building = AsyncMock(return_value=True)

        res = await self.arbitrage_mgr.execute_arbitrage_cycle(account=self.account, village_id=12345)
        self.assertEqual(res.action_type, ArbitrageActionType.BUILD)
        self.main_manager.build_building.assert_called_once_with(
            account=self.account,
            building="main",
            village_id=12345,
        )

    async def test_execute_arbitrage_cycle_recruit_micro(self):
        decision = ArbitrageDecision(
            village_id=12345,
            action_type=ArbitrageActionType.RECRUIT_MICRO,
            reason="Micro-lote de emergência",
            target_recruitment={"spear": 2},
        )
        self.arbitrage_mgr.evaluate_village_arbitrage = AsyncMock(return_value=decision)
        self.recruitment_manager.train_units = AsyncMock(return_value=True)

        with patch("asyncio.sleep", AsyncMock()):
            res = await self.arbitrage_mgr.execute_arbitrage_cycle(account=self.account, village_id=12345)
            self.assertEqual(res.action_type, ArbitrageActionType.RECRUIT_MICRO)
            self.recruitment_manager.train_units.assert_called_once_with(
                account=self.account,
                building="barracks",
                orders={"spear": 2},
                village_id=12345,
            )


class TestArbitrageScheduler(unittest.TestCase):
    def test_schedule_auto_arbitrage(self):
        scheduler = TaskScheduler()
        account = TribalAccount(world="pt117", sid="test_sid")
        arbitrage_mgr = EconomicArbitrageManager()

        arbitrage_mgr.schedule_auto_arbitrage(
            scheduler=scheduler,
            account=account,
            interval_seconds=45.0,
            village_id=12345,
        )

        self.assertEqual(scheduler.pending_count, 1)


if __name__ == "__main__":
    unittest.main()
