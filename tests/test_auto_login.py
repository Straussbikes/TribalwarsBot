"""
Testes Unitários para o Sistema de Login Automático (Auto-Login) no Tribal Wars.
Valida o cofre AES-256-GCM, o fluxo assíncrono de autenticação, deteção de CAPTCHA e API.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from engine.core.auth_handler import (
    AuthResult,
    TribalWarsAuthHandler,
)
from engine.storage.cloud_db import CredentialsVault


class TestCredentialsVaultPassword(unittest.TestCase):
    """Testes de encriptação e isolamento seguro de palavras-passe no cofre AES-256-GCM."""

    def test_encrypt_and_decrypt_password(self):
        vault = CredentialsVault()
        creds = {
            "sid": "test_sid_1234567890abcdef",
            "world": "pt117",
            "domain": "tribalwars.com.pt",
            "password": "MinhaPasswordUltraSecreta!@#123",
            "auto_login_enabled": True,
        }
        encrypted = vault.encrypt(creds)
        self.assertIsInstance(encrypted, bytes)
        self.assertNotIn(b"MinhaPasswordUltraSecreta", encrypted)

        decrypted = vault.decrypt(encrypted)
        self.assertEqual(decrypted["password"], "MinhaPasswordUltraSecreta!@#123")
        self.assertTrue(decrypted["auto_login_enabled"])
        self.assertEqual(decrypted["world"], "pt117")


class TestTribalWarsAuthHandler(unittest.IsolatedAsyncioTestCase):
    """Testes do fluxo de autenticação assíncrono TribalWarsAuthHandler."""

    async def test_login_missing_credentials(self):
        handler = TribalWarsAuthHandler()
        res = await handler.login(username="", password="")
        self.assertFalse(res.success)
        self.assertEqual(res.error_type, "invalid_input")

    async def test_login_success_flow(self):
        handler = TribalWarsAuthHandler()

        mock_session = AsyncMock()
        mock_session.cookies = MagicMock()
        mock_home_res = MagicMock()
        mock_home_res.text = "<html><body>Bem-vindo ao Tribal Wars</body></html>"
        mock_session.get.side_effect = [
            mock_home_res,
            MagicMock(url="https://pt117.tribalwars.com.pt/game.php", text="<html>OK</html>"),
        ]

        mock_login_res = MagicMock()
        mock_login_res.url = "https://www.tribalwars.com.pt/page/play/pt117"
        mock_login_res.text = "<html><body><a href='/page/play/pt117'>Mundo 117</a></body></html>"
        mock_session.post.return_value = mock_login_res

        mock_session.cookies.get.return_value = "new_valid_session_cookie_12345678"
        mock_session.cookies.jar = []

        with patch.object(handler, "_create_session", return_value=mock_session):
            res = await handler.login(username="meu_user", password="minha_password", target_world="pt117")
            self.assertTrue(res.success)
            self.assertEqual(res.sid, "new_valid_session_cookie_12345678")
            self.assertEqual(res.world, "pt117")
            self.assertEqual(res.username, "meu_user")

    async def test_login_invalid_credentials(self):
        handler = TribalWarsAuthHandler()
        mock_session = AsyncMock()
        mock_session.cookies = MagicMock()

        mock_home_res = MagicMock()
        mock_home_res.text = "<html><body>Bem-vindo</body></html>"
        mock_session.get.return_value = mock_home_res

        mock_login_res = MagicMock()
        mock_login_res.url = "https://www.tribalwars.com.pt/index.php?action=login"
        mock_login_res.text = "<html><body><div class='error_box'>Palavra-passe errada.</div></body></html>"
        mock_session.post.return_value = mock_login_res
        mock_session.cookies.get.return_value = None
        mock_session.cookies.jar = []

        with patch.object(handler, "_create_session", return_value=mock_session):
            res = await handler.login(username="meu_user", password="password_errada", target_world="pt117")
            self.assertFalse(res.success)
            self.assertEqual(res.error_type, "invalid_credentials")
            self.assertTrue("incorretos" in res.message or "errada" in res.message.lower())

    async def test_login_captcha_protection_detected(self):
        handler = TribalWarsAuthHandler()
        mock_session = AsyncMock()
        mock_session.cookies = MagicMock()

        mock_home_res = MagicMock()
        mock_home_res.text = "<html><body>Bem-vindo</body></html>"
        mock_session.get.return_value = mock_home_res

        mock_login_res = MagicMock()
        mock_login_res.url = "https://www.tribalwars.com.pt/index.php?action=login"
        mock_login_res.text = "<html><body><div id='bot_check'>Por favor resolva o desafio CAPTCHA</div></body></html>"
        mock_session.post.return_value = mock_login_res
        mock_session.cookies.get.return_value = None
        mock_session.cookies.jar = []

        with patch.object(handler, "_create_session", return_value=mock_session):
            res = await handler.login(username="meu_user", password="password", target_world="pt117")
            self.assertFalse(res.success)
            self.assertTrue(res.captcha_detected)
            self.assertEqual(res.error_type, "captcha_required")


class TestContextAutoLogin(unittest.IsolatedAsyncioTestCase):
    """Testes da integração de perform_auto_login no EngineContext."""

    async def test_perform_auto_login_no_password(self):
        from engine.api.context import EngineContext

        ctx = EngineContext()
        ctx.current_app_user = MagicMock(id="user_123")

        mock_acc = MagicMock()
        mock_acc.id = "acc_abc"
        mock_acc.app_user_id = "user_123"
        mock_acc.game_username = "Player1"

        ctx.game_account_repo = MagicMock()
        ctx.game_account_repo.get_by_id = AsyncMock(return_value=mock_acc)
        ctx.game_account_repo.decrypt_credentials = MagicMock(return_value={"sid": "old_sid", "password": None})

        res = await ctx.perform_auto_login("acc_abc")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_type"], "no_password")

    async def test_perform_auto_login_success(self):
        from engine.api.context import EngineContext

        ctx = EngineContext()
        ctx.current_app_user = MagicMock(id="user_123")

        mock_acc = MagicMock()
        mock_acc.id = "acc_abc"
        mock_acc.app_user_id = "user_123"
        mock_acc.game_username = "Player1"

        ctx.game_account_repo = MagicMock()
        ctx.game_account_repo.get_by_id = AsyncMock(return_value=mock_acc)
        ctx.game_account_repo.decrypt_credentials = MagicMock(return_value={"sid": "old_sid", "password": "pass", "world": "pt117"})
        ctx.game_account_repo.create_or_update = AsyncMock()

        ctx.account = MagicMock()
        ctx.account.username = "Player1"
        ctx.account.update_sid = AsyncMock()
        ctx.account.refresh_state = AsyncMock()

        fake_auth_res = AuthResult(
            success=True,
            sid="fresh_sid_987654321",
            world="pt117",
            username="Player1",
        )

        with patch("engine.core.auth_handler.TribalWarsAuthHandler.login", AsyncMock(return_value=fake_auth_res)):
            res = await ctx.perform_auto_login("acc_abc")
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["sid"], "fresh_sid_987654321")
            ctx.account.update_sid.assert_awaited_once_with("fresh_sid_987654321")
