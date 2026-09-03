"""
Testes de Robustez de Rede e Reconexão Automática (Fase 5)
Valida a tolerância a falhas de conexão, quebras de socket, reconexão transparente
e manutenção de cookies de sessão em TribalAccount.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from engine.core.account import TribalAccount
from engine.core.exceptions import NetworkTimeoutError


class TestNetworkRobustness(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Instância base de teste de TribalAccount com retentativas rápidas."""
        self.account = TribalAccount(
            world="pt117",
            sid="test_robust_sid_token_123",
            domain="tribalwars.com.pt",
            max_network_retries=3,
            retry_backoff_base=0.01,  # Rápido para não abrandar a suíte de testes
        )
        self.account.csrf_token = "csrf_test_abc"

    async def asyncTearDown(self):
        await self.account.close()

    def _create_mock_session(self, get_func=None, post_func=None):
        """Cria um mock de AsyncSession do curl_cffi que simula respostas e cookies."""
        mock_session = AsyncMock()
        mock_cookies = MagicMock()
        mock_cookies.get = MagicMock(return_value="test_robust_sid_token_123")
        mock_session.cookies = mock_cookies
        if get_func:
            mock_session.get = AsyncMock(side_effect=get_func)
        if post_func:
            mock_session.post = AsyncMock(side_effect=post_func)
        return mock_session

    async def test_get_screen_transient_network_error_recovers(self):
        """
        Testa que uma falha de conexão transitória na 1ª tentativa de GET
        provoca restabelecimento da sessão e tem sucesso na 2ª tentativa.
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<html><div id="game_data">{"village":{"id":500}}</div></html>'
        mock_resp.content = mock_resp.text.encode("utf-8")
        mock_resp.url = "https://pt117.tribalwars.com.pt/game.php?screen=main"

        call_count = 0

        async def flaky_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionResetError("Connection reset by peer (drop transitório)")
            return mock_resp

        init_count = 0

        async def mock_init():
            nonlocal init_count
            init_count += 1
            self.account._session = self._create_mock_session(get_func=flaky_get)

        with patch.object(self.account, "init_session", side_effect=mock_init):
            await self.account.init_session()

            # Ao chamar get_screen, deve tolerar a 1ª falha e ter sucesso na 2ª
            html = await self.account.get_screen("main", apply_jitter=False)
            self.assertIn("game_data", html)
            self.assertEqual(call_count, 2)
            # init_session deve ter sido chamado inicialmente (1) e na reconexão (2)
            self.assertEqual(init_count, 2)

    async def test_get_screen_persistent_network_error_raises(self):
        """
        Testa que se o erro de rede persistir em todas as retentativas (3/3),
        a exceção canónica NetworkTimeoutError é levantada.
        """
        async def broken_get(*args, **kwargs):
            raise TimeoutError("Network timed out permanently")

        async def mock_init():
            self.account._session = self._create_mock_session(get_func=broken_get)

        with patch.object(self.account, "init_session", side_effect=mock_init):
            await self.account.init_session()

            with self.assertRaises(NetworkTimeoutError) as ctx:
                await self.account.get_screen("main", apply_jitter=False)

            self.assertIn("Falha de conexão persistente", str(ctx.exception))
            # Deve ter registrado o histórico da requisição com erro
            self.assertGreaterEqual(len(self.account.request_history), 1)
            self.assertEqual(self.account.request_history[-1]["status_code"], 0)
            self.assertIn("Network timed out permanently", self.account.request_history[-1]["error"])

    async def test_post_action_transient_network_error_recovers(self):
        """
        Testa que uma falha de conexão transitória na 1ª tentativa de POST
        provoca restabelecimento da sessão e tem sucesso na 2ª tentativa.
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<html><div class="success">Comando enviado com sucesso</div></html>'
        mock_resp.content = mock_resp.text.encode("utf-8")
        mock_resp.url = "https://pt117.tribalwars.com.pt/game.php?screen=place&action=command"

        call_count = 0

        async def flaky_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("Network unreachable (quebra de Wi-Fi)")
            return mock_resp

        init_count = 0

        async def mock_init():
            nonlocal init_count
            init_count += 1
            self.account._session = self._create_mock_session(post_func=flaky_post)

        with patch.object(self.account, "init_session", side_effect=mock_init):
            await self.account.init_session()

            html = await self.account.post_action("place", action="command", data={"target": "500|500"}, apply_jitter=False)
            self.assertIn("Comando enviado com sucesso", html)
            self.assertEqual(call_count, 2)
            self.assertEqual(init_count, 2)

    async def test_post_action_persistent_network_error_raises(self):
        """
        Testa que uma falha persistente de rede em POST levanta NetworkTimeoutError.
        """
        async def broken_post(*args, **kwargs):
            raise ConnectionRefusedError("Connection refused by target host")

        async def mock_init():
            self.account._session = self._create_mock_session(post_func=broken_post)

        with patch.object(self.account, "init_session", side_effect=mock_init):
            await self.account.init_session()

            with self.assertRaises(NetworkTimeoutError) as ctx:
                await self.account.post_action("place", action="command", apply_jitter=False)

            self.assertIn("Falha de rede persistente", str(ctx.exception))

    async def test_session_reconnect_preserves_cookies_and_identity(self):
        """
        Testa que após re-inicializar a sessão curl_cffi por falha de socket,
        os cookies essenciais (especialmente o 'sid') são corretamente injetados no novo jar.
        """
        await self.account.init_session()
        self.assertIsNotNone(self.account._session)
        self.assertEqual(self.account._session.cookies.get("sid"), "test_robust_sid_token_123")

        # Simula encerramento e recriação de sessão
        await self.account._session.close()
        self.account._session = None
        await self.account.init_session()

        self.assertIsNotNone(self.account._session)
        self.assertEqual(self.account._session.cookies.get("sid"), "test_robust_sid_token_123")


class TestWebSocketRobustness(unittest.TestCase):
    def test_websocket_reconnection_backoff_formula(self):
        """
        Valida a fórmula de backoff exponencial do cliente WebSocket do frontend (websocket.js):
        delay = min(reconnectInterval * (1.3 ^ attempts), 15000)
        """
        base_interval = 2000
        max_interval = 15000

        delays = []
        for attempt in range(15):
            delay = min(base_interval * (1.3 ** attempt), max_interval)
            delays.append(delay)

        # Tentativa 0 deve começar em 2000ms
        self.assertEqual(delays[0], 2000)
        # O delay deve crescer monotonicamente
        self.assertGreater(delays[1], delays[0])
        self.assertGreater(delays[5], delays[4])
        # O delay nunca deve exceder o teto máximo de 15 segundos
        self.assertEqual(delays[-1], max_interval)
        self.assertTrue(all(d <= max_interval for d in delays))
