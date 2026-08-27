"""
Suíte de Testes Unitários para o Módulo da Praça de Reunião (screen=place).
Cobre: modelos de tropas (UnitsCount), capacidade de carga, parsing de tropas disponíveis,
comandos em curso, tela de confirmação (try=confirm) e envio de ataques/apoios em 2 etapas.
"""

import asyncio
import sys
import unittest
from unittest.mock import AsyncMock

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from engine.actions.place import (
    CARRY_CAPACITY,
    POP_COST,
    CommandMovement,
    PlaceManager,
    PlaceState,
    UnitType,
    UnitsCount,
)
from engine.utils.parsers import (
    parse_available_units,
    parse_command_confirmation,
    parse_place_commands,
)


SAMPLE_PLACE_HTML = """
<!DOCTYPE html>
<html>
<body>
    <!-- Formulário da Praça de Reunião com Tropas -->
    <form id="command-data-form" action="/game.php?village=12345&amp;screen=place&amp;try=confirm" method="post">
        <table>
            <tr>
                <td><a id="unit_input_spear_all" href="#" class="units-entry-all" data-unit="spear">(120)</a></td>
                <td><input id="unit_input_spear" name="spear" type="text" data-all-count="120" /></td>

                <td><a id="unit_input_sword_all" href="#" class="units-entry-all" data-unit="sword">(80)</a></td>
                <td><input id="unit_input_sword" name="sword" type="text" data-all-count="80" /></td>

                <td><a id="unit_input_axe_all" href="#" class="units-entry-all" data-unit="axe">(250)</a></td>
                <td><input id="unit_input_axe" name="axe" type="text" data-all-count="250" /></td>

                <td><a id="unit_input_spy_all" href="#" class="units-entry-all" data-unit="spy">(20)</a></td>
                <td><input id="unit_input_spy" name="spy" type="text" data-all-count="20" /></td>

                <td><a id="unit_input_light_all" href="#" class="units-entry-all" data-unit="light">(50)</a></td>
                <td><input id="unit_input_light" name="light" type="text" data-all-count="50" /></td>
            </tr>
        </table>
        <input id="inputx" name="x" type="text" />
        <input id="inputy" name="y" type="text" />
        <input name="attack" class="btn" type="submit" value="Ataque" />
        <input name="support" class="btn" type="submit" value="Apoio" />
    </form>

    <!-- Tabela de Comandos Ativos -->
    <table id="commands_outgoings_table" class="vis">
        <tr>
            <th>Comando</th>
            <th>Duração</th>
            <th>Chegada</th>
        </tr>
        <tr>
            <td>
                <a href="/game.php?village=12345&amp;screen=info_command&amp;id=9901">
                    Ataque a Aldeia de bárbaros (452|553)
                </a>
            </td>
            <td><span class="timer">0:14:22</span></td>
            <td>16:45:10</td>
        </tr>
        <tr>
            <td>
                <a href="/game.php?village=12345&amp;screen=info_command&amp;id=9902">
                    Apoio a Muralha Forte (450|550)
                </a>
            </td>
            <td><span class="timer">0:05:10</span></td>
            <td>16:36:00</td>
        </tr>
    </table>
</body>
</html>
"""

SAMPLE_CONFIRM_HTML = """
<!DOCTYPE html>
<html>
<body>
    <h2>Confirmar comando</h2>
    <form action="/game.php?village=12345&amp;screen=place&amp;action=command&amp;h=csrf_token_abc" method="post">
        <input type="hidden" name="attack" value="true" />
        <input type="hidden" name="chck" value="validation_hash_9876" />
        <input type="hidden" name="x" value="455" />
        <input type="hidden" name="y" value="555" />
        <input type="hidden" name="spear" value="50" />
        <input type="hidden" name="axe" value="100" />
        <input type="hidden" name="light" value="25" />
        <input type="hidden" name="action_id" value="cmd_123" />
        <input type="hidden" name="h" value="csrf_token_abc" />

        <table class="vis">
            <tr>
                <td>Destino:</td>
                <td>Aldeia de bárbaros (455|555)</td>
            </tr>
            <tr>
                <td>Duração:</td>
                <td>0:18:25</td>
            </tr>
            <tr>
                <td>Chegada:</td>
                <td>17:35:10</td>
            </tr>
        </table>
        <input type="submit" name="submit" value="Confirmar" class="btn" />
    </form>
</body>
</html>
"""

