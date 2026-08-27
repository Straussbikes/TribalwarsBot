"""
Suíte de Testes Unitários para o Módulo do Edifício Principal (screen=main).
Cobre: parsing de níveis, fila de construção, custos de upgrade, cálculo de níveis virtuais,
validação de requisitos tecnológicos, seleção de candidatos e ordens de build/cancel.
"""

import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from engine.actions.main_building import (
    BUILDING_REQUIREMENTS,
    BuildingType,
    BuildingUpgrade,
    MainBuildingManager,
    MainBuildingState,
    QueueOrder,
    RUSH_RESOURCES_TEMPLATE,
)
from engine.core.models import Resources
from engine.utils.parsers import (
    parse_build_queue,
    parse_building_levels,
    parse_building_upgrades,
)


SAMPLE_MAIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <script type="text/javascript">
        var game_data = {
            "player": {"id": 100, "name": "General"},
            "village": {
                "id": 12345,
                "name": "Aldeia 01",
                "buildings": {
                    "main": "5",
                    "barracks": "2",
                    "wood": "8",
                    "stone": "7",
                    "iron": "6",
                    "farm": "5",
                    "storage": "6",
                    "hide": "2",
                    "wall": "1"
                }
            },
            "csrf": "test_csrf_token_999"
        };
    </script>
</head>
<body>
    <!-- Fila de Construção Ativa -->
    <table id="buildqueue" class="vis">
        <tr>
            <th>Construção</th>
            <th>Duração</th>
            <th>Conclusão</th>
            <th>Cancelar</th>
        </tr>
        <tr class="lit buildorder_wood">
            <td>Bosque (Nível 9)</td>
            <td><span class="timer">0:12:45</span></td>
            <td>16:45:00</td>
            <td>
                <a href="/game.php?village=12345&amp;screen=main&amp;action=cancel&amp;id=54321&amp;h=test_csrf_token_999">
                    cancelar
                </a>
            </td>
        </tr>
    </table>

    <!-- Tabela de Edifícios -->
    <table id="buildings" class="vis">
        <tr id="main_buildrow_wood">
            <td>Bosque</td>
            <td><span class="level">8</span></td>
            <td>
                <span class="cost_wood">150</span>
                <span class="cost_stone">180</span>
                <span class="cost_iron">120</span>
                <span class="cost_pop">2</span>
            </td>
            <td>
                <a class="btn_build" href="/game.php?village=12345&amp;screen=main&amp;action=build&amp;id=wood&amp;force=1&amp;h=test_csrf_token_999">
                    Evoluir para nível 9
                </a>
            </td>
        </tr>
        <tr id="main_buildrow_stone">
            <td>Poço de Argila</td>
            <td>(Nível 7)</td>
            <td>
                <span class="cost_wood">200</span>
                <span class="cost_stone">160</span>
                <span class="cost_iron">140</span>
                <span class="cost_pop">2</span>
            </td>
            <td>
                <a class="btn_build" href="/game.php?village=12345&amp;screen=main&amp;action=build&amp;id=stone&amp;force=1&amp;h=test_csrf_token_999">
                    Evoluir para nível 8
                </a>
            </td>
        </tr>
        <tr id="main_buildrow_farm">
            <td>Fazenda</td>
            <td>(Nível 5)</td>
            <td>
                <span class="cost_wood">350</span>
                <span class="cost_stone">400</span>
                <span class="cost_iron">280</span>
                <span class="cost_pop">0</span>
            </td>
            <td>
                <span class="inactive">Recursos insuficientes</span>
            </td>
        </tr>
        <tr id="main_buildrow_storage">
            <td>Armazém</td>
            <td>(Nível 6)</td>
            <td>
                <span class="cost_wood">500</span>
                <span class="cost_stone">450</span>
                <span class="cost_iron">380</span>
                <span class="cost_pop">0</span>
            </td>
            <td>
                <span class="inactive">Armazém muito pequeno</span>
            </td>
        </tr>
        <tr id="main_buildrow_stable">
            <td>Estábulo</td>
            <td>(Nível 0)</td>
            <td>
                <span class="cost_wood">550</span>
                <span class="cost_stone">580</span>
                <span class="cost_iron">540</span>
                <span class="cost_pop">8</span>
            </td>
            <td>
                <span class="inactive">Requisitos não preenchidos</span>
            </td>
        </tr>
    </table>
