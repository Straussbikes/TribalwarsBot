"""
Testes Unitários Automatizados para a Secção 2.7:
Mercado, Leitura de Mercadores e Algoritmo de Balanceamento de Recursos (screen=market).
"""

import asyncio
from typing import Any, Dict, Optional
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from engine.actions.market import (
    MarketManager,
    MarketOffer,
    MarketState,
    MerchantMovement,
    TransferOrder,
)
from engine.config.settings import BotConfig, MarketConfig
from engine.core.account import TribalAccount
from engine.core.models import Resources, VillageData
from engine.utils.parsers import parse_market_offers, parse_market_screen


class TestMarketParsers(unittest.TestCase):
    """Testes dos parsers de HTML do Mercado."""

    def test_parse_market_screen_merchants(self):
        html = """
        <div id="content_value">
            <table class="vis">
                <tr>
                    <th colspan="3">
                        Mercadores: <span id="market_merchant_available_count">7</span>/<span id="market_merchant_total_count">10</span>
                    </th>
                </tr>
            </table>
        </div>
        """
        data = parse_market_screen(html)
        self.assertEqual(data["merchants_available"], 7)
        self.assertEqual(data["merchants_total"], 10)

    def test_parse_market_screen_merchants_text_fallback(self):
        html = """
        <div id="content_value">
            <p>Mercadores: 5 / 15</p>
        </div>
        """
        data = parse_market_screen(html)
        self.assertEqual(data["merchants_available"], 5)
        self.assertEqual(data["merchants_total"], 15)

    def test_parse_market_screen_transports(self):
        html = """
        <table class="vis">
            <tr><th>Direção</th><th>Aldeia</th><th>Recursos</th><th>Chegada</th></tr>
            <tr>
                <td>Transporte para</td>
                <td><a href="/game.php?village=6662&screen=info_village&id=7777">Aldeia Alpha (450|550)</a></td>
                <td><span class="icon header wood"></span> 2.000 <span class="icon header stone"></span> 1.000 <span class="icon header iron"></span> 0</td>
                <td><span class="timer">0:14:22</span></td>
            </tr>
            <tr>
                <td>Transporte de</td>
                <td><a href="/game.php?village=6662&screen=info_village&id=8888">Aldeia Beta (460|560)</a></td>
                <td><span class="icon header wood"></span> 0 <span class="icon header stone"></span> 0 <span class="icon header iron"></span> 3.000</td>
                <td>hoje às 04:10:15</td>
            </tr>
        </table>
        """
        data = parse_market_screen(html)
        transports = data["transports"]
        self.assertEqual(len(transports), 2)

        # Primeiro transporte (outgoing)
        t1 = transports[0]
        self.assertEqual(t1["direction"], "outgoing")
        self.assertEqual(t1["village_id"], 7777)
        self.assertEqual(t1["coords"], (450, 550))
        self.assertEqual(t1["wood"], 2000)
        self.assertEqual(t1["stone"], 1000)
        self.assertEqual(t1["iron"], 0)
        self.assertEqual(t1["total_resources"], 3000)
        self.assertEqual(t1["merchants_count"], 3)
        self.assertEqual(t1["arrival_time"], "0:14:22")

        # Segundo transporte (incoming)
        t2 = transports[1]
        self.assertEqual(t2["direction"], "incoming")
        self.assertEqual(t2["village_id"], 8888)
        self.assertEqual(t2["coords"], (460, 560))
        self.assertEqual(t2["wood"], 0)
        self.assertEqual(t2["stone"], 0)
        self.assertEqual(t2["iron"], 3000)
        self.assertEqual(t2["total_resources"], 3000)
        self.assertEqual(t2["merchants_count"], 3)

    def test_parse_market_screen_empty(self):
        data = parse_market_screen("")
        self.assertEqual(data["merchants_available"], 0)
        self.assertEqual(data["merchants_total"], 0)
        self.assertEqual(data["transports"], [])

    def test_parse_market_offers(self):
        html = """
        <table class="vis">
            <tr><th>Oferta</th><th>Procura</th><th>Rácio</th><th>Disponíveis</th></tr>
            <tr>
                <td><input type="checkbox" name="id_12345" /> <span class="icon header wood"></span> 1.000</td>
                <td><span class="icon header iron"></span> 1.000</td>
                <td>1.00</td>
                <td>3x</td>
            </tr>
            <tr>
                <td><input type="checkbox" name="id_67890" /> <span class="icon header stone"></span> 2.000</td>
                <td><span class="icon header wood"></span> 1.000</td>
                <td>0.50</td>
                <td>1x</td>
            </tr>
        </table>
        """
        offers = parse_market_offers(html)
        self.assertEqual(len(offers), 2)
        self.assertEqual(offers[0]["id"], 12345)
        self.assertEqual(offers[0]["sell_res"], "wood")
        self.assertEqual(offers[0]["sell_amount"], 1000)
        self.assertEqual(offers[0]["buy_res"], "iron")
        self.assertEqual(offers[0]["buy_amount"], 1000)
        self.assertEqual(offers[0]["available_offers"], 3)

        self.assertEqual(offers[1]["id"], 67890)
        self.assertEqual(offers[1]["sell_res"], "stone")
        self.assertEqual(offers[1]["available_offers"], 1)