SAMPLE_CONFIRM_ERROR_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="error_box">
        O jogador encontra-se sob proteção de iniciantes até 28/08 às 10:00.
    </div>
</body>
</html>
"""


class TestUnitsCount(unittest.TestCase):
    def test_units_metrics(self):
        units = UnitsCount(spear=100, sword=50, axe=200, light=40, ram=5)
        self.assertEqual(units.total_units(), 395)

        # Capacidade de saque:
        # spear: 100 * 25 = 2500
        # sword: 50 * 15 = 750
        # axe: 200 * 10 = 2000
        # light: 40 * 80 = 3200
        # ram: 5 * 0 = 0
        # Total esperado: 2500 + 750 + 2000 + 3200 = 8450
        self.assertEqual(units.carrying_capacity(), 8450)

        # População consumida:
        # spear: 100 * 1 = 100
        # sword: 50 * 1 = 50
        # axe: 200 * 1 = 200
        # light: 40 * 4 = 160
        # ram: 5 * 5 = 25
        # Total esperado: 100 + 50 + 200 + 160 + 25 = 535
        self.assertEqual(units.total_population(), 535)

    def test_has_units_and_clamping(self):
        available = UnitsCount(spear=100, axe=50, light=20)
        wanted = UnitsCount(spear=50, axe=50, light=10)
        impossible = UnitsCount(spear=150, axe=50)

        self.assertTrue(available.has_units(wanted))
        self.assertFalse(available.has_units(impossible))

        # Teste de clamp para envio parcial
        clamped = impossible.clamp_to_available(available)
        self.assertEqual(clamped.spear, 100)  # Reduzido para o máximo disponível
        self.assertEqual(clamped.axe, 50)
        self.assertEqual(clamped.light, 0)
        self.assertTrue(available.has_units(clamped))

    def test_dict_serialization(self):
        units = UnitsCount(spear=30, light=15)
        d = units.to_dict()
        self.assertEqual(d["spear"], 30)
        self.assertEqual(d["light"], 15)
        self.assertEqual(d["sword"], 0)

        reconstructed = UnitsCount.from_dict(d)
        self.assertEqual(reconstructed.spear, 30)
        self.assertEqual(reconstructed.light, 15)
        self.assertEqual(reconstructed.total_units(), 45)


class TestPlaceParsers(unittest.TestCase):
    def test_parse_available_units(self):
        units = parse_available_units(SAMPLE_PLACE_HTML)
        self.assertEqual(units["spear"], 120)
        self.assertEqual(units["sword"], 80)
        self.assertEqual(units["axe"], 250)
        self.assertEqual(units["spy"], 20)
        self.assertEqual(units["light"], 50)
        self.assertEqual(units["ram"], 0)
        self.assertEqual(units["snob"], 0)

    def test_parse_place_commands(self):
        commands = parse_place_commands(SAMPLE_PLACE_HTML)
        self.assertEqual(len(commands), 2)

        cmd0 = commands[0]
        self.assertEqual(cmd0["command_id"], "9901")
        self.assertEqual(cmd0["type"], "attack")
        self.assertEqual(cmd0["target_coords"], "452|553")
        self.assertEqual(cmd0["timer_str"], "0:14:22")

        cmd1 = commands[1]
        self.assertEqual(cmd1["command_id"], "9902")
        self.assertEqual(cmd1["type"], "support")
        self.assertEqual(cmd1["target_coords"], "450|550")
        self.assertEqual(cmd1["timer_str"], "0:05:10")

    def test_parse_command_confirmation(self):
        confirm = parse_command_confirmation(SAMPLE_CONFIRM_HTML)
        self.assertTrue(confirm["success"])
        self.assertEqual(confirm["error_message"], "")
        self.assertEqual(confirm["target_coords"], "455|555")
        self.assertEqual(confirm["duration_str"], "0:18:25")

        hidden = confirm["hidden_fields"]
        self.assertEqual(hidden["chck"], "validation_hash_9876")
        self.assertEqual(hidden["spear"], "50")
        self.assertEqual(hidden["axe"], "100")
        self.assertEqual(hidden["light"], "25")
        self.assertEqual(hidden["action_id"], "cmd_123")
        self.assertEqual(hidden["h"], "csrf_token_abc")

    def test_parse_command_confirmation_error(self):
        confirm = parse_command_confirmation(SAMPLE_CONFIRM_ERROR_HTML)
        self.assertFalse(confirm["success"])
        self.assertIn("proteção de iniciantes", confirm["error_message"].lower())


class TestPlaceAsyncActions(unittest.IsolatedAsyncioTestCase):
    async def test_get_state(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345
        account.get_screen = AsyncMock(return_value=SAMPLE_PLACE_HTML)

        manager = PlaceManager()
        state = await manager.get_state(account)

        self.assertEqual(state.village_id, 12345)
        self.assertEqual(state.units.spear, 120)
        self.assertEqual(state.units.axe, 250)
        self.assertEqual(len(state.commands), 2)
        self.assertEqual(state.total_carrying_capacity, 120 * 25 + 80 * 15 + 250 * 10 + 20 * 0 + 50 * 80)

    async def test_send_command_success(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.csrf_token = "csrf_token_abc"
        account.current_village_id = 12345

        # Mock: get_screen retorna a página da praça (com tropas suficientes)
        account.get_screen = AsyncMock(return_value=SAMPLE_PLACE_HTML)

        # Mock: post_action da Etapa 1 retorna SAMPLE_CONFIRM_HTML, e da Etapa 2 retorna sucesso
        account.post_action = AsyncMock(side_effect=[
            SAMPLE_CONFIRM_HTML,
            SAMPLE_PLACE_HTML,
        ])

        manager = PlaceManager()
        troops_to_send = UnitsCount(spear=50, axe=100, light=25)

        success = await manager.send_command(
            account=account,
            target_coords=(455, 555),
            units=troops_to_send,
            is_attack=True,
        )
        self.assertTrue(success)

        # Valida que post_action foi chamado 2 vezes (Etapa 1 e Etapa 2)
        self.assertEqual(account.post_action.call_count, 2)

        # Etapa 1 chamada
        call1 = account.post_action.call_args_list[0]
        self.assertEqual(call1.kwargs["extra_params"], {"try": "confirm"})
        self.assertEqual(call1.kwargs["data"]["attack"], "Ataque")
        self.assertEqual(call1.kwargs["data"]["target_x"], "455")
        self.assertEqual(call1.kwargs["data"]["target_y"], "555")

        # Etapa 2 chamada
        call2 = account.post_action.call_args_list[1]
        self.assertEqual(call2.kwargs["action"], "command")
        self.assertEqual(call2.kwargs["data"]["chck"], "validation_hash_9876")

    async def test_send_command_insufficient_troops(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345
        account.get_screen = AsyncMock(return_value=SAMPLE_PLACE_HTML)
        account.post_action = AsyncMock()

        manager = PlaceManager()
        # Pede 500 lanceiros quando a aldeia só tem 120
        too_many = UnitsCount(spear=500)

        success = await manager.send_command(
            account=account,
            target_coords=(455, 555),
            units=too_many,
            is_attack=True,
            allow_partial=False,
        )
        self.assertFalse(success)
        # Não deve fazer nenhuma chamada de rede para enviar comando
        account.post_action.assert_not_called()


if __name__ == "__main__":
    unittest.main()
