"""
Testes Unitários para o Módulo de Autenticação e Gestão de Sessão (TribalAuthManager)
"""

import json
import tempfile
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from engine.config.settings import AuthConfig, BotConfig, load_config, save_config_sid
from engine.core.auth_manager import (
    TribalAuthManager,
    clean_sid_value,
    extract_sid_from_cookies,
)


class TestAuthManager(unittest.IsolatedAsyncioTestCase):
    """Validação da extração e persistência de cookies de autenticação."""


    def test_clean_sid_value(self):
        """Verifica a limpeza e decodificação de strings 'sid'."""
        self.assertEqual(clean_sid_value("abc123xyz"), "abc123xyz")
        self.assertEqual(clean_sid_value("'0%3Aabcdef%20123'"), "0:abcdef 123")
        self.assertEqual(clean_sid_value('  "my_sid_cookie"  '), "my_sid_cookie")

    def test_extract_sid_from_dict(self):
        """Extração de 'sid' a partir de dicionário."""
        cookies = {"other": "123", "sid": "session_token_xyz"}
        self.assertEqual(extract_sid_from_cookies(cookies), "session_token_xyz")

    def test_extract_sid_from_simple_cookies(self):
        """Extração de 'sid' a partir de lista de objetos SimpleCookie."""
        cookie_obj = SimpleCookie()
        cookie_obj["sid"] = "cookie_value_from_webview"
        morsel = cookie_obj["sid"]

        extracted = extract_sid_from_cookies([morsel])
        self.assertEqual(extracted, "cookie_value_from_webview")

    def test_extract_sid_from_cookie_dicts(self):
        """Extração de 'sid' de lista de dicionários [{'name': 'sid', 'value': '...'}]"""
        raw_list = [
            {"name": "ref", "value": "start"},
            {"name": "sid", "value": "0%3Asid_token_123"},
        ]
        self.assertEqual(extract_sid_from_cookies(raw_list), "0:sid_token_123")

    def test_save_config_sid(self):
        """Persistência atómica de novo cookie no config.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_file = Path(tmpdir) / "config.json"
            initial_data = {
                "world": "pt117",
                "sid": "old_sid",
                "building": {"template": "rush_resources"},
            }
            cfg_file.write_text(json.dumps(initial_data), encoding="utf-8")

            success = save_config_sid("new_fresh_sid_456", config_path=cfg_file)
            self.assertTrue(success)

            updated = json.loads(cfg_file.read_text(encoding="utf-8"))
            self.assertEqual(updated["sid"], "new_fresh_sid_456")
            self.assertEqual(updated["world"], "pt117")

    def test_load_config_auth_section(self):
        """Carregamento da secção 'auth' do config.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_file = Path(tmpdir) / "config.json"
            cfg_data = {
                "world": "pt117",
                "sid": "sid_123",
                "auth": {
                    "username": "meu_user",
                    "password": "minha_password",
                    "auto_login": True,
                    "keep_alive": True,
                    "keep_alive_interval_minutes": 20.0,
                },
            }
            cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

            bot_cfg = load_config(str(cfg_file))
            self.assertEqual(bot_cfg.auth.username, "meu_user")
            self.assertEqual(bot_cfg.auth.password, "minha_password")
            self.assertTrue(bot_cfg.auth.auto_login)
            self.assertEqual(bot_cfg.auth.keep_alive_interval_minutes, 20.0)

    @patch("engine.core.auth_manager.TribalAuthManager.perform_webview_login")
    async def test_auto_renew_session_flow(self, mock_login):
        """Fluxo assíncrono de renovação de sessão."""
        mock_login.return_value = "new_captured_sid_789"

        account = MagicMock()
        account.world = "pt117"
        account.sid = "old_sid"
        account.init_session = AsyncMock()

        config = BotConfig(
            world="pt117",
            sid="old_sid",
            auth=AuthConfig(username="user", password="pwd", auto_login=True),
        )

        auth_mgr = TribalAuthManager()
        success = await auth_mgr.auto_renew_session(account, config)

        self.assertTrue(success)
        self.assertEqual(account.sid, "new_captured_sid_789")
        account.init_session.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
