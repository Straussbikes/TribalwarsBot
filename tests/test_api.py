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

        # Verifica se 3 tarefas foram enfileiradas no agendador
        self.assertEqual(self.scheduler.queue_size, initial_tasks + 3)

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


if __name__ == "__main__":
    unittest.main()
