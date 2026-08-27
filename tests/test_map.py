"""
Suíte de Testes Automatizados para a Camada de Mapa Tático & Scanner de Bárbaras (Secção 2.11).
Cobre: parsing de dados do mapa (JSON e HTML), cálculo de distâncias euclidianas,
identificação de bárbaras/bónus, persistência em cache local, ondas de farm por mapa e API Sidecar.
"""

import asyncio
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from engine.actions.farm import FarmManager
from engine.actions.map import MapManager, MapState, MapVillage
from engine.actions.place import UnitsCount
from engine.core.account import TribalAccount
from engine.core.models import Resources, VillageData
from engine.utils.parsers import parse_map_response


SAMPLE_MAP_AJAX_JSON = {
    "villages": {
        "1001": [500, 501, "Aldeia de Bárbaros 1", 120, 0, 0, 0],
        "1002": [503, 504, "Aldeia Bónus de Bárbaros", 250, 0, 0, 1],
        "1003": [501, 500, "Aldeia Jogador Alpha", 1500, 888, 77, 0],
        "1004": [520, 520, "Aldeia Bárbara Longe", 80, 0, 0, 0],
    },
    "players": {
        "888": ["SirLancelot", 5000, 77]
    },
    "allies": {
        "77": ["Cavaleiros da Távola", "CDT", 120000]
    }
}

SAMPLE_MAP_HTML_SCRIPT = """
<!DOCTYPE html>
<html>
<head>
    <script>
        TWMap.sectorData = {
            "villages": {
                "2001": [480, 480, "Bárbaros do Norte", 95, 0, 0, 0],
                "2002": [482, 485, "Reino dos Deuses", 3200, 999, 55, 0]
            },
            "players": {
                "999": ["Zeus", 10000, 55]
            },
            "allies": {
                "55": ["Olimpo", "OLP", 500000]
            }
        };
    </script>
</head>
<body>
    <div id="map_container"></div>
</body>
</html>
"""


class TestMapParsers(unittest.TestCase):
    """Testes unitários de parsing de mapa."""

    def test_parse_map_ajax_json(self):
        villages = parse_map_response(SAMPLE_MAP_AJAX_JSON)
        self.assertEqual(len(villages), 4)

        # Aldeia Bárbara 1
        v1 = next(v for v in villages if v["id"] == 1001)
        self.assertEqual(v1["x"], 500)
        self.assertEqual(v1["y"], 501)
        self.assertEqual(v1["player_id"], 0)
        self.assertEqual(v1["bonus_id"], 0)

        # Aldeia Bónus
        v2 = next(v for v in villages if v["id"] == 1002)
        self.assertEqual(v2["bonus_id"], 1)

        # Aldeia de Jogador
        v3 = next(v for v in villages if v["id"] == 1003)
        self.assertEqual(v3["player_id"], 888)
        self.assertEqual(v3["player_name"], "SirLancelot")
        self.assertEqual(v3["tribe_id"], 77)
        self.assertEqual(v3["tribe_tag"], "CDT")

    def test_parse_map_html_script(self):
        villages = parse_map_response(SAMPLE_MAP_HTML_SCRIPT)
        self.assertEqual(len(villages), 2)
        v = next(v for v in villages if v["id"] == 2001)
        self.assertEqual(v["name"], "Bárbaros do Norte")
        self.assertEqual(v["x"], 480)
        self.assertEqual(v["y"], 480)

    def test_parse_map_sector_prefech(self):
        """Valida parsing do formato de setores reais /map.php e TWMap.sectorPrefech."""
        sector_json = [{
            "x": 560,
            "y": 480,
            "tiles": [[1, 2], [3, 4]],
            "data": {
                "x": 560,
                "y": 480,
                "villages": [
                    {
                        "2": ["5280", 5, "Aldeia de Constantin22", "136", "849084430", 42, None, "0", None, None, "standard", "0", 5],
                        "3": ["5144", 4, 0, "26", "0", 42, None, "0", None, None, "standard", None, 4],
                    }
                ],
                "players": {
                    "849084430": ["Constantin22", "136", "42"]
                },
                "allies": {
                    "42": ["Imperio", "1000", "IMP"]
                }
            }
        }]
        villages = parse_map_response(sector_json)
        self.assertEqual(len(villages), 2)

        # Aldeia do jogador em x=560+0=560, y=480+2=482
        p_v = next(v for v in villages if v["id"] == 5280)
        self.assertEqual(p_v["x"], 560)
        self.assertEqual(p_v["y"], 482)
        self.assertEqual(p_v["name"], "Aldeia de Constantin22")
        self.assertEqual(p_v["player_name"], "Constantin22")
        self.assertEqual(p_v["tribe_tag"], "IMP")

        # Aldeia bárbara em x=560+0=560, y=480+3=483
        b_v = next(v for v in villages if v["id"] == 5144)
        self.assertEqual(b_v["x"], 560)
        self.assertEqual(b_v["y"], 483)
        self.assertEqual(b_v["player_id"], 0)
        self.assertEqual(b_v["name"], "Aldeia de bárbaros")

    def test_parse_map_village_csv(self):
        """Valida parsing de dump público mundial /map/village.txt."""
        csv_text = "1,Aldeia+b%C3%A1rbara,500,500,0,50,0\n2,Aldeia+do+Jogador,505,505,888,250,0"
        villages = parse_map_response(csv_text)
        self.assertEqual(len(villages), 2)
        v1 = villages[0]
        self.assertEqual(v1["id"], 1)
        self.assertEqual(v1["x"], 500)
        self.assertEqual(v1["y"], 500)
        self.assertEqual(v1["name"], "Aldeia bárbara")
        self.assertEqual(v1["player_id"], 0)


