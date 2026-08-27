"""
Suíte de Testes Automatizados para a Camada Sidecar IPC & API (Fase 3).
Cobre: Autenticação por token efêmero, endpoints REST (status, config, scheduler, ações),
e conexão / streaming em tempo real via WebSocket.
"""

import json
import logging
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from engine.api.auth import TokenVerifier, generate_auth_token
from engine.api.context import EngineContext
from engine.api.server import create_app
from engine.config.settings import BotConfig, BuildingConfig, FarmConfig, RecruitmentConfig
from engine.core.account import TribalAccount
from engine.core.models import Resources, VillageData
from engine.core.scheduler import TaskScheduler


class TestApiSidecar(unittest.TestCase):
    def setUp(self):
        # 1. Configurações e instâncias mock
        self.config = BotConfig(
            world="pt117",
            sid="test_token_sid",
            building=BuildingConfig(template="rush_resources", max_queue=3, interval_seconds=60.0),
            farm=FarmConfig(enabled=False, mode="am_farm"),
            recruitment=RecruitmentConfig(enabled=False),
        )

        self.scheduler = TaskScheduler(name="TestApiScheduler")
        self.account = TribalAccount(world="pt117", sid="test_sid")
        self.account.current_village_id = 6810
        self.account.villages[6810] = VillageData(
            id=6810,
            name="Aldeia Teste",
            x=571,
            y=485,
            points=150,
            resources=Resources(wood=300, stone=300, iron=300, storage_max=1000, pop=40, pop_max=240),
        )

        # 2. Contexto do Motor
        self.context = EngineContext(
            scheduler=self.scheduler,
            config=self.config,
            account=self.account,
            config_path=Path("test_config_scratch.json"),
        )

        # 3. Token e aplicação FastAPI
        self.token = "secure_test_sidecar_token_12345"
        self.app = create_app(self.context, token=self.token, attach_log_handler=False)
        self.client = TestClient(self.app)

    def tearDown(self):
        # Limpa ficheiro temporário se criado
        p = Path("test_config_scratch.json")
        if p.exists():
            p.unlink()

    # --- Testes de Autenticação ---

    def test_auth_rejection_without_token(self):
        """Requisições sem token devem ser rejeitadas com HTTP 401."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 401)

        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 401)

    def test_auth_rejection_with_invalid_token(self):
        """Tokens incorretos devem ser rejeitados com HTTP 401."""
        response = self.client.get("/api/health", headers={"X-Engine-Token": "wrong_token"})
        self.assertEqual(response.status_code, 401)

    def test_auth_success_via_header(self):
        """Acesso concedido com cabeçalho X-Engine-Token correto."""
        response = self.client.get("/api/health", headers={"X-Engine-Token": self.token})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")

    def test_auth_success_via_bearer(self):
        """Acesso concedido via Authorization: Bearer <token>."""
        response = self.client.get("/api/health", headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(response.status_code, 200)

    def test_auth_success_via_query_param(self):
        """Acesso concedido via query string ?token=<token>."""
        response = self.client.get(f"/api/health?token={self.token}")
        self.assertEqual(response.status_code, 200)

    # --- Testes de Endpoints REST ---

    def test_get_status_returns_complete_overview(self):
        """GET /api/status retorna estado do agendador, recursos, jogador e aldeia."""
        response = self.client.get("/api/status", headers={"X-Engine-Token": self.token})
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("engine", data)
        self.assertIn("account", data)
        self.assertIn("modules", data)

        village = data["account"]["village"]
        self.assertEqual(village["id"], 6810)
        self.assertEqual(village["coordinates"], "571|485")
        self.assertEqual(village["resources"]["wood"], 300)
        self.assertEqual(village["resources"]["free_pop"], 200)

    def test_get_and_update_config(self):
        """GET e POST em /api/config atualizam dinamicamente opções."""
        # 1. Leitura inicial
        get_res = self.client.get("/api/config", headers={"X-Engine-Token": self.token})
        self.assertEqual(get_res.status_code, 200)
        cfg_data = get_res.json()
        self.assertFalse(cfg_data["farm"]["enabled"])

        # 2. Atualização via POST
        post_payload = {
            "farm": {"enabled": True, "mode": "am_farm", "template": "B"},
            "building": {"max_queue": 4},
        }
        post_res = self.client.post(
            "/api/config",
            json=post_payload,
            headers={"X-Engine-Token": self.token},
        )
        self.assertEqual(post_res.status_code, 200)
        self.assertEqual(post_res.json()["status"], "success")

        # 3. Valida se a configuração ativa no EngineContext foi atualizada
        self.assertTrue(self.context.config.farm.enabled)
        self.assertEqual(self.context.config.farm.template, "B")
        self.assertEqual(self.context.config.building.max_queue, 4)

    def test_scheduler_pause_and_resume(self):
        """POST /api/scheduler/pause e /resume controlam o estado do agendador."""
        # Pausa
        p_res = self.client.post("/api/scheduler/pause", headers={"X-Engine-Token": self.token})
        self.assertEqual(p_res.status_code, 200)
        self.assertEqual(p_res.json()["status"], "paused")
        self.assertTrue(self.scheduler.is_paused)

        # Retoma
        r_res = self.client.post("/api/scheduler/resume", headers={"X-Engine-Token": self.token})
        self.assertEqual(r_res.status_code, 200)
        self.assertEqual(r_res.json()["status"], "resumed")
        self.assertFalse(self.scheduler.is_paused)

    def test_trigger_manual_actions(self):
        """Endpoints /api/actions/*/trigger agendam tarefas imediatas na fila."""
        initial_tasks = self.scheduler.queue_size

        # Dispara construção
        b_res = self.client.post("/api/actions/build/trigger", headers={"X-Engine-Token": self.token})
        self.assertEqual(b_res.status_code, 200)
        self.assertEqual(b_res.json()["status"], "scheduled")

        # Dispara farm
        f_res = self.client.post("/api/actions/farm/trigger", headers={"X-Engine-Token": self.token})
        self.assertEqual(f_res.status_code, 200)
        self.assertEqual(f_res.json()["status"], "scheduled")

        # Dispara recrutamento
        r_res = self.client.post("/api/actions/recruit/trigger", headers={"X-Engine-Token": self.token})
        self.assertEqual(r_res.status_code, 200)
        self.assertEqual(r_res.json()["status"], "scheduled")

        # Dispara missões
        q_res = self.client.post("/api/actions/quest/trigger", headers={"X-Engine-Token": self.token})
        self.assertEqual(q_res.status_code, 200)
        self.assertEqual(q_res.json()["status"], "scheduled")

        # Verifica se 4 tarefas foram enfileiradas no agendador
        self.assertEqual(self.scheduler.queue_size, initial_tasks + 4)

    def test_quest_api_endpoints(self):
        """Endpoints /api/quest/* retornam dados de missões e executam ações manuais."""
        # 1. GET /api/quest/status com mocks
        with patch.object(self.context.quest_manager, "get_quest_state", new_callable=AsyncMock) as mock_q, \
             patch.object(self.context.quest_manager, "get_daily_bonus_state", new_callable=AsyncMock) as mock_d, \
             patch.object(self.context.quest_manager, "get_inventory_state", new_callable=AsyncMock) as mock_inv:

            from engine.actions.quest import QuestState, DailyBonusState, InventoryState, QuestItem, QuestReward, InventoryItem
            mock_q.return_value = QuestState(
                village_id=6810,
                quests=[QuestItem(id="99", title="Missão Teste", finishable=True, rewards=QuestReward(wood=100))],
                finishable_count=1,
            )
            mock_d.return_value = DailyBonusState(can_open=True, is_opened_today=False)
            mock_inv.return_value = InventoryState(items=[InventoryItem(id="boost_wood", name="Boost Madeira", count=1, can_use=True)])

            status_res = self.client.get("/api/quest/status", headers={"X-Engine-Token": self.token})
            self.assertEqual(status_res.status_code, 200)
            data = status_res.json()
            self.assertEqual(len(data["quests"]), 1)
            self.assertEqual(data["finishable_count"], 1)
            self.assertTrue(data["daily_bonus"]["can_open"])
            self.assertEqual(len(data["inventory"]), 1)

        # 2. POST /api/quest/daily-bonus/open
        with patch.object(self.context.quest_manager, "open_daily_bonus", new_callable=AsyncMock) as mock_open:
            mock_open.return_value = True
            open_res = self.client.post("/api/quest/daily-bonus/open", headers={"X-Engine-Token": self.token})
            self.assertEqual(open_res.status_code, 200)
            self.assertEqual(open_res.json()["status"], "success")

        # 3. POST /api/quest/inventory/use/{item_id} (Manual)
        with patch.object(self.context.quest_manager, "use_inventory_item", new_callable=AsyncMock) as mock_use:
            mock_use.return_value = True
            use_res = self.client.post("/api/quest/inventory/use/boost_wood", headers={"X-Engine-Token": self.token})
            self.assertEqual(use_res.status_code, 200)
            self.assertEqual(use_res.json()["status"], "success")

    def test_map_api_endpoints(self):
        """Endpoints /api/map/* retornam a grelha de mapa e disparam varreduras/farm."""
        from engine.actions.map import MapVillage

        mock_villages = [
            MapVillage(id=101, x=571, y=486, name="Bárbara 1", points=100, player_id=0, distance=1.0),
            MapVillage(id=102, x=575, y=485, name="Jogador 1", points=2000, player_id=55, distance=4.0),
        ]

        # 1. GET /api/map/grid
        with patch.object(self.context.map_manager, "load_cache", return_value=([], 0.0)), \
             patch.object(self.context.map_manager, "fetch_map_data", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_villages
            grid_res = self.client.get("/api/map/grid?x=571&y=485&radius=10", headers={"X-Engine-Token": self.token})
            self.assertEqual(grid_res.status_code, 200)
            data = grid_res.json()
            self.assertEqual(data["count"], 2)
            self.assertEqual(data["villages"][0]["id"], 101)

        # 2. GET /api/map/barbarians
        with patch.object(self.context.map_manager, "scan_nearby_barbarians", new_callable=AsyncMock) as mock_scan:
            mock_scan.return_value = [mock_villages[0]]
            barb_res = self.client.get("/api/map/barbarians?radius=10", headers={"X-Engine-Token": self.token})
            self.assertEqual(barb_res.status_code, 200)
            b_data = barb_res.json()
            self.assertEqual(b_data["count"], 1)
            self.assertEqual(b_data["barbarians"][0]["name"], "Bárbara 1")

        # 3. POST /api/map/scan
        with patch.object(self.context.map_manager, "scan_nearby_barbarians", new_callable=AsyncMock) as mock_scan:
            mock_scan.return_value = [mock_villages[0]]
            scan_res = self.client.post("/api/map/scan?radius=15", headers={"X-Engine-Token": self.token})
            self.assertEqual(scan_res.status_code, 200)
            self.assertEqual(scan_res.json()["status"], "success")

        # 4. POST /api/map/farm
        with patch.object(self.context, "trigger_map_farm_wave", new_callable=AsyncMock) as mock_farm:
            mock_farm.return_value = {"status": "scheduled", "task_id": "test_map_farm_task"}
            farm_res = self.client.post("/api/map/farm", headers={"X-Engine-Token": self.token})
            self.assertEqual(farm_res.status_code, 200)
            self.assertEqual(farm_res.json()["status"], "scheduled")

    def test_bot_protect_resume_clears_alert(self):
        """POST /api/bot-protect/resume retoma o agendador e limpa alertas de captcha."""
        self.context.last_captcha_alert = {"world": "pt117", "url": "http://..."}
        self.scheduler.pause()

        res = self.client.post("/api/bot-protect/resume", headers={"X-Engine-Token": self.token})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(self.scheduler.is_paused)
        self.assertIsNone(self.context.last_captcha_alert)

    # --- Testes de WebSocket ---

    def test_websocket_auth_rejection(self):
        """Conexão WebSocket sem token válido deve ser rejeitada."""
        with self.assertRaises(Exception):
            with self.client.websocket_connect("/ws?token=invalid"):
                pass

    def test_websocket_connection_and_ping(self):
        """Conexão WebSocket autenticada recebe estado inicial e responde a ping."""
        with self.client.websocket_connect(f"/ws?token={self.token}") as ws:
            # Primeira mensagem enviada pelo servidor é o estado inicial
            initial_msg = ws.receive_json()
            self.assertEqual(initial_msg["type"], "INITIAL_STATE")
            self.assertIn("data", initial_msg)
            self.assertEqual(initial_msg["data"]["account"]["village"]["id"], 6810)

            # Envia ping
            ws.send_text(json.dumps({"action": "ping"}))
            pong_msg = ws.receive_json()
            self.assertEqual(pong_msg["type"], "PONG")

    def test_auth_info_endpoint(self):
        """Endpoint /api/auth-info deve retornar o token de sessão para o cliente local."""
        resp = self.client.get("/api/auth-info")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["token"], self.token)

    def test_frontend_static_serving(self):
        """A raiz do servidor deve carregar o HTML da interface frontend."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("TribalWars Bot", resp.text)
        self.assertIn("badge-world", resp.text)

        # Testa também um asset CSS
        css_resp = self.client.get("/css/style.css")
        self.assertEqual(css_resp.status_code, 200)
        self.assertIn("neon-cyan", css_resp.text)

    def test_refresh_village_and_claim_all_quests(self):
        """Endpoints /api/account/refresh e /api/quest/claim-all atualizam recursos e tropas."""
        # 1. POST /api/account/refresh
        with patch.object(self.context, "refresh_village_data", new_callable=AsyncMock) as mock_ref:
            mock_ref.return_value = {
                "status": "success",
                "data": {"resources": {"wood": 1200, "stone": 1100, "iron": 900}, "troops": {"spear": 50, "sword": 40}},
            }
            ref_res = self.client.post("/api/account/refresh", headers={"X-Engine-Token": self.token})
            self.assertEqual(ref_res.status_code, 200)
            self.assertEqual(ref_res.json()["status"], "success")
            self.assertEqual(ref_res.json()["data"]["troops"]["spear"], 50)

        # 2. POST /api/quest/claim-all
        with patch.object(self.context, "claim_all_quests_safe", new_callable=AsyncMock) as mock_claim:
            mock_claim.return_value = {
                "status": "success",
                "claimed_count": 2,
                "skipped_count": 0,
            }
            claim_res = self.client.post("/api/quest/claim-all", headers={"X-Engine-Token": self.token})
            self.assertEqual(claim_res.status_code, 200)
            self.assertEqual(claim_res.json()["claimed_count"], 2)

    def test_worlds_endpoints(self):
        """Endpoints /api/worlds, /api/worlds/register e /api/worlds/switch."""
        # 1. GET /api/worlds
        res = self.client.get("/api/worlds", headers={"X-Engine-Token": self.token})
        self.assertEqual(res.status_code, 200)
        self.assertIn("worlds", res.json())

        # 2. POST /api/worlds/register
        reg_res = self.client.post(
            "/api/worlds/register",
            json={"world": "pt118", "sid": "new_sid_118", "domain": "tribalwars.com.pt"},
            headers={"X-Engine-Token": self.token},
        )
        self.assertEqual(reg_res.status_code, 200)
        self.assertEqual(reg_res.json()["status"], "success")

        # 3. POST /api/worlds/switch
        sw_res = self.client.post(
            "/api/worlds/switch",
            json={"world": "pt118"},
            headers={"X-Engine-Token": self.token},
        )
        self.assertEqual(sw_res.status_code, 200)
        self.assertEqual(sw_res.json()["status"], "success")

    def test_villages_and_category_endpoints(self):
        """Endpoints /api/account/villages, /api/account/village/category e balance."""
        # 1. GET /api/account/villages
        v_res = self.client.get("/api/account/villages", headers={"X-Engine-Token": self.token})
        self.assertEqual(v_res.status_code, 200)
        data = v_res.json()
        self.assertIn("villages", data)

        # 2. POST /api/account/village/category
        cat_res = self.client.post(
            "/api/account/village/category",
            json={"village_id": 6810, "category": "attack"},
            headers={"X-Engine-Token": self.token},
        )
        self.assertEqual(cat_res.status_code, 200)
        self.assertEqual(cat_res.json()["status"], "success")

        # 3. GET /api/account/villages/balance
        bal_res = self.client.get("/api/account/villages/balance", headers={"X-Engine-Token": self.token})
        self.assertEqual(bal_res.status_code, 200)


if __name__ == "__main__":
    unittest.main()