</body>
</html>
"""


class TestMainBuildingParsing(unittest.TestCase):
    def test_parse_building_levels_from_game_data(self):
        from engine.utils.parsers import extract_game_data
        gd = extract_game_data(SAMPLE_MAIN_HTML)
        levels = parse_building_levels(SAMPLE_MAIN_HTML, gd)
        self.assertEqual(levels["wood"], 8)
        self.assertEqual(levels["stone"], 7)
        self.assertEqual(levels["main"], 5)
        self.assertEqual(levels["barracks"], 2)

    def test_parse_building_levels_fallback_html(self):
        # Sem game_data (None)
        levels = parse_building_levels(SAMPLE_MAIN_HTML, None)
        self.assertEqual(levels["wood"], 8)
        self.assertEqual(levels["stone"], 7)
        self.assertEqual(levels["farm"], 5)
        self.assertEqual(levels["storage"], 6)

    def test_parse_build_queue(self):
        queue = parse_build_queue(SAMPLE_MAIN_HTML)
        self.assertEqual(len(queue), 1)
        q0 = queue[0]
        self.assertEqual(q0["order_id"], "54321")
        self.assertIn("Bosque", q0["building_raw"])
        self.assertEqual(q0["target_level"], 9)
        self.assertEqual(q0["timer_str"], "0:12:45")
        self.assertIn("action=cancel", q0["cancel_url"])
        self.assertIn("id=54321", q0["cancel_url"])

    def test_parse_building_upgrades(self):
        upgrades = parse_building_upgrades(SAMPLE_MAIN_HTML)
        self.assertIn("wood", upgrades)
        self.assertIn("stone", upgrades)
        self.assertIn("farm", upgrades)
        self.assertIn("storage", upgrades)
        self.assertIn("stable", upgrades)

        # Bosque pode ser construído
        wood_up = upgrades["wood"]
        self.assertEqual(wood_up["wood"], 150)
        self.assertEqual(wood_up["stone"], 180)
        self.assertEqual(wood_up["iron"], 120)
        self.assertEqual(wood_up["pop"], 2)
        self.assertTrue(wood_up["can_build"])
        self.assertIsNone(wood_up["error_reason"])
        self.assertIsNotNone(wood_up["build_url"])

        # Fazenda bloqueada por falta de recursos
        farm_up = upgrades["farm"]
        self.assertFalse(farm_up["can_build"])
        self.assertEqual(farm_up["error_reason"], "insufficient_resources")

        # Armazém bloqueado por capacidade
        storage_up = upgrades["storage"]
        self.assertFalse(storage_up["can_build"])
        self.assertEqual(storage_up["error_reason"], "storage_too_small")

        # Estábulo bloqueado por requisitos
        stable_up = upgrades["stable"]
        self.assertFalse(stable_up["can_build"])
        self.assertEqual(stable_up["error_reason"], "requirements_not_met")


class TestMainBuildingLogic(unittest.TestCase):
    def setUp(self):
        self.manager = MainBuildingManager(default_max_queue=2)

    def test_normalize_building_names(self):
        self.assertEqual(self.manager.normalize_building_id("Edifício Principal"), BuildingType.MAIN)
        self.assertEqual(self.manager.normalize_building_id("Bosque"), BuildingType.WOOD)
        self.assertEqual(self.manager.normalize_building_id("wood"), BuildingType.WOOD)
        self.assertEqual(self.manager.normalize_building_id("clay pit"), BuildingType.STONE)
        self.assertEqual(self.manager.normalize_building_id("Quartel"), BuildingType.BARRACKS)
        self.assertEqual(self.manager.normalize_building_id("headquarters"), BuildingType.MAIN)

    def test_virtual_levels_calculation(self):
        state = MainBuildingState(
            village_id=12345,
            buildings={"main": 3, "wood": 5, "stone": 4},
            queue=[
                QueueOrder(order_id="1", building="wood", building_name="Bosque", target_level=6),
                QueueOrder(order_id="2", building="barracks", building_name="Quartel", target_level=1),
            ],
            max_queue_size=2,
        )

        virt = state.virtual_levels
        self.assertEqual(virt["main"], 3)
        self.assertEqual(virt["wood"], 6)        # Atual 5 + Ordem para 6
        self.assertEqual(virt["barracks"], 1)    # Atual 0 + Ordem para 1
        self.assertEqual(virt["stone"], 4)
        self.assertTrue(state.is_queue_full)
        self.assertEqual(state.queue_count, 2)

    def test_requirements_validation(self):
        # Quartel exige Edifício Principal nível 3
        self.assertFalse(self.manager.are_requirements_met(BuildingType.BARRACKS, {"main": 2}))
        self.assertTrue(self.manager.are_requirements_met(BuildingType.BARRACKS, {"main": 3}))

        # Estábulo exige Edifício Principal 10, Quartel 5, Ferreiro 5
        self.assertFalse(self.manager.are_requirements_met(
            BuildingType.STABLE,
            {"main": 10, "barracks": 5, "smith": 4}
        ))
        self.assertTrue(self.manager.are_requirements_met(
            BuildingType.STABLE,
            {"main": 10, "barracks": 5, "smith": 5}
        ))

    def test_get_next_build_candidate_queue_full(self):
        state = MainBuildingState(
            village_id=12345,
            buildings={"wood": 1},
            queue=[
                QueueOrder(order_id="1", building="wood", building_name="Bosque", target_level=2),
                QueueOrder(order_id="2", building="stone", building_name="Poço de Argila", target_level=2),
            ],
            max_queue_size=2,
        )
        plan = [(BuildingType.WOOD, 3), (BuildingType.STONE, 3)]
        resources = Resources(wood=1000, stone=1000, iron=1000, pop=100, pop_max=200)

        candidate = self.manager.get_next_build_candidate(state, plan, resources)
        self.assertIsNone(candidate)

    def test_get_next_build_candidate_insufficient_resources(self):
        state = MainBuildingState(
            village_id=12345,
            buildings={"wood": 1, "stone": 1},
            queue=[],
            upgrades={
                "wood": BuildingUpgrade(building="wood", current_level=1, target_level=2, wood=250, stone=200, iron=150, pop=2),
            },
            max_queue_size=2,
        )
        plan = [(BuildingType.WOOD, 2)]
        # Recursos insuficientes (tem apenas 100 de madeira para um custo de 250)
        resources = Resources(wood=100, stone=500, iron=500, pop=10, pop_max=100)

        candidate = self.manager.get_next_build_candidate(state, plan, resources)
        self.assertIsNone(candidate)

    def test_get_next_build_candidate_success(self):
        state = MainBuildingState(
            village_id=12345,
            buildings={"main": 3, "wood": 1, "stone": 1},
            queue=[],
            upgrades={
                "wood": BuildingUpgrade(building="wood", current_level=1, target_level=2, wood=100, stone=100, iron=50, pop=1, can_build=True),
                "stone": BuildingUpgrade(building="stone", current_level=1, target_level=2, wood=120, stone=100, iron=60, pop=1, can_build=True),
            },
            max_queue_size=2,
        )
        plan = [(BuildingType.WOOD, 2), (BuildingType.STONE, 2)]
        resources = Resources(wood=500, stone=500, iron=500, pop=10, pop_max=100)

        candidate = self.manager.get_next_build_candidate(state, plan, resources)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.building, "wood")
        self.assertEqual(candidate.target_level, 2)


class TestMainBuildingAsyncActions(unittest.IsolatedAsyncioTestCase):
    async def test_build_and_cancel_orders(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.csrf_token = "csrf_token_abc"
        account.current_village_id = 12345

        # Mock do get_screen
        account.get_screen = AsyncMock(return_value=SAMPLE_MAIN_HTML)

        manager = MainBuildingManager()

        # 1. Teste de build_building
        build_res = await manager.build_building(account, "wood", force=True)
        self.assertTrue(build_res)
        account.get_screen.assert_called_with(
            screen="main",
            village_id=None,
            extra_params={
                "action": "build",
                "id": "wood",
                "force": "1",
                "h": "csrf_token_abc",
            },
            apply_jitter=True,
        )

        # 2. Teste de cancel_order
        cancel_res = await manager.cancel_order(account, "54321")
        self.assertTrue(cancel_res)
        account.get_screen.assert_called_with(
            screen="main",
            village_id=None,
            extra_params={
                "action": "cancel",
                "id": "54321",
                "h": "csrf_token_abc",
            },
            apply_jitter=True,
        )

        # 3. Teste de get_state
        state = await manager.get_state(account)
        self.assertEqual(state.village_id, 12345)
        self.assertEqual(state.buildings["wood"], 8)
        self.assertEqual(len(state.queue), 1)
        self.assertEqual(state.queue[0].order_id, "54321")
        self.assertEqual(state.queue[0].building, "wood")
        self.assertEqual(state.queue[0].target_level, 9)


if __name__ == "__main__":
    unittest.main()