class TestMapManagerLogic(unittest.TestCase):
    """Testes de lógica matemática, filtragem e cache local do MapManager."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = MapManager(cache_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_euclidean_distance(self):
        # Triângulo retângulo 3, 4, 5
        dist = self.manager.calculate_distance(500, 500, 503, 504)
        self.assertEqual(dist, 5.0)

        # Mesma coordenada
        self.assertEqual(self.manager.calculate_distance(500, 500, 500, 500), 0.0)

        # Distância horizontal
        self.assertEqual(self.manager.calculate_distance(500, 500, 510, 500), 10.0)

    def test_barbarian_properties(self):
        barb = MapVillage(id=1, x=500, y=501, name="Bárbaros", player_id=0, bonus_id=0)
        self.assertTrue(barb.is_barbarian)
        self.assertFalse(barb.is_bonus)
        self.assertEqual(barb.coordinates, "500|501")

        bonus_barb = MapVillage(id=2, x=502, y=502, name="Aldeia de Bárbaros", player_id=0, bonus_id=2)
        self.assertTrue(bonus_barb.is_barbarian)
        self.assertTrue(bonus_barb.is_bonus)

        player_v = MapVillage(id=3, x=505, y=505, name="Minha Aldeia", player_id=123, player_name="Guerreiro")
        self.assertFalse(player_v.is_barbarian)

    def test_cache_save_and_load(self):
        villages = [
            MapVillage(id=1, x=500, y=501, name="Bárbara 1", points=100, player_id=0),
            MapVillage(id=2, x=502, y=503, name="Bárbara 2", points=200, player_id=0),
        ]
        self.manager.save_cache("pt117", villages)

        loaded, timestamp = self.manager.load_cache("pt117")
        self.assertEqual(len(loaded), 2)
        self.assertGreater(timestamp, 0)
        self.assertEqual(loaded[0].name, "Bárbara 1")
        self.assertEqual(loaded[1].x, 502)

    def test_get_cached_barbarians_ordering(self):
        villages = [
            MapVillage(id=10, x=506, y=508, name="Longe (10 campos)", player_id=0), # dist 10
            MapVillage(id=11, x=503, y=504, name="Perto (5 campos)", player_id=0),  # dist 5
            MapVillage(id=12, x=501, y=500, name="Muito Perto (1 campo)", player_id=0), # dist 1
            MapVillage(id=13, x=500, y=500, name="Própria Aldeia", player_id=0), # dist 0 (deve excluir)
            MapVillage(id=14, x=502, y=502, name="Jogador", player_id=999, player_name="Inimigo"), # não é bárbara
        ]
        self.manager.save_cache("pt117", villages)

        barbs = self.manager.get_cached_barbarians("pt117", center_x=500, center_y=500, radius=8.0)
        # Deve conter apenas dist <= 8.0: id 12 (dist 1) e id 11 (dist 5)
        self.assertEqual(len(barbs), 2)
        self.assertEqual(barbs[0].id, 12)
        self.assertEqual(barbs[0].distance, 1.0)
        self.assertEqual(barbs[1].id, 11)
        self.assertEqual(barbs[1].distance, 5.0)


class TestMapManagerAsync(unittest.IsolatedAsyncioTestCase):
    """Testes assíncronos de varredura ativa e farm baseado em mapa."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = MapManager(cache_dir=self.temp_dir)
        self.mock_account = AsyncMock()
        self.mock_account.world = "pt117"
        self.mock_account.host = "pt117.tribalwars.com.pt"
        self.mock_account.current_village_id = 5555
        self.mock_account.villages = {
            5555: VillageData(
                id=5555,
                name="Aldeia Ativa",
                x=500,
                y=500,
                resources=Resources(wood=1000, stone=1000, iron=1000, storage_max=4000, pop=50, pop_max=100),
            )
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_MAP_AJAX_JSON
        mock_resp.text = json.dumps(SAMPLE_MAP_AJAX_JSON)
        self.mock_account.session = MagicMock()
        self.mock_account.session.get = AsyncMock(return_value=mock_resp)
        self.mock_account.get_screen.return_value = json.dumps(SAMPLE_MAP_AJAX_JSON)
        self.mock_account.get.return_value = SAMPLE_MAP_AJAX_JSON

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_scan_nearby_barbarians_live(self):
        self.mock_account.get.return_value = SAMPLE_MAP_AJAX_JSON

        barbs = await self.manager.scan_nearby_barbarians(
            account=self.mock_account,
            center_x=500,
            center_y=500,
            radius=10.0,
            use_cache=False,
        )

        # 1001 (500|501) dist=1, 1002 (503|504) dist=5 estão no raio <= 10.
        # 1003 é de jogador, 1004 dist > 20.
        self.assertEqual(len(barbs), 2)
        self.assertEqual(barbs[0].id, 1001)
        self.assertEqual(barbs[0].distance, 1.0)
        self.assertEqual(barbs[1].id, 1002)
        self.assertEqual(barbs[1].distance, 5.0)

        # Valida que salvou na cache
        loaded, _ = self.manager.load_cache("pt117")
        self.assertEqual(len(loaded), 4)

    async def test_run_map_farm_wave(self):
        self.mock_account.get.return_value = SAMPLE_MAP_AJAX_JSON
        mock_farm_manager = AsyncMock()
        mock_farm_manager.run_place_farm_wave.return_value = 2

        sent = await self.manager.run_map_farm_wave(
            account=self.mock_account,
            farm_manager=mock_farm_manager,
            troops=UnitsCount(spear=5, spy=1),
            max_attacks=10,
            radius=10.0,
            use_cache=False,
        )

        self.assertEqual(sent, 2)
        mock_farm_manager.run_place_farm_wave.assert_called_once()
        call_kwargs = mock_farm_manager.run_place_farm_wave.call_args.kwargs
        # Confirma que os alvos passados foram as duas bárbaras mais próximas
        self.assertEqual(call_kwargs["targets"], [(500, 501), (503, 504)])


if __name__ == "__main__":
    unittest.main()
