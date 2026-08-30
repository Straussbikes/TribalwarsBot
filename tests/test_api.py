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
            building=BuildingConfig(template="default_plan", max_queue=3, interval_seconds=60.0),
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

        # 5. GET /api/map/data
        with patch.object(self.context.map_manager, "load_cache", return_value=([], 0.0)), \
             patch.object(self.context.map_manager, "fetch_map_data", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_villages
            data_res = self.client.get("/api/map/data?x=571&y=485&radius=10", headers={"X-Engine-Token": self.token})
            self.assertEqual(data_res.status_code, 200)
            self.assertEqual(data_res.json()["status"], "success")
            self.assertEqual(data_res.json()["total_barbarians"], 1)

        # 6. POST /api/map/farm-target
        target_res = self.client.post("/api/map/farm-target", json={"x": 570, "y": 480}, headers={"X-Engine-Token": self.token})
        self.assertEqual(target_res.status_code, 200)
        self.assertEqual(target_res.json()["status"], "success")

        # 7. POST /api/map/quick-attack
        with patch.object(self.context.place_manager, "send_attack", new_callable=AsyncMock) as mock_att:
            mock_att.return_value = True
            att_res = self.client.post("/api/map/quick-attack", json={"target_x": 570, "target_y": 480, "spear": 5}, headers={"X-Engine-Token": self.token})
            self.assertEqual(att_res.status_code, 200)
            self.assertEqual(att_res.json()["status"], "success")

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

    def test_market_toggle_endpoint(self):
        """Testa o endpoint POST /api/market/toggle para ativar/desativar mercado e balanceamento."""
        # Desativa o mercado
        t_res1 = self.client.post(
            "/api/market/toggle",
            json={"enabled": False, "auto_balance_enabled": False},
            headers={"X-Engine-Token": self.token},
        )
        self.assertEqual(t_res1.status_code, 200)
        self.assertEqual(t_res1.json()["status"], "success")

        # Verifica status atualizado
        cfg_res = self.client.get("/api/config", headers={"X-Engine-Token": self.token})
        self.assertEqual(cfg_res.status_code, 200)
        market_cfg = cfg_res.json().get("market", {})
        self.assertFalse(market_cfg.get("enabled"))
        self.assertFalse(market_cfg.get("auto_balance_enabled"))

        # Reativa o mercado
        t_res2 = self.client.post(
            "/api/market/toggle",
            json={"enabled": True, "auto_balance_enabled": True},
            headers={"X-Engine-Token": self.token},
        )
        self.assertEqual(t_res2.status_code, 200)
        self.assertEqual(t_res2.json()["status"], "success")

        cfg_res2 = self.client.get("/api/config", headers={"X-Engine-Token": self.token})
        self.assertTrue(cfg_res2.json().get("market", {}).get("enabled"))

    def test_building_state_and_cancel_endpoints(self):
        """Testa os endpoints GET /api/building/state e POST /api/building/cancel/{order_id}."""
        # Mock do get_building_state no contexto
        from unittest.mock import AsyncMock
        self.context.get_building_state = AsyncMock(return_value={
            "status": "success",
            "village_id": 6810,
            "template": "custom",
            "queue": [],
            "buildings": {"wood": 1, "stone": 1},
            "upcoming": [
                {"step": 1, "building": "wood", "building_name": "Bosque", "target_level": 2, "status": "next"}
            ],
            "next_target": {"building": "wood", "building_name": "Bosque", "target_level": 2},
            "plan_total": 10,
            "completed_count": 2,
        })
        self.context.cancel_building_order = AsyncMock(return_value={
            "status": "success",
            "message": "Ordem cancelada.",
        })

        # 1. GET /api/building/state
        b_res = self.client.get("/api/building/state", headers={"X-Engine-Token": self.token})
        self.assertEqual(b_res.status_code, 200)
        b_data = b_res.json()
        self.assertEqual(b_data["status"], "success")
        self.assertEqual(b_data["village_id"], 6810)
        self.assertIn("upcoming", b_data)
        self.assertEqual(len(b_data["upcoming"]), 1)

        # 2. POST /api/building/cancel/12345
        c_res = self.client.post("/api/building/cancel/12345", headers={"X-Engine-Token": self.token})
        self.assertEqual(c_res.status_code, 200)
        self.assertEqual(c_res.json()["status"], "success")

    def test_building_toggle_endpoint(self):
        """Testa o endpoint POST /api/building/toggle."""
        t_res = self.client.post(
            "/api/building/toggle",
            json={"enabled": False, "interval_seconds": 90, "max_queue": 3},
            headers={"X-Engine-Token": self.token},
        )
        self.assertEqual(t_res.status_code, 200)
        self.assertEqual(t_res.json()["status"], "success")

        cfg_res = self.client.get("/api/config", headers={"X-Engine-Token": self.token})
        bld_cfg = cfg_res.json().get("building", {})
        self.assertFalse(bld_cfg.get("enabled"))
        self.assertEqual(bld_cfg.get("interval_seconds"), 90)
        self.assertEqual(bld_cfg.get("max_queue"), 3)

        # Reativa
        t_res2 = self.client.post(
            "/api/building/toggle",
            json={"enabled": True, "interval_seconds": 60},
            headers={"X-Engine-Token": self.token},
        )
        self.assertEqual(t_res2.status_code, 200)
        cfg_res2 = self.client.get("/api/config", headers={"X-Engine-Token": self.token})
        self.assertTrue(cfg_res2.json().get("building", {}).get("enabled"))
        self.assertEqual(cfg_res2.json().get("building", {}).get("interval_seconds"), 60)

    def test_recruitment_state_and_toggle_endpoints(self):
        """Testa GET /api/recruitment/state e POST /api/recruitment/toggle."""
        from unittest.mock import AsyncMock
        self.context.get_recruitment_state = AsyncMock(return_value={
            "status": "success",
            "village_id": 6810,
            "enabled": True,
            "interval_minutes": 5.0,
            "min_free_pop": 10,
            "targets": {"spear": 50, "sword": 50},
            "batch_sizes": {"spear": 10, "sword": 10},
            "active_orders": [
                {
                    "building": "barracks",
                    "unit": "spear",
                    "unit_name": "Lanceiro",
                    "count": 10,
                    "timer_str": "00:05:30",
                    "finish_time": "15:45:00",
                }
            ],
            "total_in_queue": {"spear": 10},
            "troops_home": {"spear": 20, "sword": 10},
            "available_units": ["spear", "sword", "axe"],
        })

        # 1. GET /api/recruitment/state
        r_res = self.client.get("/api/recruitment/state", headers={"X-Engine-Token": self.token})
        self.assertEqual(r_res.status_code, 200)
        r_data = r_res.json()
        self.assertEqual(r_data["status"], "success")
        self.assertEqual(len(r_data["active_orders"]), 1)
        self.assertEqual(r_data["active_orders"][0]["unit"], "spear")

        # 2. POST /api/recruitment/toggle
        t_res = self.client.post(
            "/api/recruitment/toggle",
            json={"enabled": False, "interval_minutes": 10, "min_free_pop": 25},
            headers={"X-Engine-Token": self.token},
        )
        self.assertEqual(t_res.status_code, 200)
        self.assertEqual(t_res.json()["status"], "success")

        cfg_res = self.client.get("/api/config", headers={"X-Engine-Token": self.token})
        rec_cfg = cfg_res.json().get("recruitment", {})
        self.assertFalse(rec_cfg.get("enabled"))
        self.assertEqual(rec_cfg.get("interval_minutes"), 10)
        self.assertEqual(rec_cfg.get("min_free_pop"), 25)

    def test_arbitrage_api_endpoints(self):
        """Testa GET /api/arbitrage/state, POST /api/arbitrage/evaluate e POST /api/arbitrage/toggle."""
        from unittest.mock import AsyncMock
        self.context.get_arbitrage_state = AsyncMock(return_value={
            "status": "success",
            "enabled": True,
            "decision": {
                "village_id": 6810,
                "action_type": "build",
                "reason": "Construção de Bosque priorizada",
            },
        })
        self.context.trigger_arbitrage_cycle = AsyncMock(return_value={
            "status": "success",
            "message": "Ciclo de Arbitragem executado",
            "decision": {"action_type": "build"},
        })

        # 1. GET /api/arbitrage/state
        res = self.client.get("/api/arbitrage/state", headers={"X-Engine-Token": self.token})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")
        self.assertEqual(res.json()["decision"]["action_type"], "build")

        # 2. POST /api/arbitrage/evaluate
        eval_res = self.client.post("/api/arbitrage/evaluate", headers={"X-Engine-Token": self.token})
        self.assertEqual(eval_res.status_code, 200)
        self.assertEqual(eval_res.json()["status"], "success")

        # 3. POST /api/arbitrage/toggle
        t_res = self.client.post(
            "/api/arbitrage/toggle",
            json={"enabled": True, "interval_seconds": 45, "emergency_queue_seconds": 600},
            headers={"X-Engine-Token": self.token},
        )
        self.assertEqual(t_res.status_code, 200)
        self.assertEqual(t_res.json()["status"], "success")
        self.assertTrue(self.context.config.arbitrage.enabled)
        self.assertEqual(self.context.config.arbitrage.interval_seconds, 45)

    def test_radar_farm_api_endpoints(self):
        """Testa POST /api/farm/radar/plan e POST /api/farm/radar/run."""
        from unittest.mock import AsyncMock
        self.context.get_radar_farm_plan = AsyncMock(return_value={
            "status": "success",
            "village_id": 6810,
            "total_barbarians_found": 5,
            "eligible_targets_count": 3,
            "squads_assigned_count": 3,
            "total_carrying_capacity": 375,
            "squads": [{"target": "(501|501)", "units": {"spear": 5}}],
        })
        self.context.trigger_radar_farm_cycle = AsyncMock(return_value={
            "status": "success",
            "message": "Onda de Radar Farming concluída: 3 ataques despachados.",
            "data": {"sent_attacks": 3},
        })

        # 1. POST /api/farm/radar/plan
        plan_res = self.client.post(
            "/api/farm/radar/plan",
            json={"radius": 12.0, "squad_troops": {"spear": 5, "spy": 1}},
            headers={"X-Engine-Token": self.token},
        )
        self.assertEqual(plan_res.status_code, 200)
        self.assertEqual(plan_res.json()["status"], "success")
        self.assertEqual(plan_res.json()["squads_assigned_count"], 3)

        # 2. POST /api/farm/radar/run
        run_res = self.client.post(
            "/api/farm/radar/run",
            json={"radius": 12.0, "squad_troops": {"spear": 5, "spy": 1}},
            headers={"X-Engine-Token": self.token},
        )
        self.assertEqual(run_res.status_code, 200)
        self.assertEqual(run_res.json()["status"], "success")
        self.assertEqual(run_res.json()["data"]["sent_attacks"], 3)

    def test_get_network_requests_endpoint(self):
        """Testa GET /api/network/requests."""
        # Insere uma requisição simulada no histórico
        self.account._record_request(
            req_id=1,
            method="GET",
            url="https://pt117.tribalwars.com.pt/game.php?screen=main&page=mobile",
            params={"screen": "main", "page": "mobile"},
            status_code=200,
            duration_ms=120.5,
            size_bytes=45000,
        )

        res = self.client.get(
            "/api/network/requests",
            headers={"X-Engine-Token": self.token},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["method"], "GET")
        self.assertEqual(data[0]["status_code"], 200)
        self.assertIn("page=mobile", data[0]["url"])

    def test_account_villages_and_recruitment_models_api(self):
        """Testa GET /api/account/villages e endpoints de modelos de recrutamento."""
        from unittest.mock import AsyncMock

        self.context.sync_and_get_all_villages = AsyncMock(return_value={
            "world": "pt117",
            "count": 1,
            "villages": [{"id": 6810, "name": "Minha Aldeia", "category": "attack"}],
            "balance": {"total_villages": 1},
        })

        # 1. GET /api/account/villages
        v_res = self.client.get("/api/account/villages", headers={"X-Engine-Token": self.token})
        self.assertEqual(v_res.status_code, 200)
        v_data = v_res.json()
        self.assertEqual(v_data["count"], 1)
        self.assertEqual(v_data["villages"][0]["category"], "attack")

        # 2. GET /api/recruitment/models
        m_get = self.client.get("/api/recruitment/models", headers={"X-Engine-Token": self.token})
        self.assertEqual(m_get.status_code, 200)
        self.assertIn("attack", m_get.json()["models"])

        # 3. POST /api/recruitment/models com modelos customizados
        with patch.object(self.context, "update_config_and_save", return_value={"status": "success"}):
            m_post = self.client.post(
                "/api/recruitment/models",
                json={
                    "models": {
                        "attack": {"axe": 6500, "light": 3000},
                        "defense": {"spear": 8000, "sword": 8000},
                        "fast_nuke": {"axe": 7000, "light": 3500},
                    }
                },
                headers={"X-Engine-Token": self.token},
            )
            self.assertEqual(m_post.status_code, 200)
            self.assertEqual(m_post.json()["status"], "success")

            # 4. DELETE /api/recruitment/models/fast_nuke
            m_del = self.client.delete("/api/recruitment/models/fast_nuke", headers={"X-Engine-Token": self.token})
            self.assertEqual(m_del.status_code, 200)
            self.assertEqual(m_del.json()["status"], "success")


if __name__ == "__main__":
    unittest.main()


