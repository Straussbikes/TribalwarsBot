"""
Tribal Wars Mobile Automation Engine - Testes Unitários do Módulo de Mapa
Validação de parsing de village.txt/player.txt, parsing de HTML do mapa,
cálculo de distâncias euclidianas, classificação de aldeias bárbaras/jogadores
e endpoints REST da API Sidecar.
"""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from engine.actions.map import (
    MapData,
    MapManager,
    MapVillage,
    build_map_villages,
    calculate_distance,
    parse_map_screen_data,
    parse_player_txt,
    parse_village_txt,
)
from engine.api.auth import TokenVerifier
from engine.api.context import EngineContext
from engine.api.routes import create_api_router
from engine.config.settings import BotConfig, BuildingConfig, FarmConfig, RecruitmentConfig
from engine.core.account import TribalAccount
from engine.core.models import VillageData


class TestMapCalculationsAndParsers(unittest.TestCase):
    """Testes para o cálculo de distâncias e parsing do mapa."""

    def test_calculate_distance(self):
        # Mesma posição
        self.assertEqual(calculate_distance(500, 500, 500, 500), 0.0)
        # Distância horizontal/vertical direta
        self.assertEqual(calculate_distance(500, 500, 503, 500), 3.0)
        self.assertEqual(calculate_distance(500, 500, 500, 504), 4.0)
        # Triângulo retângulo 3-4-5
        self.assertEqual(calculate_distance(500, 500, 503, 504), 5.0)

    # --- Testes do parser village.txt ---

    def test_parse_village_txt_basic(self):
        content = (
            "6942,Aldeia+de+Teste,502,501,12345,1500,1\n"
            "6943,B%C3%A1rbara+Sul,498,503,0,80,0\n"
            "6944,Outra+Aldeia,510,510,999,3000,2\n"
        )
        villages = parse_village_txt(content)
        self.assertEqual(len(villages), 3)

        # Verifica primeira aldeia
        v = villages[0]
        self.assertEqual(v["id"], 6942)
        self.assertEqual(v["name"], "Aldeia de Teste")
        self.assertEqual(v["x"], 502)
        self.assertEqual(v["y"], 501)
        self.assertEqual(v["player_id"], 12345)
        self.assertEqual(v["points"], 1500)

        # Verifica bárbara (player_id = 0)
        barb = villages[1]
        self.assertEqual(barb["player_id"], 0)
        self.assertIn("Bárbara", barb["name"])

    def test_parse_village_txt_empty(self):
        self.assertEqual(parse_village_txt(""), [])
        self.assertEqual(parse_village_txt("   \n\n  "), [])

    def test_parse_village_txt_malformed_lines(self):
        content = (
            "6942,Aldeia,502,501,12345,1500,1\n"
            "bad_line_without_commas\n"
            "6943,Outra,498,503,0,80,0\n"
        )
        villages = parse_village_txt(content)
        self.assertEqual(len(villages), 2)  # Linha inválida ignorada

    # --- Testes do parser player.txt ---

    def test_parse_player_txt_basic(self):
        content = (
            "12345,Rei+Arthur,100,5,25000,3\n"
            "999,Lord+X,100,2,8000,15\n"
        )
        players = parse_player_txt(content)
        self.assertEqual(len(players), 2)
        self.assertEqual(players[12345], "Rei Arthur")
        self.assertEqual(players[999], "Lord X")

    def test_parse_player_txt_empty(self):
        self.assertEqual(parse_player_txt(""), {})

    # --- Testes do build_map_villages ---

    def test_build_map_villages_filters_by_radius(self):
        raw = [
            {"id": 1, "name": "Perto", "x": 502, "y": 500, "player_id": 0, "points": 80, "rank": 0},
            {"id": 2, "name": "Longe", "x": 550, "y": 550, "player_id": 0, "points": 80, "rank": 0},
        ]
        result = build_map_villages(raw, {}, center_x=500, center_y=500, radius=10.0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 1)

    def test_build_map_villages_identifies_own_and_barbarian(self):
        raw = [
            {"id": 1001, "name": "Capital", "x": 500, "y": 500, "player_id": 42, "points": 500, "rank": 1},
            {"id": 2001, "name": "Bárbara", "x": 501, "y": 500, "player_id": 0, "points": 80, "rank": 0},
            {"id": 3001, "name": "Inimigo", "x": 502, "y": 500, "player_id": 99, "points": 1200, "rank": 5},
        ]
        players = {42: "Eu", 99: "Inimigo Lord"}
        result = build_map_villages(
            raw, players,
            center_x=500, center_y=500,
            own_player_id=42,
            own_village_ids={1001},
            radius=10.0,
        )

        self.assertEqual(len(result), 3)

        own = next(v for v in result if v.id == 1001)
        self.assertTrue(own.is_own)
        self.assertFalse(own.is_barbarian)
        self.assertEqual(own.player_name, "Eu")

        barb = next(v for v in result if v.id == 2001)
        self.assertTrue(barb.is_barbarian)
        self.assertFalse(barb.is_own)

        enemy = next(v for v in result if v.id == 3001)
        self.assertFalse(enemy.is_barbarian)
        self.assertFalse(enemy.is_own)
        self.assertEqual(enemy.player_name, "Inimigo Lord")

    # --- Testes do parser HTML screen=map (Fallback) ---

    def test_parse_map_json_data(self):
        json_content = json.dumps({
            "villages": [
                {"id": 101, "name": "Bárbara (502|500)", "x": 502, "y": 500, "player": 0, "points": 120},
                {"id": 102, "name": "Jogador X", "x": 505, "y": 505, "player": 55, "player_name": "Rei Arthur", "points": 1500},
                {"id": 103, "name": "Muito Longe", "x": 550, "y": 550, "player": 0, "points": 50},
            ]
        })

        villages = parse_map_screen_data(
            content=json_content,
            center_x=500,
            center_y=500,
            own_village_id=999,
            own_player_id=1,
            radius=10.0,
        )

        # Deve conter 3 aldeias no raio: Minha Aldeia (999), Bárbara (101) e Jogador X (102)
        self.assertEqual(len(villages), 3)

        own_v = villages[0]
        self.assertEqual(own_v.id, 999)
        self.assertTrue(own_v.is_own)
        self.assertEqual(own_v.distance, 0.0)

        barb = villages[1]
        self.assertEqual(barb.id, 101)
        self.assertTrue(barb.is_barbarian)
        self.assertEqual(barb.distance, 2.0)

        player_v = villages[2]
        self.assertEqual(player_v.id, 102)
        self.assertFalse(player_v.is_barbarian)
        self.assertEqual(player_v.player_name, "Rei Arthur")

    def test_parse_map_html_script_regex(self):
        html_content = """
        <html>
        <head><title>Mapa</title></head>
        <body>
        <script>
        var sectorPreCache = [
            {"id": 201, "name": "Aldeia Abandonada", "x": 498, "y": 500, "player": 0, "points": 80},
            {"id": 202, "name": "Minha Base", "x": 500, "y": 500, "player": 1, "points": 1000}
        ];
        </script>
        </body>
        </html>
        """

        villages = parse_map_screen_data(
            content=html_content,
            center_x=500,
            center_y=500,
            own_village_id=202,
            own_player_id=1,
            radius=15.0,
        )

        self.assertEqual(len(villages), 2)
        own = next(v for v in villages if v.id == 202)
        self.assertTrue(own.is_own)
        self.assertEqual(own.distance, 0.0)

        abandoned = next(v for v in villages if v.id == 201)
        self.assertTrue(abandoned.is_barbarian)
        self.assertEqual(abandoned.distance, 2.0)


