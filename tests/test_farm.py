"""
Suíte de Testes Unitários para o Módulo de Micro-Farming (Item 2.3).
Cobre: parsing do Assistente de Farm (screen=am_farm), filtros de segurança (skip losses / skip wall),
envio de ondas com modelos A e B, fallback via Praça de Reunião e configurações.
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

from engine.actions.farm import FarmAssistantState, FarmManager, FarmTarget
from engine.actions.place import UnitsCount
from engine.config.settings import BotConfig, FarmConfig, load_config
from engine.utils.parsers import (
    parse_am_farm_targets,
    parse_am_farm_templates,
)


SAMPLE_AM_FARM_HTML = """
<!DOCTYPE html>
<html>
<body>
    <form action="/game.php?village=12345&amp;screen=am_farm&amp;mode=farm" method="post">
        <input name="a[spear]" value="6" />
        <input name="a[spy]" value="1" />
        <input name="b[light]" value="3" />
        <input name="b[spy]" value="1" />
    </form>

    <table id="plunder_list" class="vis">
        <!-- Alvo 1: Verde, sem muralha, dist 2.4, ambos disponíveis -->
        <tr id="village_101" class="row_a">
            <td><img src="/graphic/dots/green.png" class="dot green" /></td>
            <td><a href="/game.php?screen=info_village&amp;id=101">Aldeia Bárbara 1 (451|551)</a></td>
            <td>2.4</td>
            <td class="wall">0</td>
            <td>
                <a class="farm_icon farm_icon_a" href="/game.php?village=12345&amp;screen=am_farm&amp;action=farm&amp;target=101&amp;template_id=11&amp;h=csrf123"></a>
            </td>
            <td>
                <a class="farm_icon farm_icon_b" href="/game.php?village=12345&amp;screen=am_farm&amp;action=farm&amp;target=101&amp;template_id=22&amp;h=csrf123"></a>
            </td>
        </tr>

        <!-- Alvo 2: Amarelo (perdas), muralha 1, dist 4.8, A disponível, B disabled -->
        <tr id="village_102" class="row_b">
            <td><img src="/graphic/dots/yellow.png" class="dot yellow" /></td>
            <td><a href="/game.php?screen=info_village&amp;id=102">Aldeia Bárbara 2 (452|552)</a></td>
            <td>4.8</td>
            <td class="wall">1</td>
            <td>
                <a class="farm_icon farm_icon_a" href="/game.php?village=12345&amp;screen=am_farm&amp;action=farm&amp;target=102&amp;template_id=11&amp;h=csrf123"></a>
            </td>
            <td>
                <a class="farm_icon farm_icon_b farm_icon_disabled" href="/game.php?village=12345&amp;screen=am_farm&amp;action=farm&amp;target=102&amp;template_id=22&amp;h=csrf123"></a>
            </td>
        </tr>

        <!-- Alvo 3: Vermelho (derrota), muralha 0, dist 18.0 (muito longe) -->
        <tr id="village_103" class="row_a">
            <td><img src="/graphic/dots/red.png" class="dot red" /></td>
            <td><a href="/game.php?screen=info_village&amp;id=103">Aldeia Bárbara 3 (460|560)</a></td>
            <td>18.0</td>
            <td class="wall">0</td>
            <td>
                <a class="farm_icon farm_icon_a" href="/game.php?village=12345&amp;screen=am_farm&amp;action=farm&amp;target=103&amp;template_id=11&amp;h=csrf123"></a>
            </td>
            <td>
                <a class="farm_icon farm_icon_b" href="/game.php?village=12345&amp;screen=am_farm&amp;action=farm&amp;target=103&amp;template_id=22&amp;h=csrf123"></a>
            </td>
        </tr>

        <!-- Alvo 4: Verde, sem muralha, dist 5.5, apenas A disponível -->
        <tr id="village_104" class="row_b">
            <td><img src="/graphic/dots/green.png" class="dot green" /></td>
            <td><a href="/game.php?screen=info_village&amp;id=104">Aldeia Bárbara 4 (455|553)</a></td>
            <td>5.5</td>
            <td class="wall">0</td>
            <td>
                <a class="farm_icon farm_icon_a" href="/game.php?village=12345&amp;screen=am_farm&amp;action=farm&amp;target=104&amp;template_id=11&amp;h=csrf123"></a>
            </td>
            <td>
                <a class="farm_icon farm_icon_b farm_icon_disabled" href="#"></a>
            </td>
        </tr>
    </table>
