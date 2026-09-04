import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from engine.api.context import EngineContext
from engine.config.settings import BotConfig
from engine.core.account import TribalAccount
from engine.core.profile_manager import AccountProfile


class TestWorldSelection(unittest.IsolatedAsyncioTestCase):

    async def test_get_account_available_worlds(self):
        """Testa a deteção de mundos disponíveis e status de presença na Top Bar."""
        cfg = BotConfig(world="pt117", sid="dummy_sid")
        ctx = EngineContext(config=cfg)
        
        # Mock account
        mock_account = MagicMock(spec=TribalAccount)
        mock_account.world = "pt117"
        mock_account.sid = "dummy_sid"
        mock_account.player_name = "ReiTribal"
        mock_account.discover_active_worlds = AsyncMock(return_value=["pt117", "pt118", "pt116"])
        ctx.account = mock_account

        res = await ctx.get_account_available_worlds()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["current_world"], "pt117")
        
        worlds = {w["world"]: w for w in res["worlds"]}
        self.assertIn("pt117", worlds)
        self.assertIn("pt118", worlds)
        self.assertIn("pt116", worlds)
        
        # pt117 está ativo na top bar (é o mundo atual da config)
        self.assertTrue(worlds["pt117"]["is_in_top_bar"])
        # pt118 ainda não está na top bar
        self.assertFalse(worlds["pt118"]["is_in_top_bar"])

    async def test_toggle_game_world_worker(self):
        """Testa a ativação/pausa de automação por mundo (toggle de mundo x ou y)."""
        cfg = BotConfig(world="pt117", sid="dummy_sid")
        ctx = EngineContext(config=cfg)
    
        # Cria perfil
        prof = AccountProfile(id="test_acc_1", name="Conta Teste", world="pt117")
        ctx.profile_manager.save_profile(prof)
        ctx.active_profile_id = prof.id

        # Toggle pt118 para pausado
        res_pause = await ctx.toggle_game_world_worker(world_code="pt118", is_active=False, account_id=prof.id)
        self.assertEqual(res_pause["status"], "success")
        self.assertFalse(res_pause["is_active"])

        updated_prof = ctx.profile_manager.get_profile(prof.id)
        self.assertFalse(updated_prof.worlds["pt118"]["is_active"])

        # Toggle pt118 para ativo
        res_active = await ctx.toggle_game_world_worker(world_code="pt118", is_active=True, account_id=prof.id)
        self.assertEqual(res_active["status"], "success")
        updated_prof2 = ctx.profile_manager.get_profile(prof.id)
        self.assertTrue(updated_prof2.worlds["pt118"]["is_active"])

    async def test_activate_and_persist_world(self):
        """Testa o fluxo de conexão, persistência e ativação de um novo mundo para a conta."""
        cfg = BotConfig(world="pt117", sid="dummy_sid")
        ctx = EngineContext(config=cfg)

        prof = AccountProfile(id="test_acc_2", name="Conta Teste 2", world="pt117")
        ctx.profile_manager.save_profile(prof)
        ctx.active_profile_id = prof.id

        with patch("engine.api.context.TribalAccount") as MockAccClass:
            mock_acc_instance = MagicMock()
            mock_acc_instance.world = "pt118"
            mock_acc_instance.current_village_id = 1234
            mock_v = MagicMock()
            mock_v.id = 1234
            mock_v.name = "Aldeia Nova"
            mock_v.x = 500
            mock_v.y = 500
            mock_acc_instance.villages = {1234: mock_v}
            mock_acc_instance.init_session = AsyncMock()
            mock_acc_instance.refresh_state = AsyncMock()
            mock_acc_instance.fetch_overview_villages = AsyncMock()
            mock_acc_instance.obtain_session_for_world = AsyncMock(return_value="target_sid_118")
            MockAccClass.return_value = mock_acc_instance

            res = await ctx.activate_and_persist_world(world_code="pt118", sid="target_sid_118")
            self.assertEqual(res["status"], "success")
            self.assertIn("PT118", res["message"])
            self.assertEqual(res["villages_count"], 1)

            # Verifica persistência no perfil
            updated_prof = ctx.profile_manager.get_profile(prof.id)
            self.assertIn("pt118", updated_prof.worlds)
            self.assertEqual(updated_prof.worlds["pt118"]["village_id"], 1234)
            self.assertTrue(updated_prof.worlds["pt118"]["is_active"])

            # Verifica registo no MultiWorldManager
            self.assertIn("pt118", ctx.world_manager.instances)
            self.assertEqual(ctx.world_manager.active_world, "pt118")

    async def test_api_endpoints(self):
        """Testa as rotas REST /api/worlds/available-to-add e toggle por conta."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from engine.api.auth import TokenVerifier
        from engine.api.routes import create_api_router

        cfg = BotConfig(world="pt117", sid="dummy_sid")
        ctx = EngineContext(config=cfg)

        prof = AccountProfile(id="test_acc_api", name="Conta API", world="pt117")
        ctx.profile_manager.save_profile(prof)
        ctx.active_profile_id = prof.id

        app = FastAPI()
        token_verifier = TokenVerifier(valid_token="test_token")
        app.include_router(create_api_router(ctx, token_verifier))

        with TestClient(app, headers={"X-Engine-Token": "test_token"}) as client:
            resp = client.get("/api/worlds/available-to-add")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "success")

            resp_toggle = client.post(
                f"/api/accounts/{prof.id}/worlds/pt118/toggle",
                json={"is_active": False},
            )
            self.assertEqual(resp_toggle.status_code, 200)
            data_toggle = resp_toggle.json()
            self.assertEqual(data_toggle["status"], "success")
            self.assertFalse(data_toggle["is_active"])
