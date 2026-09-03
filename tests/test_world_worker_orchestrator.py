"""
Testes Unitários do WorldWorkerOrchestrator e Isolamento de Workers.
Validação de execução concorrente multi-mundo sob a mesma conta, tratamento isolado de rate limits
e paragem/ativação dinâmica de mundos.
"""

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock

from engine.config.settings import BotConfig
from engine.core.account import TribalAccount
from engine.core.world_worker_orchestrator import WorldWorker, WorldWorkerOrchestrator
from engine.storage.cloud_db import CloudDatabase


class TestWorldWorkerOrchestrator(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = CloudDatabase(database_url="sqlite+aiosqlite:///:memory:")
        await self.db.init_db()
        self.orchestrator = WorldWorkerOrchestrator(db=self.db)

    async def asyncTearDown(self):
        await self.orchestrator.stop_all_workers()
        await self.db.close()

    async def test_parallel_workers_execution(self):
        # Regista 2 workers para mundos diferentes (pt114 e pt117)
        w1 = await self.orchestrator.register_and_start_worker(
            world_code="pt114",
            sid="sid_pt114",
            is_active=True,
        )
        w2 = await self.orchestrator.register_and_start_worker(
            world_code="pt117",
            sid="sid_pt117",
            is_active=True,
        )

        self.assertEqual(len(self.orchestrator.workers), 2)
        self.assertTrue(w1.scheduler.is_running)
        self.assertTrue(w2.scheduler.is_running)

        # Status do orchestrator reflete ambos
        status = self.orchestrator.get_status()
        self.assertEqual(status["total_workers"], 2)
        self.assertIn("pt114", status["workers"])
        self.assertIn("pt117", status["workers"])

    async def test_rate_limit_isolation_between_worlds(self):
        w1 = await self.orchestrator.register_and_start_worker(
            world_code="pt114",
            sid="sid_pt114",
            is_active=True,
        )
        w2 = await self.orchestrator.register_and_start_worker(
            world_code="pt117",
            sid="sid_pt117",
            is_active=True,
        )

        # Dispara rate limit apenas no mundo pt114
        w1.handle_rate_limit(retry_after=45.0)

        # pt114 deve estar marcado com rate limit
        self.assertTrue(w1.is_rate_limited)
        self.assertGreater(w1.rate_limit_until, time.time())

        # pt117 NÃO pode ser afetado pelo rate limit do pt114!
        self.assertFalse(w2.is_rate_limited)
        self.assertEqual(w2.rate_limit_until, 0.0)

    async def test_toggle_world_worker(self):
        w1 = await self.orchestrator.register_and_start_worker(
            world_code="pt114",
            sid="sid_pt114",
            is_active=True,
        )
        self.assertTrue(w1.is_active)
        self.assertTrue(w1.scheduler.is_running)

        # Pausa o worker do pt114
        toggled_off = await self.orchestrator.toggle_world_worker("pt114", is_active=False)
        self.assertTrue(toggled_off)
        self.assertFalse(w1.is_active)
        self.assertFalse(w1.scheduler.is_running)

        # Retoma o worker
        toggled_on = await self.orchestrator.toggle_world_worker("pt114", is_active=True)
        self.assertTrue(toggled_on)
        self.assertTrue(w1.is_active)
        self.assertTrue(w1.scheduler.is_running)
