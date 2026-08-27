"""
Suíte de testes unitários para a Camada de Abstração Multiplataforma (engine/platforms).
Valida resolução de adaptadores para Windows, macOS e Linux, comportamento de rede e proteções.
"""

import unittest
from unittest.mock import MagicMock

from engine.platforms import (
    BasePlatformAdapter,
    WindowsPlatformAdapter,
    MacOSPlatformAdapter,
    LinuxPlatformAdapter,
    get_platform_adapter,
)


class TestPlatformAbstraction(unittest.TestCase):
    """Testes da camada de adaptadores de plataforma."""

    def test_adapter_resolution(self):
        """Valida que get_platform_adapter instancia a classe correta conforme o SO."""
        win_adapter = get_platform_adapter(force_platform="win32")
        self.assertIsInstance(win_adapter, WindowsPlatformAdapter)
        self.assertEqual(win_adapter.platform_name, "windows")
        self.assertEqual(win_adapter.gui_backend, "edgechromium")

        mac_adapter = get_platform_adapter(force_platform="darwin")
        self.assertIsInstance(mac_adapter, MacOSPlatformAdapter)
        self.assertEqual(mac_adapter.platform_name, "darwin")
        self.assertEqual(mac_adapter.gui_backend, "cocoa")

        linux_adapter = get_platform_adapter(force_platform="linux")
        self.assertIsInstance(linux_adapter, LinuxPlatformAdapter)
        self.assertEqual(linux_adapter.platform_name, "linux")
        self.assertEqual(linux_adapter.gui_backend, "gtk")

    def test_captcha_asset_hijack_detection(self):
        """Valida a deteção de URLs de assets estáticos de captchas que causariam ecrã branco."""
        adapter = get_platform_adapter()

        # URLs maliciosas/desviadas que devem ser bloqueadas
        self.assertTrue(adapter.is_captcha_or_asset_hijack("https://newassets.hcaptcha.com/captcha/v1/80155bd7"))
        self.assertTrue(adapter.is_captcha_or_asset_hijack("https://assets.hcaptcha.com/c/123/site.js"))
        self.assertTrue(adapter.is_captcha_or_asset_hijack("https://challenges.cloudflare.com/turnstile/v0/api.js"))

        # URLs legítimas do Tribal Wars que devem passar
        self.assertFalse(adapter.is_captcha_or_asset_hijack("https://www.tribalwars.com.pt/"))
        self.assertFalse(adapter.is_captcha_or_asset_hijack("https://pt117.tribalwars.com.pt/game.php?village=123"))
        self.assertFalse(adapter.is_captcha_or_asset_hijack("https://pt117.tribalwars.com.pt/page/play"))
        self.assertFalse(adapter.is_captcha_or_asset_hijack(""))

    def test_extract_cookies_safe(self):
        """Valida que extract_cookies retorna lista mesmo em caso de erro da janela."""
        adapter = get_platform_adapter()

        # Janela funcional
        mock_window = MagicMock()
        mock_window.get_cookies.return_value = [{"name": "sid", "value": "test_sid"}]
        cookies = adapter.extract_cookies(mock_window)
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0]["value"], "test_sid")

        # Janela com exceção
        mock_window_err = MagicMock()
        mock_window_err.get_cookies.side_effect = RuntimeError("Dead object")
        cookies_err = adapter.extract_cookies(mock_window_err)
        self.assertEqual(cookies_err, [])

    def test_get_safe_url(self):
        """Valida leitura protegida do URL atual via evaluate_js."""
        adapter = get_platform_adapter()

        mock_window = MagicMock()
        mock_window.evaluate_js.return_value = "https://pt117.tribalwars.com.pt/game.php"
        self.assertEqual(adapter.get_safe_url(mock_window), "https://pt117.tribalwars.com.pt/game.php")

        mock_window_err = MagicMock()
        mock_window_err.evaluate_js.side_effect = Exception("UI thread unavailable")
        self.assertEqual(adapter.get_safe_url(mock_window_err, default="fallback"), "fallback")

    def test_windows_network_interception_setup(self):
        """Valida que o adaptador Windows registra eventos de rede request_sent e response_received."""
        from webview.event import Event

        win_adapter = WindowsPlatformAdapter()
        mock_window = MagicMock()
        mock_window.events.request_sent = Event(mock_window)
        mock_window.events.response_received = Event(mock_window)

        captured = []
        win_adapter.setup_network_interception(mock_window, lambda h: captured.append(h))

        self.assertEqual(len(mock_window.events.request_sent), 1)
        self.assertEqual(len(mock_window.events.response_received), 1)

    def test_macos_network_interception_bypassed(self):
        """Valida que o adaptador macOS NÃO intercepta request_sent (evita quebra de POST), mas escuta response_received."""
        from webview.event import Event

        mac_adapter = MacOSPlatformAdapter()
        mock_window = MagicMock()
        mock_window.events.request_sent = Event(mock_window)
        mock_window.events.response_received = Event(mock_window)

        mac_adapter.setup_network_interception(mock_window, lambda h: None)

        self.assertEqual(len(mock_window.events.request_sent), 0)
        self.assertEqual(len(mock_window.events.response_received), 1)


if __name__ == "__main__":
    unittest.main()
