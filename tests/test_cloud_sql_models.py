"""
Testes Unitários da Camada de Dados Cloud SQL (PostgreSQL), Modelos e Cofre Criptográfico.
Validação de integridade de esquema, unicidade, cofre AES-256-GCM e repositórios.
"""

import asyncio
from pathlib import Path
import tempfile
import unittest
import uuid

from engine.storage.cloud_db import (
    AppUserRepository,
    CloudDatabase,
    CredentialsVault,
    GameAccountRepository,
    GameWorldRepository,
    VillageRepository,
    hash_password,
    verify_password,
)


class TestCloudSqlModels(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Utiliza SQLite em memória com aiosqlite para execução ultra-rápida e isolada nos testes unitários
        self.db = CloudDatabase(database_url="sqlite+aiosqlite:///:memory:")
        await self.db.init_db(drop_all=True)
        self.user_repo = AppUserRepository(self.db)
        self.acc_repo = GameAccountRepository(self.db)
        self.world_repo = GameWorldRepository(self.db)
        self.village_repo = VillageRepository(self.db)

    async def asyncTearDown(self):
        await self.db.close()

    def test_password_hashing(self):
        pwd = "UltraSecurePassword2026!"
        hashed = hash_password(pwd)
        self.assertTrue(verify_password(pwd, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))

    def test_credentials_vault_aes_gcm(self):
        vault = CredentialsVault()
        payload = {
            "sid": "0%3Asid_token_1234567890",
            "password": "my_secret_tw_password",
            "proxy": "http://user:pass@proxy.corp:8080",
            "domain": "tribalwars.com.pt",
        }
        encrypted = vault.encrypt(payload)
        self.assertIsInstance(encrypted, bytes)
        self.assertGreater(len(encrypted), 30)

        decrypted = vault.decrypt(encrypted)
        self.assertEqual(decrypted["sid"], payload["sid"])
        self.assertEqual(decrypted["password"], payload["password"])
        self.assertEqual(decrypted["proxy"], payload["proxy"])
        self.assertEqual(decrypted["domain"], payload["domain"])

    async def test_app_user_crud_and_uniqueness(self):
        user = await self.user_repo.create_user(
            email="test_user@tribalwars.bot",
            password="Password123!",
            license_type="pro",
        )
        self.assertEqual(user.email, "test_user@tribalwars.bot")
        self.assertEqual(user.license_type, "pro")

        # Autenticação correta
        auth_user = await self.user_repo.authenticate("test_user@tribalwars.bot", "Password123!")
        self.assertIsNotNone(auth_user)
        self.assertEqual(auth_user.id, user.id)

        # Autenticação incorreta
        auth_fail = await self.user_repo.authenticate("test_user@tribalwars.bot", "BadPassword")
        self.assertIsNone(auth_fail)

        # Unicidade de email
        with self.assertRaises(Exception):
            await self.user_repo.create_user(
                email="test_user@tribalwars.bot",
                password="AnotherPassword",
            )

    async def test_game_account_hierarchy_and_vault(self):
        user = await self.user_repo.create_user(
            email="player@tribalwars.bot",
            password="Password123!",
        )

        creds = {"sid": "token_abc", "domain": "tribalwars.com.pt"}
        acc = await self.acc_repo.create_or_update(
            app_user_id=user.id,
            game_username="LordCommander",
            credentials_data=creds,
        )
        self.assertEqual(acc.game_username, "LordCommander")
        self.assertEqual(acc.app_user_id, user.id)

        # Desencriptação do cofre
        decrypted = self.acc_repo.decrypt_credentials(acc)
        self.assertEqual(decrypted["sid"], "token_abc")

        # Atualização idempotente da mesma conta
        acc_updated = await self.acc_repo.create_or_update(
            app_user_id=user.id,
            game_username="LordCommander",
            credentials_data={"sid": "new_token_xyz"},
        )
        self.assertEqual(acc_updated.id, acc.id)
        decrypted2 = self.acc_repo.decrypt_credentials(acc_updated)
        self.assertEqual(decrypted2["sid"], "new_token_xyz")

    async def test_game_worlds_and_villages_hierarchy(self):
        user = await self.user_repo.create_user(
            email="multi_world_player@tribalwars.bot",
            password="Password123!",
        )
        acc = await self.acc_repo.create_or_update(
            app_user_id=user.id,
            game_username="Warlord",
            credentials_data={"sid": "token_warlord"},
        )

        # Criação de 2 mundos
        w1 = await self.world_repo.get_or_create(game_account_id=acc.id, world_code="pt114", is_active=True)
        w2 = await self.world_repo.get_or_create(game_account_id=acc.id, world_code="pt117", is_active=False)

        worlds = await self.world_repo.list_by_account(acc.id)
        self.assertEqual(len(worlds), 2)

        # Toggle de status do mundo
        toggled_w2 = await self.world_repo.toggle_active(acc.id, "pt117", is_active=True)
        self.assertTrue(toggled_w2.is_active)

        # Aldeias associadas ao mundo
        v1 = await self.village_repo.upsert_village(
            game_world_id=w1.id,
            village_game_id=12345,
            village_name="Primeira Aldeia",
            coord_x=450,
            coord_y=550,
            active_build_model_id="rush_resources",
        )
        self.assertEqual(v1.coordinates, "450|550")
        self.assertEqual(v1.active_build_model_id, "rush_resources")

        # Atualização do modelo de construção da aldeia
        updated_v = await self.village_repo.update_build_model(v1.id, "military_rush")
        self.assertEqual(updated_v.active_build_model_id, "military_rush")

        villages_list = await self.village_repo.list_by_world(w1.id)
        self.assertEqual(len(villages_list), 1)
        self.assertEqual(villages_list[0].village_name, "Primeira Aldeia")
