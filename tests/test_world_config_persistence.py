"""
Testes de persistência, isolamento e segregação de configurações por mundo (GameWorld) no Cloud SQL.
Valida que 1 Conta tem N Mundos e que cada Mundo preserva as suas próprias configurações sem interferência.
"""

import asyncio
import unittest
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from engine.api.server import create_app
from engine.api.context import EngineContext
from engine.config.settings import BotConfig
from engine.storage.cloud_db import CloudDatabase, GameAccountRepository, GameWorldRepository, AppUserRepository


class TestWorldConfigPersistence(unittest.IsolatedAsyncioTestCase):
    """Valida a persistência isolada por mundo e segregação de credenciais."""

    async def asyncSetUp(self):
        # Base de dados em memória SQLite isolada para este teste
        self.cloud_db = CloudDatabase(database_url="sqlite+aiosqlite:///:memory:")
        await self.cloud_db.init_db(drop_all=True)

        self.user_repo = AppUserRepository(self.cloud_db)
        self.acc_repo = GameAccountRepository(self.cloud_db)
        self.gw_repo = GameWorldRepository(self.cloud_db)

        # 1. Cria utilizador da aplicação (AppUser)
        self.user = await self.user_repo.create_user(
            email="testuser@example.com",
            password="secretpassword123",
        )

        # 2. Cria conta de jogo (GameAccount) com cofre AES
        self.acc = await self.acc_repo.create_or_update(
            app_user_id=self.user.id,
            game_username="Strauss",
            credentials_data={
                "username": "Strauss",
                "password": "gamepassword456",
                "sid": "cookie_sid_abc",
                "domain": "tribalwars.com.pt",
                "auto_login_enabled": True,
            },
        )

        # 3. Cria dois mundos associados a esta conta (1 conta -> N mundos)
        self.w1 = await self.gw_repo.get_or_create(self.acc.id, "pt117", is_active=True)
        self.w2 = await self.gw_repo.get_or_create(self.acc.id, "pt114", is_active=True)

    async def test_cloud_db_world_config_isolation(self):
        """Valida que save_world_config e get_world_config isolam configurações entre mundos da mesma conta."""
        cfg_pt117 = {
            "farm": {"min_interval_seconds": 180.0, "enabled": True},
            "building": {"template": "balanced", "max_queue": 3},
        }
        cfg_pt114 = {
            "farm": {"min_interval_seconds": 360.0, "enabled": False},
            "building": {"template": "military_rush", "max_queue": 1},
        }

        # Grava configurações distintas para cada mundo
        ok1 = await self.gw_repo.save_world_config(self.acc.id, "pt117", cfg_pt117)
        ok2 = await self.gw_repo.save_world_config(self.acc.id, "pt114", cfg_pt114)
        self.assertTrue(ok1)
        self.assertTrue(ok2)

        # Recupera as configurações e valida o isolamento estrito
        saved_117 = await self.gw_repo.get_world_config(self.acc.id, "pt117")
        saved_114 = await self.gw_repo.get_world_config(self.acc.id, "pt114")

        self.assertIsNotNone(saved_117)
        self.assertIsNotNone(saved_114)

        self.assertEqual(saved_117["farm"]["min_interval_seconds"], 180.0)
        self.assertEqual(saved_117["building"]["template"], "balanced")
        self.assertTrue(saved_117["farm"]["enabled"])

        self.assertEqual(saved_114["farm"]["min_interval_seconds"], 360.0)
        self.assertEqual(saved_114["building"]["template"], "military_rush")
        self.assertFalse(saved_114["farm"]["enabled"])

        # Atualização incremental (deep merge) em pt117 não deve apagar template nem afetar pt114
        await self.gw_repo.save_world_config(self.acc.id, "pt117", {"farm": {"skip_losses": True}})
        updated_117 = await self.gw_repo.get_world_config(self.acc.id, "pt117")
        self.assertEqual(updated_117["farm"]["min_interval_seconds"], 180.0)
        self.assertTrue(updated_117["farm"]["skip_losses"])
        self.assertEqual(updated_117["building"]["template"], "balanced")

        # pt114 permanece intocado
        unchanged_114 = await self.gw_repo.get_world_config(self.acc.id, "pt114")
        self.assertEqual(unchanged_114["farm"]["min_interval_seconds"], 360.0)
        self.assertNotIn("skip_losses", unchanged_114["farm"])

    async def test_auth_data_remains_in_account_vault(self):
        """Valida que os dados de autenticação (password, auto_login, sid) pertencem e persistem na conta."""
        creds = self.acc_repo.decrypt_credentials(self.acc)
        self.assertEqual(creds["username"], "Strauss")
        self.assertEqual(creds["password"], "gamepassword456")
        self.assertEqual(creds["sid"], "cookie_sid_abc")
        self.assertTrue(creds["auto_login_enabled"])

    async def test_engine_context_world_config_and_switch(self):
        """Valida a integração no EngineContext: update_config_and_save por mundo e switch_world."""
        config = BotConfig(world="pt117", domain="tribalwars.com.pt")
        context = EngineContext(config=config, db=None)
        context.cloud_db = self.cloud_db
        context.game_world_repo = self.gw_repo
        context.game_account_repo = self.acc_repo
        context.current_app_user = self.user
        context.active_profile_id = self.acc.id

        # 1. Salva configuração específica para pt117
        res1 = context.update_config_and_save({
            "farm": {"min_interval_seconds": 150.0},
            "building": {"template": "default_plan"},
        }, world="pt117")
        self.assertEqual(res1["status"], "success")

        # 2. Salva configuração específica para pt114
        res2 = context.update_config_and_save({
            "farm": {"min_interval_seconds": 300.0},
            "building": {"template": "rush_custom"},
        }, world="pt114")
        self.assertEqual(res2["status"], "success")

        # Aguarda sincronização assíncrona com a base de dados
        await asyncio.sleep(0.05)

        # 3. Consulta as configurações de cada mundo via get_config_dict
        cfg_117 = context.get_config_dict(world="pt117")
        cfg_114 = context.get_config_dict(world="pt114")

        # Config atual focado é pt117
        self.assertEqual(context.config.world, "pt117")
        self.assertEqual(context.config.farm.min_interval_seconds, 150.0)

        # 4. Alterna foco para pt114
        inst114 = MagicMock()
        mock_acc = MagicMock()
        mock_acc.current_village = None
        mock_acc.villages = {}
        mock_acc.player = None
        inst114.account = mock_acc
        inst114.scheduler = MagicMock()
        inst114.config = BotConfig(world="pt114")
        inst114.to_dict.return_value = {"world": "pt114"}
        context.world_manager.instances["pt114"] = inst114

        sw_res = await context.switch_world("pt114")
        self.assertEqual(sw_res["status"], "success")
        self.assertEqual(context.config.world, "pt114")
        self.assertEqual(context.config.farm.min_interval_seconds, 300.0)
        self.assertEqual(context.config.building.template, "rush_custom")

    def test_recruitment_config_with_nested_batch_sizes(self):
        """Garante que update_config_and_save suporta batch_sizes tanto flat como aninhado por modelo."""
        config = BotConfig(world="pt117", domain="tribalwars.com.pt")
        context = EngineContext(config=config, db=None)
        context.cloud_db = self.cloud_db
        context.game_world_repo = self.gw_repo
        context.game_account_repo = self.acc_repo
        context.current_app_user = self.user
        context.active_profile_id = self.acc.id

        # Salva com batch_sizes aninhado por modelo (formato do frontend)
        res = context.update_config_and_save({
            "recruitment": {
                "enabled": True,
                "interval_seconds": 120,
                "min_reserve_resources": 500,
                "models": {
                    "attack": {"spear": 30, "axe": 6000},
                    "defense": {"spear": 7000, "sword": 7000},
                },
                "batch_sizes": {
                    "attack": {"spear": 5, "axe": 10},
                    "defense": {"spear": 10, "sword": 10},
                },
            }
        }, world="pt117")

        self.assertEqual(res["status"], "success")
        self.assertTrue(context.config.recruitment.enabled)
        self.assertEqual(context.config.recruitment.batch_sizes.get("spear"), 10)
        self.assertEqual(context.config.recruitment.batch_sizes.get("axe"), 10)


