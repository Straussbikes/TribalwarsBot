"""
Suíte de Testes Unitários para o Sistema de Defesa & Alarme de Ataques (Ponto 2.8).
Cobre: parsing de contagem de incomings, parsing da tabela de ataques recebidos,
conversão de timers, estimativa de velocidade da unidade mais lenta (Nobre/Aríete),
cálculo de distância euclidiana, Auto-Dodge, cancelamento pós-impacto com TaskPriority.ALERT (0)
e endpoints REST do Sidecar.
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

from engine.actions.defense import (
    DefenseManager,
    DodgeOperation,
    IncomingAttack,
    UNIT_SPEED_SECONDS,
)
from engine.actions.place import UnitsCount
from engine.config.settings import BotConfig, DefenseConfig
from engine.core.account import TribalAccount
from engine.core.models import TaskPriority
from engine.core.scheduler import TaskScheduler
from engine.utils.parsers import (
    parse_incomings_count,
    parse_incomings_overview,
    parse_timer_to_seconds,
)


SAMPLE_INCOMINGS_OVERVIEW_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div id="header_info">
        <span id="incomings_amount">2</span>
    </div>
    <table id="incomings_table" class="vis">
        <tr>
            <th>Comando</th>
            <th>Destino</th>
            <th>Origem</th>
            <th>Jogador</th>
            <th>Distância</th>
            <th>Chegada</th>
            <th>Chegada em</th>
        </tr>
        <tr class="nowrap">
            <td>
                <a href="/game.php?village=1001&amp;screen=info_command&amp;id=8801">
                    Ataque a Aldeia Central (500|500)
                </a>
            </td>
            <td><a href="/game.php?village=1001&amp;screen=info_village&amp;id=1001">Aldeia Central (500|500)</a></td>
            <td><a href="/game.php?village=1001&amp;screen=info_village&amp;id=2002">Aldeia Inimiga Alfa (503|504)</a></td>
            <td><a href="/game.php?village=1001&amp;screen=info_player&amp;id=999">LordInimigo</a></td>
            <td>5.0</td>
            <td>hoje às 21:30:00</td>
            <td><span class="timer">0:15:00</span></td>
        </tr>
        <tr class="nowrap">
            <td>
                <a href="/game.php?village=1001&amp;screen=info_command&amp;id=8802">
                    Ataque de Conquista (500|500)
                </a>
            </td>
            <td><a href="/game.php?village=1001&amp;screen=info_village&amp;id=1001">Aldeia Central (500|500)</a></td>
            <td><a href="/game.php?village=1001&amp;screen=info_village&amp;id=3003">Base Avançada (510|500)</a></td>
            <td><a href="/game.php?village=1001&amp;screen=info_player&amp;id=888">Conquistador</a></td>
            <td>10.0</td>
            <td>amanhã às 02:45:00</td>
            <td><span class="timer">5:50:00</span></td>
        </tr>
    </table>
</body>
</html>
"""

SAMPLE_PLACE_INCOMINGS_HTML = """
<!DOCTYPE html>
<html>
<body>
    <table id="commands_incomings_table" class="vis">
        <tr>
            <th>Comandos a chegar</th>
            <th>Duração</th>
            <th>Chegada</th>
        </tr>
        <tr>
            <td>
                <a href="/game.php?village=1001&amp;screen=info_command&amp;id=7701">
                    Ataque de InimigoX (498|502)
                </a>
            </td>
            <td><span class="timer">0:08:30</span></td>
            <td>hoje às 22:00:15</td>
        </tr>
    </table>
</body>
</html>
"""


