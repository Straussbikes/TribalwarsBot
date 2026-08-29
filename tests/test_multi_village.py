"""
Testes Unitários para Extração e Alternância Multi-Aldeia (parsers & account)
"""

import unittest
from unittest.mock import AsyncMock, patch

from engine.core.account import TribalAccount
from engine.core.models import VillageData
from engine.utils.parsers import extract_all_villages


class TestMultiVillage(unittest.IsolatedAsyncioTestCase):
    """Valida a deteção de múltiplas aldeias e a alternância de contexto."""

    def test_extract_all_villages_from_dict_game_data(self):
        """Valida a extração de múltiplas aldeias estruturadas como dicionário em game_data."""
        game_data = {
            "village": {
                "id": 6810,
                "name": "Aldeia Alpha",
                "x": 571,
                "y": 485,
                "points": 450,
            },
            "player": {
                "id": 100,
                "name": "General",
                "villages": {
                    "6810": {"name": "Aldeia Alpha", "coord": "571|485", "points": 450},
                    "7290": {"name": "Aldeia Beta", "coord": "572|486", "points": 120},
                    "8500": {"name": "Aldeia Gamma", "coord": "580|490", "points": 1250},
                },
            },
        }

        villages = extract_all_villages("<html></html>", game_data)
        self.assertEqual(len(villages), 3)
        self.assertIn(6810, villages)
        self.assertIn(7290, villages)
        self.assertIn(8500, villages)

        v_beta = villages[7290]
        self.assertEqual(v_beta.name, "Aldeia Beta")
        self.assertEqual(v_beta.x, 572)
        self.assertEqual(v_beta.y, 486)
        self.assertEqual(v_beta.coordinates, "572|486")
        self.assertEqual(v_beta.points, 120)

    def test_extract_all_villages_from_html_options_fallback(self):
        """Valida o fallback de extração via tags <option> do seletor móvel de aldeias."""
        html = """
        <select name="village" id="village_switch">
            <option value="6810" selected="selected">001 Principal (571|485) K55</option>
            <option value="7290">002 Expansão (572|486) K55</option>
            <option value="9999">003 Fortaleza (600|500) K56</option>
        </select>
        """

        villages = extract_all_villages(html, None)
        self.assertEqual(len(villages), 3)
        self.assertIn(6810, villages)
        self.assertIn(7290, villages)
        self.assertIn(9999, villages)

        v_fortaleza = villages[9999]
        self.assertEqual(v_fortaleza.coordinates, "600|500")
        self.assertEqual(v_fortaleza.x, 600)
        self.assertEqual(v_fortaleza.y, 500)

    def test_parse_overview_villages_production_table(self):
        """Valida a extração de recursos em lote a partir do ecrã overview_villages."""
        from engine.utils.parsers import parse_overview_villages
        html = """
        <table id="production_table">
            <tr data-id="101">
                <td><a href="game.php?village=101&screen=overview">Aldeia Alpha (500|500) K55</a></td>
                <td class="points">1.250</td>
                <td><span class="wood">5.400</span> <span class="stone">4.200</span> <span class="iron">3.100</span></td>
                <td><span class="storage">10.000</span></td>
                <td><a href="game.php?village=101&screen=farm">150/240</a></td>
            </tr>
            <tr data-id="102">
                <td><a href="game.php?village=102&screen=overview">Aldeia Beta (501|500) K55</a></td>
                <td class="points">850</td>
                <td><span class="wood">2.100</span> <span class="stone">1.950</span> <span class="iron">800</span></td>
                <td><span class="storage">6.000</span></td>
                <td><a href="game.php?village=102&screen=farm">80/150</a></td>
            </tr>
        </table>
        """
        vills = parse_overview_villages(html)
        self.assertEqual(len(vills), 2)
        self.assertIn(101, vills)
        self.assertIn(102, vills)

        v1 = vills[101]
        self.assertEqual(v1.id, 101)
        self.assertEqual(v1.coordinates, "500|500")
        self.assertEqual(v1.points, 1250)
        self.assertEqual(v1.resources.wood, 5400)
        self.assertEqual(v1.resources.stone, 4200)
        self.assertEqual(v1.resources.iron, 3100)
        self.assertEqual(v1.resources.storage_max, 10000)
        self.assertEqual(v1.resources.pop, 150)
        self.assertEqual(v1.resources.pop_max, 240)

        v2 = vills[102]
        self.assertEqual(v2.id, 102)
        self.assertEqual(v2.resources.wood, 2100)
        self.assertEqual(v2.resources.storage_max, 6000)

    def test_extract_player_worlds(self):
        """Valida a extração de subdomínios dos mundos do jogador a partir do portal."""
        from engine.utils.parsers import extract_player_worlds
        portal_html = """
        <div class="world_selection">
            <a class="world_button_active" href="https://pt117.tribalwars.com.pt/game.php">Mundo 117</a>
            <a class="world_button_active" href="https://pt118.tribalwars.com.pt/game.php">Mundo 118</a>
            <a class="world_button_active" data-world="pt119" href="https://pt119.tribalwars.com.pt/game.php">Mundo 119</a>
        </div>
        """
        worlds = extract_player_worlds(portal_html, "tribalwars.com.pt")
        self.assertIn("pt117", worlds)
        self.assertIn("pt118", worlds)
        self.assertIn("pt119", worlds)
        self.assertNotIn("www", worlds)

    @patch.object(TribalAccount, "get_screen", new_callable=AsyncMock)
    async def test_fetch_all_villages_overview(self, mock_get_screen):
        """Valida que fetch_all_villages_overview atualiza as aldeias da conta sem mudar current_village_id."""
        mock_get_screen.return_value = """
        <table id="production_table">
            <tr data-id="6810">
                <td><a href="game.php?village=6810&screen=overview">Aldeia 1 (571|485)</a></td>
                <td class="points">500</td>
                <td><span class="wood">1.500</span> <span class="stone">1.200</span> <span class="iron">900</span></td>
                <td><span class="storage">2.000</span></td>
                <td>200/400</td>
            </tr>
            <tr data-id="7290">
                <td><a href="game.php?village=7290&screen=overview">Aldeia 2 (572|486)</a></td>
                <td class="points">300</td>
                <td><span class="wood">800</span> <span class="stone">600</span> <span class="iron">400</span></td>
                <td><span class="storage">1.500</span></td>
                <td>100/250</td>
            </tr>
        </table>
        """
        account = TribalAccount(world="pt117", sid="dummy_sid")
        account.current_village_id = 6810
        account.villages[6810] = VillageData(id=6810, name="Aldeia 1", x=571, y=485)

        vills = await account.fetch_all_villages_overview()
        self.assertEqual(len(vills), 2)
        self.assertEqual(account.current_village_id, 6810)  # Preserva aldeia ativa
        self.assertEqual(account.villages[6810].resources.wood, 1500)
        self.assertEqual(account.villages[7290].resources.wood, 800)


if __name__ == "__main__":
    unittest.main()

