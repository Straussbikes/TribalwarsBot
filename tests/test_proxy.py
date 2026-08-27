"""
Testes Unitários para Validação de Proxies Residenciais/Dedicados
"""

import unittest
from unittest.mock import AsyncMock, patch

from engine.core.profile_manager import test_proxy_connection


class TestProxy(unittest.IsolatedAsyncioTestCase):
    """Valida o utilitário de teste e diagnóstico de proxies."""

    @patch("curl_cffi.requests.AsyncSession.get", new_callable=AsyncMock)
    async def test_proxy_connection_success(self, mock_get):
        """Valida deteção de proxy online e parsing do IP público retornado."""
        from unittest.mock import MagicMock
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value={"ip": "198.51.100.42"})
        mock_get.return_value = mock_resp


        res = await test_proxy_connection("http://user:pass@198.51.100.42:8080")
        self.assertEqual(res["status"], "online")
        self.assertEqual(res["ip"], "198.51.100.42")
        self.assertIn("latency_ms", res)
        self.assertEqual(res["proxy"], "http://user:pass@198.51.100.42:8080")

    @patch("curl_cffi.requests.AsyncSession.get", side_effect=Exception("Connection refused"))
    async def test_proxy_connection_failure(self, mock_get):
        """Valida reporte correto de proxy offline em caso de falha de conexão."""
        res = await test_proxy_connection("http://127.0.0.1:9999")
        self.assertEqual(res["status"], "offline")
        self.assertIn("Connection refused", res["error"])


if __name__ == "__main__":
    unittest.main()
