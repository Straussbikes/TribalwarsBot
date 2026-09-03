"""
Testes Unitários do Gestor de Sessão e Mutex de Contas (AccountSessionManager).
Validação de exclusão mútua estrita, cancellation tokens, bloqueio de conflitos concorrentes
e paragem graciosa na transição de contas.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from engine.core.account_session_manager import (
    AccountSessionConflictError,
    AccountSessionManager,
    AccountSessionState,
)


class TestAccountSessionManager(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        AccountSessionManager.reset_instance_for_testing()
        self.mgr = AccountSessionManager.get_instance()

    def tearDown(self):
        AccountSessionManager.reset_instance_for_testing()

    def test_singleton_identity(self):
        m1 = AccountSessionManager.get_instance()
        m2 = AccountSessionManager()
        self.assertIs(m1, m2)

    async def test_initial_state_idle(self):
        status = self.mgr.get_status()
        self.assertEqual(status["state"], AccountSessionState.IDLE.value)
        self.assertIsNone(status["active_game_username"])
        self.assertFalse(status["is_running"])

    async def test_assert_account_active_enforces_active_user(self):
        # Sem conta ativa -> deve falhar
        with self.assertRaises(AccountSessionConflictError):
            self.mgr.assert_account_active("PlayerOne")

        # Ativa PlayerOne
        mock_orch = MagicMock()
        mock_orch.on_account_switched = AsyncMock()
        self.mgr.orchestrator = mock_orch

        await self.mgr.switch_account(
            app_user_id="user_123",
            game_username="PlayerOne",
            account_id="acc_123",
        )

        # PlayerOne tem acesso permitido
        self.mgr.assert_account_active("PlayerOne")
        self.mgr.assert_account_active("playerone")  # case-insensitive

        # Qualquer outra conta deve ser rejeitada imediatamente
        with self.assertRaises(AccountSessionConflictError):
            self.mgr.assert_account_active("PlayerTwo")

    async def test_graceful_cancellation_on_account_switch(self):
        mock_orch = MagicMock()
        mock_orch.on_account_switched = AsyncMock()
        mock_orch.stop_all_workers = AsyncMock()
        self.mgr.orchestrator = mock_orch

        # 1. Ativa PlayerOne
        await self.mgr.switch_account(
            app_user_id="user_1",
            game_username="PlayerOne",
            account_id="acc_1",
        )
        token_p1 = self.mgr.get_cancellation_token()
        self.assertFalse(token_p1.is_set())  # Não cancelado

        # Simula uma tarefa em segundo plano a monitorizar o cancellation token
        cancelled_flag = False

        async def worker_loop():
            nonlocal cancelled_flag
            while not token_p1.is_set():
                await asyncio.sleep(0.01)
            cancelled_flag = True

        task = asyncio.create_task(worker_loop())

        # 2. Troca atómica para PlayerTwo
        status_p2 = await self.mgr.switch_account(
            app_user_id="user_1",
            game_username="PlayerTwo",
            account_id="acc_2",
            timeout=1.0,
        )

        # Aguarda a tarefa do PlayerOne detetar o cancelamento
        await asyncio.wait_for(task, timeout=1.0)
        self.assertTrue(cancelled_flag)

        # Verifica se o stop_all_workers foi invocado para desalocar recursos
        mock_orch.stop_all_workers.assert_called_once()

        # Novo estado reflete unicamente o PlayerTwo
        self.assertEqual(status_p2["active_game_username"], "PlayerTwo")
        self.assertEqual(self.mgr.active_game_username, "PlayerTwo")
        self.mgr.assert_account_active("PlayerTwo")
        with self.assertRaises(AccountSessionConflictError):
            self.mgr.assert_account_active("PlayerOne")

    async def test_stop_current_session(self):
        mock_orch = MagicMock()
        mock_orch.on_account_switched = AsyncMock()
        mock_orch.stop_all_workers = AsyncMock()
        self.mgr.orchestrator = mock_orch

        await self.mgr.switch_account(
            app_user_id="user_1",
            game_username="PlayerActive",
            account_id="acc_1",
        )
        self.assertEqual(self.mgr.state, AccountSessionState.RUNNING)

        await self.mgr.stop_current_session()
        self.assertEqual(self.mgr.state, AccountSessionState.IDLE)
        self.assertIsNone(self.mgr.active_game_username)
        mock_orch.stop_all_workers.assert_called_once()
