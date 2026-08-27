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

    @patch.object(TribalAccount, "get_screen", new_callable=AsyncMock)
    async def test_switch_village_context(self, mock_get_screen):
        """Valida que switch_village atualiza o village_id ativo na conta e efetua requisição."""
        account = TribalAccount(world="pt117", sid="dummy_sid")
        account.villages[6810] = VillageData(id=6810, name="Aldeia 1", x=571, y=485)
        account.villages[7290] = VillageData(id=7290, name="Aldeia 2", x=572, y=486)
        account.current_village_id = 6810

        switched = await account.switch_village(7290)
        self.assertEqual(account.current_village_id, 7290)
        self.assertEqual(switched.id, 7290)
        self.assertEqual(switched.name, "Aldeia 2")
        mock_get_screen.assert_awaited_once_with("overview", village_id=7290, apply_jitter=True)


if __name__ == "__main__":
    unittest.main()