class TestMarketBalancingLogic(unittest.TestCase):
    """Testes matemáticos do algoritmo de balanceamento de recursos."""

    def setUp(self):
        self.manager = MarketManager()
        self.mock_account = MagicMock(spec=TribalAccount)
        self.mock_account.world = "pt117"
        self.mock_account.villages = {}

    def test_balancing_single_village_returns_empty(self):
        v1 = VillageData(
            id=1001,
            name="Aldeia Solo",
            x=500,
            y=500,
            resources=Resources(wood=20000, stone=20000, iron=20000, storage_max=40000),
        )
        self.mock_account.villages = {1001: v1}
        orders = self.manager.calculate_balancing_transfers(self.mock_account)
        self.assertEqual(orders, [])

    def test_balancing_donor_and_receiver(self):
        # Aldeia 1: Rica em Madeira e Pedra (excedente)
        v1 = VillageData(
            id=1001,
            name="Aldeia Doadora",
            x=500,
            y=500,
            resources=Resources(wood=35000, stone=30000, iron=5000, storage_max=40000),
        )
        # Aldeia 2: Pobre em Madeira e Pedra (défice)
        v2 = VillageData(
            id=1002,
            name="Aldeia Recetora",
            x=502,
            y=502,
            resources=Resources(wood=2000, stone=3000, iron=5000, storage_max=40000),
        )
        self.mock_account.villages = {1001: v1, 1002: v2}

        # Simula 20 mercadores disponíveis na doadora
        self.manager._states[1001] = MarketState(
            village_id=1001,
            merchants_available=20,
            merchants_total=20,
        )

        orders = self.manager.calculate_balancing_transfers(self.mock_account)
        self.assertTrue(len(orders) > 0)

        # Verifica se todas as transferências são quantizadas em múltiplos de 1.000
        for order in orders:
            self.assertEqual(order.source_village_id, 1001)
            self.assertEqual(order.target_village_id, 1002)
            self.assertTrue(order.total_resources % 1000 == 0)
            self.assertEqual(order.merchants_required, order.total_resources // 1000)

    def test_storage_overflow_prevention(self):
        # Aldeia 1 tem armazém quase cheio (risco de transbordamento)
        v1 = VillageData(
            id=1001,
            name="Aldeia Cheia",
            x=500,
            y=500,
            resources=Resources(wood=38000, stone=38000, iron=38000, storage_max=40000),
        )
        # Aldeia 2 tem espaço limitado (armazém 10.000 com 8.000 de recursos)
        v2 = VillageData(
            id=1002,
            name="Aldeia Pequena",
            x=505,
            y=505,
            resources=Resources(wood=1000, stone=1000, iron=1000, storage_max=5000),
        )
        self.mock_account.villages = {1001: v1, 1002: v2}

        self.manager._states[1001] = MarketState(
            village_id=1001,
            merchants_available=30,
            merchants_total=30,
        )

        orders = self.manager.calculate_balancing_transfers(self.mock_account)
        # Verifica que para a aldeia 2 não são enviadas quantidades que excedam a capacidade livre (5000 * 0.9 = 4500)
        for order in orders:
            if order.target_village_id == 1002:
                # O envio não deve ser superior ao espaço livre
                self.assertLessEqual(order.wood, 4000)
                self.assertLessEqual(order.stone, 4000)
                self.assertLessEqual(order.iron, 4000)

    def test_auto_trade_excess_resources(self):
        # Aldeia com grande desequilíbrio interno: 25.000 Madeira, mas só 1.000 Ferro
        v = VillageData(
            id=1001,
            name="Aldeia Desequilibrada",
            x=500,
            y=500,
            resources=Resources(wood=25000, stone=10000, iron=1000, storage_max=30000),
        )
        self.mock_account.villages = {1001: v}

        self.manager.get_market_state = AsyncMock(
            return_value=MarketState(village_id=1001, merchants_available=10, merchants_total=10)
        )
        self.manager.create_market_offer = AsyncMock(return_value=True)

        async def _run():
            return await self.manager.auto_trade_excess_resources(self.mock_account, 1001, ratio=1.0)

        offers_count = asyncio.run(_run())
        self.assertTrue(offers_count > 0)
        self.manager.create_market_offer.assert_called_once()
        # Garante que vendeu madeira e comprou ferro
        call_kwargs = self.manager.create_market_offer.call_args[1]
        self.assertEqual(call_kwargs["sell_res"], "wood")
        self.assertEqual(call_kwargs["buy_res"], "iron")


class TestMarketManagerAsync(unittest.IsolatedAsyncioTestCase):
    """Testes assíncronos de envio e ciclo de mercado."""

    async def test_get_market_state_caching(self):
        manager = MarketManager()
        mock_account = MagicMock(spec=TribalAccount)
        mock_account.world = "pt117"
        mock_account.current_village_id = 1001
        mock_account.get_screen = AsyncMock(return_value="""
            <span id="market_merchant_available_count">12</span>
            <span id="market_merchant_total_count">15</span>
        """)

        state = await manager.get_market_state(mock_account, village_id=1001)
        self.assertEqual(state.village_id, 1001)
        self.assertEqual(state.merchants_available, 12)
        self.assertEqual(state.merchants_total, 15)
        self.assertEqual(state.merchants_in_transit, 3)

    async def test_send_resources_validation_insufficient_merchants(self):
        manager = MarketManager()
        mock_account = MagicMock(spec=TribalAccount)
        mock_account.world = "pt117"

        v1 = VillageData(id=1001, name="Origem", x=500, y=500, resources=Resources(wood=5000, stone=5000, iron=5000, storage_max=10000))
        v2 = VillageData(id=1002, name="Destino", x=501, y=501, resources=Resources(wood=1000, stone=1000, iron=1000, storage_max=10000))
        mock_account.villages = {1001: v1, 1002: v2}

        # Apenas 1 mercador disponível (capacidade 1.000)
        manager._states[1001] = MarketState(village_id=1001, merchants_available=1, merchants_total=10)

        # Tenta enviar 3.000 recursos (necessita de 3 mercadores)
        success = await manager.send_resources(mock_account, 1001, 1002, wood=3000)
        self.assertFalse(success)

    async def test_send_resources_success(self):
        manager = MarketManager()
        mock_account = MagicMock(spec=TribalAccount)
        mock_account.world = "pt117"
        mock_account.post_action = AsyncMock(return_value="OK")

        v1 = VillageData(id=1001, name="Origem", x=500, y=500, resources=Resources(wood=10000, stone=10000, iron=10000, storage_max=20000))
        v2 = VillageData(id=1002, name="Destino", x=501, y=501, resources=Resources(wood=1000, stone=1000, iron=1000, storage_max=20000))
        mock_account.villages = {1001: v1, 1002: v2}

        manager._states[1001] = MarketState(village_id=1001, merchants_available=10, merchants_total=10)

        # Envia 2.000 Madeira e 1.000 Ferro (3 mercadores)
        success = await manager.send_resources(mock_account, 1001, 1002, wood=2000, stone=0, iron=1000)
        self.assertTrue(success)
        mock_account.post_action.assert_called_once()
        # Verifica se os recursos locais foram deduzidos
        self.assertEqual(v1.resources.wood, 8000)
        self.assertEqual(v1.resources.iron, 9000)
        # Verifica se os mercadores disponíveis foram atualizados
        self.assertEqual(manager._states[1001].merchants_available, 7)

    async def test_run_balancing_cycle(self):
        manager = MarketManager()
        mock_account = MagicMock(spec=TribalAccount)
        mock_account.world = "pt117"
        mock_account.get_screen = AsyncMock(return_value="""
            <span id="market_merchant_available_count">10</span>
            <span id="market_merchant_total_count">10</span>
        """)
        mock_account.post_action = AsyncMock(return_value="OK")

        v1 = VillageData(id=1001, name="Doadora", x=500, y=500, resources=Resources(wood=25000, stone=20000, iron=15000, storage_max=30000))
        v2 = VillageData(id=1002, name="Recetora", x=502, y=502, resources=Resources(wood=2000, stone=2000, iron=2000, storage_max=30000))
        mock_account.villages = {1001: v1, 1002: v2}

        res = await manager.run_balancing_cycle(mock_account)
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["total_orders"] > 0)
        self.assertEqual(res["failed"], 0)
        self.assertEqual(res["executed"], res["total_orders"])