class TestDefenseParsers(unittest.TestCase):
    """Testes dos parsers utilitários de ataques a chegar e timers."""

    def test_parse_timer_to_seconds(self):
        self.assertEqual(parse_timer_to_seconds("0:14:22"), 14 * 60 + 22)
        self.assertEqual(parse_timer_to_seconds("1:00:00"), 3600)
        self.assertEqual(parse_timer_to_seconds("14:22"), 14 * 60 + 22)
        self.assertEqual(parse_timer_to_seconds("1:02:10:05"), 86400 + 2 * 3600 + 10 * 60 + 5)
        self.assertEqual(parse_timer_to_seconds(""), 0)
        self.assertEqual(parse_timer_to_seconds(None), 0)

    def test_parse_incomings_count_from_game_data(self):
        game_data = {"player": {"incomings": "4"}}
        count = parse_incomings_count("", game_data=game_data)
        self.assertEqual(count, 4)

        game_data_int = {"player": {"incomings": 7}}
        self.assertEqual(parse_incomings_count("", game_data=game_data_int), 7)

    def test_parse_incomings_count_from_html(self):
        html = '<span id="incomings_amount">3</span>'
        self.assertEqual(parse_incomings_count(html), 3)

        html_link = '<a href="/game.php?screen=overview_villages&mode=incomings">5</a>'
        self.assertEqual(parse_incomings_count(html_link), 5)
        self.assertEqual(parse_incomings_count(""), 0)

    def test_parse_incomings_count_avoids_village_id_false_positive(self):
        # Cenário real: página com link para mode=incomings e depois link com ID da aldeia 6662
        html = '''
        <a href="/game.php?village=6662&screen=overview_villages&mode=incomings">Incomings</a>
        <div>Algum conteúdo</div>
        <a href="/game.php?village=6662">6662</a>
        '''
        self.assertEqual(parse_incomings_count(html), 0)

        # Se game_data trouxer incomings = "0"
        html_with_gd = '''
        <script>var game_data = {"player": {"incomings": "0"}};</script>
        '''
        self.assertEqual(parse_incomings_count(html_with_gd), 0)


    def test_parse_incomings_overview_table(self):
        incomings = parse_incomings_overview(SAMPLE_INCOMINGS_OVERVIEW_HTML)
        self.assertEqual(len(incomings), 2)

        first = incomings[0]
        self.assertEqual(first["command_id"], "8801")
        self.assertEqual(first["type"], "attack")
        self.assertEqual(first["target_coords"], "500|500")
        self.assertEqual(first["origin_coords"], "503|504")
        self.assertEqual(first["attacker_name"], "LordInimigo")
        self.assertEqual(first["time_remaining_seconds"], 15 * 60)
        self.assertEqual(first["arrival_time_str"], "hoje às 21:30:00")

        second = incomings[1]
        self.assertEqual(second["command_id"], "8802")
        self.assertEqual(second["target_coords"], "500|500")
        self.assertEqual(second["origin_coords"], "510|500")
        self.assertEqual(second["attacker_name"], "Conquistador")
        self.assertEqual(second["time_remaining_seconds"], 5 * 3600 + 50 * 60)

    def test_parse_incomings_place_screen(self):
        incomings = parse_incomings_overview(SAMPLE_PLACE_INCOMINGS_HTML)
        self.assertEqual(len(incomings), 1)
        inc = incomings[0]
        self.assertEqual(inc["command_id"], "7701")
        self.assertEqual(inc["origin_coords"], "498|502")
        self.assertEqual(inc["time_remaining_seconds"], 8 * 60 + 30)


class TestDefenseCalculations(unittest.TestCase):
    """Testes de geometria e estimativa tática de velocidade."""

    def test_calculate_distance(self):
        # Triângulo retângulo 3-4-5
        dist = DefenseManager.calculate_distance("500|500", "503|504")
        self.assertAlmostEqual(dist, 5.0, places=2)

        # Mesma aldeia
        self.assertEqual(DefenseManager.calculate_distance("500|500", "500|500"), 0.0)
        # Coordenadas inválidas
        self.assertEqual(DefenseManager.calculate_distance("", "500|500"), 0.0)

    def test_estimate_slowest_unit_by_known_duration(self):
        # Distância = 10.0 campos
        # Duração conhecida = 10 * 35 * 60 = 21000s -> Nobre
        unit, name, is_threat = DefenseManager.estimate_slowest_unit(
            distance=10.0,
            time_remaining_seconds=1000,
            known_duration_seconds=21000,
        )
        self.assertEqual(unit, "snob")
        self.assertTrue(is_threat)

        # Duração conhecida = 10 * 30 * 60 = 18000s -> Aríete / Catapulta
        unit, name, is_threat = DefenseManager.estimate_slowest_unit(
            distance=10.0,
            time_remaining_seconds=1000,
            known_duration_seconds=18000,
        )
        self.assertEqual(unit, "ram")
        self.assertTrue(is_threat)

        # Duração conhecida = 10 * 9 * 60 = 5400s -> Espião
        unit, name, is_threat = DefenseManager.estimate_slowest_unit(
            distance=10.0,
            time_remaining_seconds=1000,
            known_duration_seconds=5400,
        )
        self.assertEqual(unit, "spy")
        self.assertFalse(is_threat)

    def test_estimate_slowest_unit_by_time_remaining(self):
        # Distância = 10.0 campos
        # Se restam 19000s (> 10 * 30m = 18000s), só pode ser Nobre (snob)!
        unit, name, is_threat = DefenseManager.estimate_slowest_unit(
            distance=10.0,
            time_remaining_seconds=19000,
        )
        self.assertEqual(unit, "snob")
        self.assertTrue(is_threat)

        # Se restam 15000s (> 10 * 22m = 13200s), só pode ser Aríete/Catapulta (ram) ou Nobre!
        unit, name, is_threat = DefenseManager.estimate_slowest_unit(
            distance=10.0,
            time_remaining_seconds=15000,
        )
        self.assertIn(unit, ("ram", "snob"))
        self.assertTrue(is_threat)


