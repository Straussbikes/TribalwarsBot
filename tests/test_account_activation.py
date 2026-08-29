"""
Testes Unitários para Ativação e Bloqueio Monousuário de Contas (Single-Active Session)
"""

import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from engine.api.context import EngineContext
from engine.config import BotConfig
from engine.core.account import TribalAccount
from engine.core.profile_manager import AccountProfile, ProfileManager
from engine.core.scheduler import TaskScheduler


class TestAccountActivation(unittest.IsolatedAsyncioTestCase):
    """Valida o ciclo de vida monousuário estrito (Single Active Session)."""

    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.profiles_dir = Path(self.temp_dir.name) / "profiles"
        self.config = BotConfig(world="pt117", sid="initial_sid", domain="tribalwars.com.pt")
        self.scheduler = TaskScheduler("TestScheduler")
        self.account = TribalAccount(world="pt117", sid="initial_sid")
        
        self.context = EngineContext(
            scheduler=self.scheduler,
            config=self.config,
            account=self.account,
        )
        self.context.profile_manager = ProfileManager(self.profiles_dir)

    async def asyncTearDown(self):
        if self.context.scheduler:
            try:
                await self.context.scheduler.stop()
            except Exception:
                pass
        if self.context.account:
            try:
                await self.context.account.close()
            except Exception:
                pass
        self.temp_dir.cleanup()

    async def test_create_and_list_accounts(self):
        """Valida a criação e listagem de contas via context."""
        res = self.context.create_account({
            "name": "Conta Bravo",
            "world_domain": "pt118.tribalwars.com.pt",
            "session_cookie": "sid_bravo_123",
            "village_id": 9999,
        })
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["account"]["name"], "Conta Bravo")
        self.assertEqual(res["account"]["world"], "pt118")

        accounts = self.context.list_accounts()
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]["name"], "Conta Bravo")

    @patch.object(TribalAccount, "init_session", new_callable=AsyncMock)
    @patch.object(TribalAccount, "refresh_state", new_callable=AsyncMock)
    async def test_activate_account_stops_previous_and_starts_new(self, mock_refresh, mock_init):
        """Valida que ativar uma conta encerra a anterior e instancia a nova com os dados corretos."""
        # Cria duas contas
        res1 = self.context.create_account({"name": "Conta 1", "world_domain": "pt117.tribalwars.com.pt", "sid": "sid1"})
        res2 = self.context.create_account({"name": "Conta 2", "world_domain": "pt118.tribalwars.com.pt", "sid": "sid2"})
        acc1_id = res1["account"]["id"]
        acc2_id = res2["account"]["id"]

        # Ativa Conta 1
        act1 = await self.context.activate_account(acc1_id)
        self.assertEqual(act1["status"], "success")
        self.assertEqual(self.context.active_profile_id, acc1_id)
        self.assertEqual(self.context.config.world, "pt117")
        self.assertEqual(self.context.account.world, "pt117")
        self.assertEqual(self.context.account.sid, "sid1")

        # Ativa Conta 2 -> Deve parar e substituir a Conta 1
        act2 = await self.context.activate_account(acc2_id)
        self.assertEqual(act2["status"], "success")
        self.assertEqual(self.context.active_profile_id, acc2_id)
        self.assertEqual(self.context.config.world, "pt118")
        self.assertEqual(self.context.account.world, "pt118")
        self.assertEqual(self.context.account.sid, "sid2")

        # Verifica persistência no profile manager
        active_prof = self.context.profile_manager.get_active_profile()
        self.assertIsNotNone(active_prof)
        self.assertEqual(active_prof.id, acc2_id)

    async def test_disconnect_account(self):
        """Valida que desconectar a conta liberta o agendador e o cliente de rede."""
        res = self.context.create_account({"name": "Conta Alfa", "world_domain": "pt117", "sid": "sid_alfa"})
        acc_id = res["account"]["id"]
        
        with patch.object(TribalAccount, "init_session", new_callable=AsyncMock), \
             patch.object(TribalAccount, "refresh_state", new_callable=AsyncMock):
            await self.context.activate_account(acc_id)
            self.assertEqual(self.context.active_profile_id, acc_id)

        disc = await self.context.disconnect_account()
        self.assertEqual(disc["status"], "success")
        self.assertIsNone(self.context.active_profile_id)
        self.assertIsNone(self.context.account)
        self.assertIsNone(self.context.profile_manager.get_active_profile())


if __name__ == "__main__":
    unittest.main()