class TestMarketApiRoutes(unittest.IsolatedAsyncioTestCase):
    """Testes dos endpoints Sidecar da API REST para o mercado."""

    async def test_routes_endpoints_with_mock_context(self):
        from engine.api.context import EngineContext
        from engine.api.routes import create_api_router
        from engine.api.auth import TokenVerifier

        mock_context = MagicMock(spec=EngineContext)
        mock_context.get_market_state = AsyncMock(return_value={
            "status": "success",
            "market": {
                "village_id": 6662,
                "merchants_available": 8,
                "merchants_total": 10,
                "merchants_in_transit": 2,
                "transports": [],
                "own_offers": [],
            }
        })
        mock_context.send_market_resources = AsyncMock(return_value={
            "status": "success",
            "message": "Recursos enviados!"
        })
        mock_context.get_resource_balancing_plan = MagicMock(return_value={
            "status": "success",
            "planned_orders": [],
            "total_orders": 0,
        })
        mock_context.trigger_resource_balancing = AsyncMock(return_value={
            "status": "success",
            "executed": 1,
            "failed": 0,
        })
        mock_context.create_market_offer = AsyncMock(return_value={
            "status": "success",
            "message": "Oferta criada!"
        })

        verifier = MagicMock(spec=TokenVerifier)
        verifier.verify = AsyncMock(return_value=True)

        router = create_api_router(mock_context, verifier)
        self.assertIsNotNone(router)

        # Testa invocações diretas das rotas registadas
        for route in router.routes:
            if getattr(route, "path", "") == "/api/market/state":
                resp = await route.endpoint(village_id=6662)
                self.assertEqual(resp["status"], "success")
            elif getattr(route, "path", "") == "/api/market/balance/plan":
                resp = route.endpoint()
                self.assertEqual(resp["status"], "success")
            elif getattr(route, "path", "") == "/api/market/balance/trigger":
                resp = await route.endpoint()
                self.assertEqual(resp["status"], "success")


if __name__ == "__main__":
    unittest.main()
