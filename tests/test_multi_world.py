"""
Testes Unitários para o Orquestrador Multi-Mundo (MultiWorldManager).
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from engine.config.settings import BotConfig
from engine.core.multi_world import MultiWorldManager, WorldInstance


class TestMultiWorldManager(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.manager = MultiWorldManager()

    @patch("engine.core.account.TribalAccount.init_session", new_callable=AsyncMock)
    async def test_register_and_switch_worlds(self, mock_init):
        """Testa registo de múltiplos mundos concorrentes e alternância de foco."""
        w1 = await self.manager.register_world(
            world="pt117",
            sid="sid_pt117",
            domain="tribalwars.com.pt",
            auto_start=False,
        )
        self.assertIn("pt117", self.manager.instances)
        self.assertEqual(self.manager.active_world, "pt117")

        w2 = await self.manager.register_world(
            world="pt118",
            sid="sid_pt118",
            domain="tribalwars.com.pt",
            proxy="http://user:pass@1.2.3.4:8080",
            auto_start=False,
        )
        self.assertIn("pt118", self.manager.instances)
        self.assertEqual(len(self.manager.instances), 2)

        # Verifica isolamento de instâncias e credenciais
        self.assertEqual(w1.account.world, "pt117")
        self.assertEqual(w1.account.sid, "sid_pt117")
        self.assertIsNone(w1.account.proxy)

        self.assertEqual(w2.account.world, "pt118")
        self.assertEqual(w2.account.sid, "sid_pt118")
        self.assertEqual(w2.account.proxy, "http://user:pass@1.2.3.4:8080")

        # Testa alternância de foco
        success = self.manager.set_active_world("pt118")
        self.assertTrue(success)
        self.assertEqual(self.manager.active_world, "pt118")

        # Consulta lista de mundos
        worlds_list = self.manager.list_worlds()
        self.assertEqual(len(worlds_list), 2)
        p118_info = next(w for w in worlds_list if w["world"] == "pt118")
        self.assertTrue(p118_info["is_focused"])

    @patch("engine.core.account.TribalAccount.init_session", new_callable=AsyncMock)
    async def test_pause_resume_and_unregister(self, mock_init):
        """Testa pausa, retoma e encerramento de um mundo."""
        await self.manager.register_world(
            world="pt117",
            sid="sid_pt117",
            auto_start=False,
        )

        inst = self.manager.get_instance("pt117")
        self.assertIsNotNone(inst)

        # Pausa e retoma
        self.manager.pause_world("pt117")
        self.assertTrue(inst.scheduler.is_paused)

        self.manager.resume_world("pt117")
        self.assertFalse(inst.scheduler.is_paused)

        # Encerramento / unregister
        removed = await self.manager.unregister_world("pt117")
        self.assertTrue(removed)
        self.assertNotIn("pt117", self.manager.instances)


if __name__ == "__main__":
    unittest.main()