class TestDefenseManagerExecution(unittest.IsolatedAsyncioTestCase):
    """Testes assíncronos do DefenseManager, Auto-Dodge e cancelamento."""

    async def asyncSetUp(self):
        self.mock_place = MagicMock()
        self.mock_place.send_dodge_command = AsyncMock()
        self.mock_place.cancel_command = AsyncMock(return_value=True)

        self.mock_map = MagicMock()
        self.mock_map.get_cached_barbarians = MagicMock(return_value=[
            {"x": 502, "y": 502, "name": "Bárbara Próxima"},
            {"x": 520, "y": 520, "name": "Bárbara Distante"},
        ])

        self.defense_mgr = DefenseManager(
            place_manager=self.mock_place,
            map_manager=self.mock_map,
        )

        self.account = TribalAccount(
            world="pt117",
            sid="test_sid",
        )
        self.account.current_village_id = 1001
        self.account.village_coords = {1001: "500|500"}

    async def test_check_incomings_dispatches_alert(self):
        self.account.get_screen = AsyncMock(return_value=SAMPLE_INCOMINGS_OVERVIEW_HTML)

        alert_called = asyncio.Event()
        received_incomings = []

        async def _on_alert(incs):
            received_incomings.extend(incs)
            alert_called.set()

        self.defense_mgr.on_incoming_alert(_on_alert)

        incomings = await self.defense_mgr.check_incomings(self.account)
        self.assertEqual(len(incomings), 2)
        self.assertEqual(self.defense_mgr.last_incomings_count, 2)
        self.assertTrue(alert_called.is_set())

    async def test_find_escape_village_uses_barbarian(self):
        coords = await self.defense_mgr.find_escape_village(self.account, 1001)
        # Bárbara mais próxima encontrada na cache é (502, 502)
        self.assertEqual(coords, (502, 502))

        # Se coordenadas preferidas forem fornecidas:
        coords_pref = await self.defense_mgr.find_escape_village(self.account, 1001, preferred_coords="499|501")
        self.assertEqual(coords_pref, (499, 501))

    async def test_execute_dodge_schedules_cancel_with_priority_alert(self):
        self.mock_place.send_dodge_command.return_value = {
            "success": True,
            "command_id": "dodge_cmd_999",
            "units": {"spear": 100, "sword": 100},
        }

        scheduler = TaskScheduler(name="TestScheduler")

        incoming = IncomingAttack(
            command_id="atk_1",
            target_village_id=1001,
            target_name="Minha Aldeia",
            target_coords="500|500",
            origin_village_id=2002,
            origin_name="Inimigo",
            origin_coords="503|504",
            attacker_name="LordInimigo",
            attacker_id=999,
            distance=5.0,
            arrival_time_str="21:30:00",
            arrival_timestamp=1000.0,
            time_remaining_seconds=30.0,
            slowest_unit="ram",
            is_threat=True,
        )

        config = DefenseConfig(
            enabled=True,
            auto_dodge_enabled=True,
            dodge_lead_time_seconds=30,
            dodge_cancel_delay_seconds=5,
        )

        res = await self.defense_mgr.execute_dodge(
            account=self.account,
            incoming=incoming,
            config=config,
            scheduler=scheduler,
        )

        self.assertEqual(res["status"], "success")
        self.assertIn("dodge_cmd_999", self.defense_mgr.active_dodges)

        # Verifica se o cancelamento foi agendado com TaskPriority.ALERT (0)
        self.assertEqual(scheduler.pending_count, 1)
        task = scheduler.queue.get_nowait()
        self.assertEqual(task.priority, int(TaskPriority.ALERT))
        self.assertEqual(task.name, "Cancel_Dodge_dodge_cmd_999")

    async def test_cancel_dodge(self):
        op = DodgeOperation(
            incoming_command_id="atk_1",
            village_id=1001,
            escape_coords="502|502",
            dodge_command_id="dodge_cmd_999",
            status="dispatched",
        )
        self.defense_mgr.active_dodges["dodge_cmd_999"] = op

        ok = await self.defense_mgr.cancel_dodge(self.account, "dodge_cmd_999", village_id=1001)
        self.assertTrue(ok)
        self.assertTrue(op.cancelled)
        self.assertEqual(op.status, "cancelled")
        self.mock_place.cancel_command.assert_called_once_with(self.account, "dodge_cmd_999", village_id=1001)


