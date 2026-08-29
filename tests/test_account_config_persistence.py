"""
Tribal Wars Bot - Testes de Persistência de Configurações por Conta no SQLite
Valida que todas as definições (construção, farm, recrutamento, missões, mercado e multi-aldeia)
são persistidas individualmente na base de dados SQLite (data/accounts.db) e isoladas por conta.
"""

from pathlib import Path
import tempfile
import unittest

from engine.config.settings import BotConfig, BuildingConfig, FarmConfig, RecruitmentConfig, load_config, save_config_sid
from engine.core.profile_manager import AccountProfile, ProfileManager
from engine.storage.database import AccountsDatabase
from engine.api.context import EngineContext
from engine.core.scheduler import TaskScheduler


class TestAccountConfigPersistence(unittest.IsolatedAsyncioTestCase):
    """Valida o isolamento e persistência das configurações do bot por conta no SQLite."""

    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "accounts.db"
        self.db = AccountsDatabase(db_path=self.db_path)

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    def test_account_profile_to_bot_config(self):
        """Testa a conversão de AccountProfile com config_data para BotConfig."""
        prof = AccountProfile(
            id="acc_atk_1",
            name="Conta Ataque",
            world="pt117",
            domain="tribalwars.com.pt",
            session_cookie="sid_12345",
            proxy="http://127.0.0.1:8080",
            build_order_strategy="military_rush",
            config_data={
                "farm": {
                    "enabled": True,
                    "mode": "am_farm",
                    "max_distance": 25.0,
                },
                "recruitment": {
                    "enabled": True,
                    "min_free_pop": 5,
                    "targets": {"spear": 100, "axe": 5000},
                },
                "villages": {
                    "1001": {"category": "attack", "building_template": "military_rush"}
                }
            }
        )

        bot_cfg = prof.to_bot_config()
        self.assertIsInstance(bot_cfg, BotConfig)
        self.assertEqual(bot_cfg.world, "pt117")
        self.assertEqual(bot_cfg.sid, "sid_12345")
        self.assertEqual(bot_cfg.proxy, "http://127.0.0.1:8080")
        self.assertEqual(bot_cfg.building.template, "military_rush")
        self.assertTrue(bot_cfg.farm.enabled)
        self.assertEqual(bot_cfg.farm.max_distance, 25.0)
        self.assertTrue(bot_cfg.recruitment.enabled)
        self.assertEqual(bot_cfg.recruitment.min_free_pop, 5)
        self.assertIn("1001", bot_cfg.villages)
        self.assertEqual(bot_cfg.villages["1001"].category, "attack")

    def test_database_account_config_persistence(self):
        """Testa a gravação e recuperação de configurações no SQLite por conta."""
        # 1. Cria duas contas com configurações distintas
        self.db.save_account({
            "id": "account_a",
            "name": "Conta A (Farm Ativo)",
            "world": "pt117",
            "session_cookie": "sid_a",
            "config_data": {
                "farm": {"enabled": True, "max_distance": 30.0},
                "recruitment": {"enabled": True, "min_free_pop": 20},
            }
        })

        self.db.save_account({
            "id": "account_b",
            "name": "Conta B (Farm Desativado)",
            "world": "pt118",
            "session_cookie": "sid_b",
            "config_data": {
                "farm": {"enabled": False, "max_distance": 10.0},
                "recruitment": {"enabled": False, "min_free_pop": 2},
            }
        })

        # 2. Verifica que cada conta manteve as suas configurações isoladas
        cfg_a = self.db.get_account_config("account_a")
        cfg_b = self.db.get_account_config("account_b")

        self.assertTrue(cfg_a["farm"]["enabled"])
        self.assertEqual(cfg_a["farm"]["max_distance"], 30.0)
        self.assertEqual(cfg_a["recruitment"]["min_free_pop"], 20)

        self.assertFalse(cfg_b["farm"]["enabled"])
        self.assertEqual(cfg_b["farm"]["max_distance"], 10.0)
        self.assertEqual(cfg_b["recruitment"]["min_free_pop"], 2)

        # 3. Atualiza configuração da conta A
        self.db.save_account_config("account_a", {"farm": {"max_distance": 45.0}})
        cfg_a_updated = self.db.get_account_config("account_a")
        self.assertEqual(cfg_a_updated["farm"]["max_distance"], 45.0)
        # Conta B não foi afetada
        self.assertEqual(self.db.get_account_config("account_b")["farm"]["max_distance"], 10.0)

    async def test_engine_context_account_activation_and_saving(self):
        """Testa a alternância de contas no EngineContext e gravação no SQLite."""
        # 1. Cria perfis de conta no SQLite
        self.db.save_account({
            "id": "acc_alpha",
            "name": "Alpha",
            "world": "pt117",
            "session_cookie": "sid_alpha",
            "config_data": {
                "building": {"template": "rush_resources", "max_queue": 3},
                "farm": {"enabled": True},
            }
        })

        self.db.save_account({
            "id": "acc_beta",
            "name": "Beta",
            "world": "pt118",
            "session_cookie": "sid_beta",
            "config_data": {
                "building": {"template": "military_rush", "max_queue": 5},
                "farm": {"enabled": False},
            }
        })

        ctx = EngineContext(db=self.db)

        # 2. Ativa conta Alpha
        res_a = await ctx.activate_account("acc_alpha")
        self.assertEqual(res_a["status"], "success")
        self.assertEqual(ctx.active_profile_id, "acc_alpha")
        self.assertEqual(ctx.config.world, "pt117")
        self.assertEqual(ctx.config.building.template, "rush_resources")
        self.assertEqual(ctx.config.building.max_queue, 3)
        self.assertTrue(ctx.config.farm.enabled)

        # 3. Altera configurações em tempo de execução
        res_update = ctx.update_config_and_save({"building": {"max_queue": 4}})
        self.assertEqual(res_update["status"], "success")
        self.assertEqual(ctx.config.building.max_queue, 4)

        # Verifica no SQLite que a conta Alpha foi atualizada
        alpha_db_cfg = self.db.get_account_config("acc_alpha")
        self.assertEqual(alpha_db_cfg["building"]["max_queue"], 4)

        # 4. Ativa conta Beta
        res_b = await ctx.activate_account("acc_beta")
        self.assertEqual(res_b["status"], "success")
        self.assertEqual(ctx.active_profile_id, "acc_beta")
        self.assertEqual(ctx.config.world, "pt118")
        self.assertEqual(ctx.config.building.template, "military_rush")
        self.assertEqual(ctx.config.building.max_queue, 5)
        self.assertFalse(ctx.config.farm.enabled)

        # 5. Salva novo sid para a conta Beta
        save_config_sid("new_sid_beta_999", account_id="acc_beta", db=self.db)
        acc_beta_db = self.db.get_account("acc_beta")
        self.assertEqual(acc_beta_db["session_cookie"], "new_sid_beta_999")
