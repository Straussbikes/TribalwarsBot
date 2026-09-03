"""
Testes de Integração da API Sidecar para Autenticação Cloud SQL,
Gestão de Contas de Jogo, Orquestração Multi-Mundo e Atribuição de Modelos em Aldeias.
"""

import asyncio
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from engine.api.context import EngineContext
from engine.api.routes import create_api_router
from engine.config.settings import BotConfig
from engine.core.account_session_manager import AccountSessionManager
from engine.storage.cloud_db import CloudDatabase


class TestApiAuthAndHierarchy(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        AccountSessionManager.reset_instance_for_testing()
        self.db = CloudDatabase(database_url="sqlite+aiosqlite:///:memory:")
        await self.db.init_db()

        self.cfg = BotConfig(world="pt117")
        self.context = EngineContext(config=self.cfg)
        self.context.cloud_db = self.db
        if self.context.session_manager.orchestrator:
            self.context.session_manager.orchestrator.db = self.db
        from engine.storage.cloud_db import AppUserRepository, GameAccountRepository, GameWorldRepository, VillageRepository
        self.context.user_repo = AppUserRepository(self.db)
        self.context.game_account_repo = GameAccountRepository(self.db)
        self.context.game_world_repo = GameWorldRepository(self.db)
        self.context.village_repo = VillageRepository(self.db)

        from engine.api.auth import TokenVerifier
        self.token_verifier = TokenVerifier(valid_token="test_token")
        self.app = FastAPI()
        router = create_api_router(context=self.context, token_verifier=self.token_verifier)
        self.app.include_router(router)
        self.client = TestClient(self.app, headers={"X-Engine-Token": "test_token"})

    async def asyncTearDown(self):
        await self.context.session_manager.stop_current_session()
        await self.db.close()
        AccountSessionManager.reset_instance_for_testing()

    def test_auth_and_account_hierarchy_endpoints(self):
        # 1. Registo de utilizador da app
        reg_res = self.client.post("/api/auth/register", json={
            "email": "test_commander@tribalwars.bot",
            "password": "StrongSecretPassword123!",
            "license_type": "pro",
        })
        self.assertEqual(reg_res.status_code, 200)
        data = reg_res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["user"]["email"], "test_commander@tribalwars.bot")

        # 2. Login
        login_res = self.client.post("/api/auth/login", json={
            "email": "test_commander@tribalwars.bot",
            "password": "StrongSecretPassword123!",
        })
        self.assertEqual(login_res.status_code, 200)
        self.assertEqual(login_res.json()["status"], "success")

        # 3. Consulta /api/auth/me
        me_res = self.client.get("/api/auth/me")
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["user"]["email"], "test_commander@tribalwars.bot")

        # 4. Criação de GameAccount no cofre
        acc_res = self.client.post("/api/accounts", json={
            "game_username": "LordVicious",
            "sid": "0%3Asid_token_test_123",
            "domain": "tribalwars.com.pt",
        })
        self.assertEqual(acc_res.status_code, 200)
        self.assertEqual(acc_res.json()["account"]["game_username"], "LordVicious")

        # 5. Listagem de GameAccounts
        list_res = self.client.get("/api/accounts")
        self.assertEqual(list_res.status_code, 200)
        accounts = list_res.json()["accounts"]
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]["game_username"], "LordVicious")

        # 6. Troca de conta ativa (AccountSessionManager)
        switch_res = self.client.post("/api/accounts/switch", json={
            "game_username": "LordVicious",
        })
        self.assertEqual(switch_res.status_code, 200)
        self.assertEqual(switch_res.json()["session"]["active_game_username"], "LordVicious")

        # 7. Status ativo da sessão
        active_res = self.client.get("/api/accounts/active")
        self.assertEqual(active_res.status_code, 200)
        self.assertEqual(active_res.json()["session"]["active_game_username"], "LordVicious")

        # 8. Adicionar mundos à conta ativa
        w1_res = self.client.post("/api/worlds", json={"world_code": "pt114", "is_active": True})
        self.assertEqual(w1_res.status_code, 200)
        w2_res = self.client.post("/api/worlds", json={"world_code": "pt117", "is_active": True})
        self.assertEqual(w2_res.status_code, 200)

        # 9. Listar mundos
        worlds_res = self.client.get("/api/worlds")
        self.assertEqual(worlds_res.status_code, 200)
        worlds = worlds_res.json()["worlds"]
        self.assertEqual(len(worlds), 2)

        # 10. Toggle de mundo
        toggle_res = self.client.patch("/api/worlds/pt114/toggle", json={"is_active": False})
        self.assertEqual(toggle_res.status_code, 200)
        self.assertFalse(toggle_res.json()["is_active"])

        # 11. Aldeias do mundo e atribuição de modelo
        v_res = self.client.get("/api/worlds/pt117/villages")
        self.assertEqual(v_res.status_code, 200)
        self.assertIn("villages", v_res.json())

        # Sincroniza uma aldeia e atribui modelo
        gw_id = v_res.json()["game_world_id"]
        v = asyncio.run(self.context.village_repo.upsert_village(
            game_world_id=gw_id,
            village_game_id=9999,
            village_name="Fortaleza Central",
            coord_x=500,
            coord_y=500,
            active_build_model_id="default_plan",
        ))
        patch_res = self.client.patch(f"/api/villages/{v.id}/model", json={"active_build_model_id": "rush_resources"})
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["village"]["active_build_model_id"], "rush_resources")