class TestWorldConfigRoutes(unittest.TestCase):
    """Testa os endpoints REST /api/config com parâmetro de mundo e /api/worlds/{world}/config."""

    def setUp(self):
        self.config = BotConfig(world="pt117")
        self.context = EngineContext(config=self.config, db=None)
        self.token = "test-token-sec"
        self.app = create_app(self.context, token=self.token, attach_log_handler=False)
        self.client = TestClient(self.app)

    def test_routes_world_config_query_and_path(self):
        """Valida que /api/config?world= e /api/worlds/{world_code}/config funcionam com sucesso."""
        headers = {"X-Engine-Token": self.token}

        # 1. GET /api/config
        r1 = self.client.get("/api/config", headers=headers)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json().get("world"), "pt117")

        # 2. POST /api/worlds/pt114/config
        r2 = self.client.post(
            "/api/worlds/pt114/config",
            headers=headers,
            json={"farm": {"min_interval_seconds": 250.0}},
        )
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json().get("status"), "success")

        # 3. GET /api/worlds/pt114/config
        r3 = self.client.get("/api/worlds/pt114/config", headers=headers)
        self.assertEqual(r3.status_code, 200)

        # 4. POST /api/config?world=pt118
        r4 = self.client.post(
            "/api/config?world=pt118",
            headers=headers,
            json={"farm": {"min_interval_seconds": 190.0}},
        )
        self.assertEqual(r4.status_code, 200)
        self.assertEqual(r4.json().get("status"), "success")


if __name__ == "__main__":
    unittest.main()