class TestDefenseContextIntegration(unittest.IsolatedAsyncioTestCase):
    """Testes de integração com o EngineContext e API REST."""

    async def test_context_defense_methods(self):
        from engine.api.context import EngineContext

        cfg = BotConfig(world="pt117")
        ctx = EngineContext(config=cfg)

        status = ctx.get_defense_status()
        self.assertEqual(status["status"], "success")
        self.assertTrue(status["enabled"])
        self.assertFalse(status["auto_dodge_enabled"])

        # Toggle Auto-Dodge
        t_res = ctx.toggle_defense_module(
            auto_dodge_enabled=True,
            dodge_lead_time_seconds=25,
            escape_coords="501|501",
        )
        self.assertEqual(t_res["status"], "success")
        self.assertTrue(ctx.config.defense.auto_dodge_enabled)
        self.assertEqual(ctx.config.defense.dodge_lead_time_seconds, 25)
        self.assertEqual(ctx.config.defense.escape_coords, "501|501")

        # get_status_dict contém o módulo de defesa
        s_dict = ctx.get_status_dict()
        self.assertIn("defense", s_dict["modules"])
        self.assertTrue(s_dict["modules"]["defense"]["auto_dodge_enabled"])


class TestDefenseApiRoutes(unittest.TestCase):
    """Testes dos endpoints REST do Sidecar para Defesa e Alarme."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from engine.api.server import create_app
        from engine.api.context import EngineContext

        self.cfg = BotConfig(world="pt117")
        self.ctx = EngineContext(config=self.cfg)
        self.token = "test_token_def_123"
        self.app = create_app(self.ctx, token=self.token, attach_log_handler=False)
        self.client = TestClient(self.app, headers={"X-Engine-Token": self.token})

    def test_get_defense_incomings_endpoint(self):
        resp = self.client.get("/api/defense/incomings")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("incomings_count", data)
        self.assertIn("active_incomings", data)

    def test_toggle_auto_dodge_endpoint(self):
        resp = self.client.post("/api/defense/dodge/toggle", json={
            "auto_dodge_enabled": True,
            "dodge_lead_time_seconds": 35,
            "escape_coords": "502|503",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(self.ctx.config.defense.auto_dodge_enabled)
        self.assertEqual(self.ctx.config.defense.dodge_lead_time_seconds, 35)
        self.assertEqual(self.ctx.config.defense.escape_coords, "502|503")

    def test_update_defense_config_endpoint(self):
        resp = self.client.post("/api/defense/config", json={
            "alarm_sound_enabled": False,
            "check_interval_seconds": 15.0,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self.ctx.config.defense.alarm_sound_enabled)
        self.assertEqual(self.ctx.config.defense.check_interval_seconds, 15.0)


if __name__ == "__main__":
    unittest.main()