class TestMapManagerAndApi(unittest.TestCase):
    """Testes de integração para MapManager e rotas REST."""

    def setUp(self):
        self.config = BotConfig(
            world="pt117",
            farm=FarmConfig(custom_targets=[(450, 550)]),
        )
        self.mock_scheduler = MagicMock()
        self.mock_scheduler.is_running = True
        self.mock_scheduler.is_paused = False
        self.mock_scheduler.get_jobs_summary.return_value = []

        self.mock_account = MagicMock(spec=TribalAccount)
        self.mock_account.world = "pt117"
        self.mock_account.host = "pt117.tribalwars.com.pt"
        self.mock_account.current_village_id = 1001
        self.mock_account.villages = {
            1001: VillageData(id=1001, name="Capital", x=500, y=500)
        }
        self.mock_account.player = MagicMock()
        self.mock_account.player.id = 1
        self.mock_account.player.name = "TestPlayer"

        # Mock da sessão HTTP para village.txt / player.txt
        self.mock_session = MagicMock()
        self.mock_account.session = self.mock_session

        self.context = EngineContext(
            scheduler=self.mock_scheduler,
            config=self.config,
            account=self.mock_account,
        )

        from engine.api.server import create_app
        self.token = "test_token"
        self.app = create_app(self.context, token=self.token, attach_log_handler=False)
        self.client = TestClient(self.app, headers={"Authorization": f"Bearer {self.token}"})

    def _make_village_txt(self):
        """Cria um conteúdo village.txt de teste."""
        return (
            "301,B%C3%A1rbara+Sul,501,501,0,110,0\n"
            "302,Vizinho+Norte,503,500,77,800,5\n"
            "1001,Capital,500,500,1,500,1\n"
            "9999,Muito+Longe,600,600,0,50,0\n"
        )

    def _make_player_txt(self):
        """Cria um conteúdo player.txt de teste."""
        return (
            "1,TestPlayer,10,1,500,1\n"
            "77,Lord+X,10,3,2400,5\n"
        )

    def test_get_map_data_route_with_village_txt(self):
        """Verifica que a rota /api/map/data carrega dados via village.txt."""
        village_resp = MagicMock()
        village_resp.status_code = 200
        village_resp.text = self._make_village_txt()

        player_resp = MagicMock()
        player_resp.status_code = 200
        player_resp.text = self._make_player_txt()

        # Simular que session.get retorna village.txt ou player.txt conforme o URL
        async def mock_get(url, **kwargs):
            if "village.txt" in url:
                return village_resp
            elif "player.txt" in url:
                return player_resp
            return MagicMock(status_code=404, text="")

        self.mock_session.get = AsyncMock(side_effect=mock_get)

        resp = self.client.get("/api/map/data?x=500&y=500&radius=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertFalse(data["cached"])

        # Deve conter 3 aldeias no raio (301, 302, 1001). 9999 está fora do raio.
        self.assertEqual(len(data["villages"]), 3)
        self.assertEqual(data["total_barbarians"], 1)

        # Verificar que a própria aldeia é identificada
        own_villages = [v for v in data["villages"] if v["is_own"]]
        self.assertEqual(len(own_villages), 1)
        self.assertEqual(own_villages[0]["id"], 1001)

        # 2ª chamada: deve vir do cache
        resp2 = self.client.get("/api/map/data?x=500&y=500&radius=10")
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertTrue(data2["cached"])

    def test_add_farm_target_route(self):
        payload = {"x": 502, "y": 503}
        resp = self.client.post("/api/map/farm-target", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn([502, 503], data["custom_targets"])

    def test_quick_attack_route(self):
        self.context.place_manager.send_attack = AsyncMock(
            return_value=MagicMock(command_id="cmd_999", duration=300)
        )
        payload = {
            "target_x": 502,
            "target_y": 503,
            "spear": 5,
            "spy": 1,
        }
        resp = self.client.post("/api/map/quick-attack", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["command_id"], "cmd_999")


if __name__ == "__main__":
    unittest.main()
