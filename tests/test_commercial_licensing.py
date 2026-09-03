"""
Testes unitários para o sistema comercial de licenças, validade, suspensão e limite de contas.
"""

import asyncio
from datetime import datetime, timezone, timedelta
import unittest
from unittest.mock import AsyncMock, MagicMock

from engine.storage.cloud_db import AppUser, AppUserRepository
from engine.api.context import EngineContext


class TestCommercialLicensing(unittest.IsolatedAsyncioTestCase):
    """Valida o modelo de dados AppUser, métodos do repositório e regras de acesso do contexto."""

    def test_app_user_dict_and_expiration(self):
        # 1. Utilizador com subscrição ativa
        future_date = datetime.now(timezone.utc) + timedelta(days=20)
        user_active = AppUser(
            id="u1",
            email="cliente@ativo.com",
            password_hash="hash",
            license_type="standard",
            is_active=True,
            expires_at=future_date,
            max_accounts=1,
            notes="Cliente teste",
        )
        d_active = user_active.to_dict()
        self.assertFalse(d_active["is_expired"])
        self.assertTrue(d_active["is_active"])
        self.assertGreaterEqual(d_active["days_left"], 19)

        # 2. Utilizador com subscrição expirada
        past_date = datetime.now(timezone.utc) - timedelta(days=5)
        user_expired = AppUser(
            id="u2",
            email="cliente@expirado.com",
            password_hash="hash",
            license_type="standard",
            is_active=True,
            expires_at=past_date,
            max_accounts=1,
        )
        d_expired = user_expired.to_dict()
        self.assertTrue(d_expired["is_expired"])
        self.assertEqual(d_expired["days_left"], 0)

        # 3. Utilizador vitalício
        user_lifetime = AppUser(
            id="u3",
            email="admin@vitalicio.com",
            password_hash="hash",
            license_type="enterprise",
            is_active=True,
            expires_at=None,
            max_accounts=10,
        )
        d_lifetime = user_lifetime.to_dict()
        self.assertFalse(d_lifetime["is_expired"])
        self.assertIsNone(d_lifetime["expires_at"])
        self.assertIsNone(d_lifetime["days_left"])

    async def test_context_login_blocks_suspended_user(self):
        ctx = EngineContext()
        ctx.user_repo = MagicMock()

        user_suspended = MagicMock()
        user_suspended.id = "u_susp"
        user_suspended.email = "suspenso@teste.com"
        user_suspended.is_active = False
        user_suspended.expires_at = None

        ctx.user_repo.authenticate = AsyncMock(return_value=user_suspended)

        res = await ctx.login_app_user("suspenso@teste.com", "senha123")
        self.assertEqual(res["status"], "error")
        self.assertIn("suspensa", res["message"].lower())

    async def test_context_login_blocks_expired_user(self):
        ctx = EngineContext()
        ctx.user_repo = MagicMock()

        user_expired = MagicMock()
        user_expired.id = "u_exp"
        user_expired.email = "expirado@teste.com"
        user_expired.is_active = True
        user_expired.expires_at = datetime.now(timezone.utc) - timedelta(days=2)

        ctx.user_repo.authenticate = AsyncMock(return_value=user_expired)

        res = await ctx.login_app_user("expirado@teste.com", "senha123")
        self.assertEqual(res["status"], "error")
        self.assertIn("expirou", res["message"].lower())

    async def test_context_add_game_account_enforces_limit(self):
        ctx = EngineContext()
        user = MagicMock()
        user.id = "u_limited"
        user.max_accounts = 1
        ctx.current_app_user = user

        # Simula que o utilizador já tem 1 conta no repositório
        existing_acc = MagicMock()
        existing_acc.id = "acc1"
        existing_acc.game_username = "PlayerExistente"

        ctx.game_account_repo = MagicMock()
        ctx.game_account_repo.get_by_user_and_username = AsyncMock(return_value=None)
        ctx.game_account_repo.list_by_user = AsyncMock(return_value=[existing_acc])

        # Tentar adicionar uma segunda conta de jogo diferente
        res = await ctx.add_user_game_account(game_username="NovoPlayer2", sid="sid123")
        self.assertEqual(res["status"], "error")
        self.assertIn("limite de contas atingido", res["message"].lower())