</body>
</html>
"""


class TestFarmParsers(unittest.TestCase):
    def test_parse_am_farm_templates(self):
        templates = parse_am_farm_templates(SAMPLE_AM_FARM_HTML)
        self.assertEqual(templates["a"]["spear"], 6)
        self.assertEqual(templates["a"]["spy"], 1)
        self.assertEqual(templates["a"]["light"], 0)

        self.assertEqual(templates["b"]["light"], 3)
        self.assertEqual(templates["b"]["spy"], 1)
        self.assertEqual(templates["b"]["spear"], 0)

    def test_parse_am_farm_targets(self):
        targets = parse_am_farm_targets(SAMPLE_AM_FARM_HTML)
        self.assertEqual(len(targets), 4)

        t1 = targets[0]
        self.assertEqual(t1["target_id"], "101")
        self.assertEqual(t1["target_coords"], "451|551")
        self.assertEqual(t1["distance"], 2.4)
        self.assertEqual(t1["report_color"], "green")
        self.assertEqual(t1["wall_level"], 0)
        self.assertEqual(t1["template_a_id"], "11")
        self.assertEqual(t1["template_b_id"], "22")
        self.assertTrue(t1["template_a_available"])
        self.assertTrue(t1["template_b_available"])

        t2 = targets[1]
        self.assertEqual(t2["target_id"], "102")
        self.assertEqual(t2["report_color"], "yellow")
        self.assertEqual(t2["wall_level"], 1)
        self.assertTrue(t2["template_a_available"])
        self.assertFalse(t2["template_b_available"])

        t3 = targets[2]
        self.assertEqual(t3["report_color"], "red")
        self.assertEqual(t3["distance"], 18.0)


class TestFarmActions(unittest.IsolatedAsyncioTestCase):
    async def test_run_am_farm_wave_filters(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.csrf_token = "csrf123"
        account.current_village_id = 12345
        account.get_screen = AsyncMock(return_value=SAMPLE_AM_FARM_HTML)

        farm_manager = FarmManager()

        # Mock sleep para acelerar o teste
        with patch("asyncio.sleep", AsyncMock()):
            # Onda com Modelo A:
            # - Alvo 101: verde, muralha 0, dist 2.4 -> DEVE ENVIAR
            # - Alvo 102: amarelo (perdas), muralha 1 -> IGNORADO por perdas e muralha
            # - Alvo 103: vermelho, dist 18.0 -> IGNORADO por perdas e distância (> 15)
            # - Alvo 104: verde, muralha 0, dist 5.5 -> DEVE ENVIAR
            sent = await farm_manager.run_am_farm_wave(
                account=account,
                template="A",
                max_distance=15.0,
                skip_losses=True,
                skip_wall=True,
                max_attacks=30,
            )

            # Espera-se 2 ataques enviados (101 e 104)
            self.assertEqual(sent, 2)

    async def test_run_am_farm_wave_template_b(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.csrf_token = "csrf123"
        account.current_village_id = 12345
        account.get_screen = AsyncMock(return_value=SAMPLE_AM_FARM_HTML)

        farm_manager = FarmManager()

        with patch("asyncio.sleep", AsyncMock()):
            # Onda com Modelo B:
            # - Alvo 101: verde, muralha 0, B disponível -> DEVE ENVIAR
            # - Alvo 102: amarelo, muralha 1, B disabled -> IGNORADO
            # - Alvo 103: vermelho, dist 18 -> IGNORADO
            # - Alvo 104: verde, mas B está DISABLED -> IGNORADO
            sent = await farm_manager.run_am_farm_wave(
                account=account,
                template="B",
                max_distance=15.0,
                skip_losses=True,
                skip_wall=True,
                max_attacks=30,
            )

            # Apenas 1 ataque enviado (alvo 101)
            self.assertEqual(sent, 1)

    async def test_run_place_farm_wave(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345

        farm_manager = FarmManager()
        # Mock do place_manager.send_command retornando True
        farm_manager.place_manager.send_command = AsyncMock(return_value=True)

        targets = [(451, 551), (452, 552), (453, 553)]
        troops = UnitsCount(spear=5, spy=1)

        with patch("asyncio.sleep", AsyncMock()):
            sent = await farm_manager.run_place_farm_wave(
                account=account,
                targets=targets,
                troops=troops,
                max_attacks=2,
            )

            self.assertEqual(sent, 2)
            self.assertEqual(farm_manager.place_manager.send_command.call_count, 2)


class TestFarmConfig(unittest.TestCase):
    def test_farm_config_defaults_and_parsing(self):
        f_cfg = FarmConfig(
            enabled=True,
            mode="radar",
            template="B",
            max_distance=12.5,
            skip_losses=True,
            skip_wall=True,
            skip_active_targets=True,
            interval_minutes=8.0,
            custom_targets=[(450, 550), (451, 551)],
            custom_troops={"spear": 10, "spy": 2},
        )
        self.assertTrue(f_cfg.enabled)
        self.assertEqual(f_cfg.mode, "radar")
        self.assertEqual(f_cfg.template, "B")
        self.assertEqual(f_cfg.max_distance, 12.5)
        self.assertTrue(f_cfg.skip_active_targets)
        self.assertEqual(len(f_cfg.custom_targets), 2)
        self.assertEqual(f_cfg.custom_troops["spear"], 10)


class TestRadarFarming(unittest.IsolatedAsyncioTestCase):
    def test_allocate_dynamic_squads(self):
        from engine.actions.farm import allocate_dynamic_squads

        available = UnitsCount(spear=23, spy=4, axe=10)
        squad_template = UnitsCount(spear=5, spy=1)
        targets = [(501, 501), (502, 502), (503, 503), (504, 504), (505, 505)]

        # Temos 23 lanças e 4 espiões -> com (5 lanças + 1 espião), conseguimos min(23//5=4, 4//1=4) = 4 esquadrões
        allocations = allocate_dynamic_squads(
            available_units=available,
            squad_template=squad_template,
            targets=targets,
        )

        self.assertEqual(len(allocations), 4)
        for i, (target, squad) in enumerate(allocations):
            self.assertEqual(target, targets[i])
            self.assertEqual(squad.spear, 5)
            self.assertEqual(squad.spy, 1)

    def test_allocate_dynamic_squads_with_max_limit(self):
        from engine.actions.farm import allocate_dynamic_squads

        available = UnitsCount(spear=100, spy=20)
        squad_template = UnitsCount(spear=10, spy=2)
        targets = [(501, 501), (502, 502), (503, 503), (504, 504)]

        # Limitar a 2 esquadrões
        allocations = allocate_dynamic_squads(
            available_units=available,
            squad_template=squad_template,
            targets=targets,
            max_squads=2,
        )
        self.assertEqual(len(allocations), 2)

    def test_allocate_dynamic_squads_insufficient_troops(self):
        from engine.actions.farm import allocate_dynamic_squads

        available = UnitsCount(spear=3, spy=0)
        squad_template = UnitsCount(spear=5, spy=1)
        targets = [(501, 501)]

        allocations = allocate_dynamic_squads(
            available_units=available,
            squad_template=squad_template,
            targets=targets,
        )
        self.assertEqual(len(allocations), 0)

    async def test_get_radar_farm_plan(self):
        from engine.actions.map import MapVillage
        from engine.actions.place import CommandMovement, PlaceState
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345
        account.villages = {12345: MagicMock(x=500, y=500)}

        farm_manager = FarmManager()
        farm_manager.map_manager = MagicMock()

        # 3 aldeias bárbaras vizinhas
        barbs = [
            MapVillage(id=1, x=501, y=501, name="Bárbara 1", distance=1.4, is_barbarian=True),
            MapVillage(id=2, x=502, y=502, name="Bárbara 2", distance=2.8, is_barbarian=True),
            MapVillage(id=3, x=503, y=503, name="Bárbara 3", distance=4.2, is_barbarian=True),
        ]
        farm_manager.map_manager.scan_nearby_barbarians = AsyncMock(return_value=barbs)

        # Aldeia tem 15 lanças e 3 espiões; já existe um ataque a caminho de (501|501)
        place_state = PlaceState(
            village_id=12345,
            units=UnitsCount(spear=15, spy=3),
            commands=[CommandMovement(command_id="1", movement_type="attack", target_name="Bárbara 1", target_coords="(501|501)")],
        )
        farm_manager.place_manager.get_state = AsyncMock(return_value=place_state)

        plan = await farm_manager.get_radar_farm_plan(
            account=account,
            radius=15.0,
            squad_template=UnitsCount(spear=5, spy=1),
            skip_active_targets=True,
            village_id=12345,
        )

        self.assertEqual(plan.total_barbarians_found, 3)
        # Como (501|501) já está a ser atacada, os alvos elegíveis são (502|502) e (503|503)
        self.assertEqual(len(plan.eligible_targets), 2)
        # Com 15 lanças, conseguimos abastecer 2 esquadrões (para os 2 alvos elegíveis)
        self.assertEqual(len(plan.squads_assigned), 2)
        self.assertEqual(plan.squads_assigned[0][0], (502, 502))
        self.assertEqual(plan.squads_assigned[1][0], (503, 503))

    async def test_run_radar_farm_cycle(self):
        from engine.actions.farm import RadarFarmPlan
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345

        farm_manager = FarmManager()
        plan = RadarFarmPlan(
            village_id=12345,
            total_barbarians_found=2,
            eligible_targets=[(502, 502), (503, 503)],
            squads_assigned=[
                ((502, 502), UnitsCount(spear=5, spy=1)),
                ((503, 503), UnitsCount(spear=5, spy=1)),
            ],
            total_carrying_capacity=250,
        )
        farm_manager.get_radar_farm_plan = AsyncMock(return_value=plan)
        farm_manager.place_manager.send_command = AsyncMock(return_value=True)

        with patch("asyncio.sleep", AsyncMock()):
            result = await farm_manager.run_radar_farm_cycle(
                account=account,
                radius=15.0,
                village_id=12345,
            )

            self.assertEqual(result["sent_attacks"], 2)
            self.assertEqual(result["total_targets"], 2)
            self.assertEqual(farm_manager.place_manager.send_command.call_count, 2)


if __name__ == "__main__":
    unittest.main()

