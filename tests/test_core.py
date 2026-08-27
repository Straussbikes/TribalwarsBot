"""
Suíte de Testes Unitários para o Core Engine do Tribal Wars Bot.
Cobre: modelos de dados, gerador de atrasos gaussianos, parsers HTML/game_data,
deteção de anti-bot e motor de prioridade do TaskScheduler.
"""

import asyncio
import sys
import time
import unittest

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from engine.core.exceptions import BotProtectionError, SessionExpiredError
from engine.core.models import PlayerData, Resources, Task, TaskPriority, VillageData
from engine.core.scheduler import TaskScheduler
from engine.utils.parsers import (
    extract_csrf_token,
    extract_game_data,
    extract_resources,
    extract_village_and_player,
    is_bot_protection_present,
    is_session_expired,
)
from engine.utils.timing import get_human_delay, get_click_jitter


class TestModels(unittest.TestCase):
    def test_resources_calculations(self):
        res = Resources(
            wood=1500,
            stone=800,
            iron=400,
            storage_max=2000,
            pop=120,
            pop_max=200,
        )
        self.assertEqual(res.free_pop, 80)
        self.assertFalse(res.is_storage_full)
        self.assertTrue(res.can_afford(wood=1000, stone=500, iron=200, pop=50))
        self.assertFalse(res.can_afford(wood=2000))
        self.assertFalse(res.can_afford(pop=90))

        # Teste de armazém cheio
        res.wood = 2000
        self.assertTrue(res.is_storage_full)


class TestTiming(unittest.TestCase):
    def test_gaussian_delay_boundaries(self):
        min_sec = 2.0
        max_sec = 5.0
        base_sec = 3.5
        std_dev = 0.8

        delays = [
            get_human_delay(base_sec, std_dev, min_sec, max_sec)
            for _ in range(500)
        ]

        for d in delays:
            self.assertGreaterEqual(d, min_sec)
            self.assertLessEqual(d, max_sec)

        mean_delay = sum(delays) / len(delays)
        # A média empírica deve estar próxima da base
        self.assertAlmostEqual(mean_delay, base_sec, delta=0.25)

    def test_click_jitter(self):
        for _ in range(100):
            jitter = get_click_jitter(min_ms=120, max_ms=380)
            self.assertGreaterEqual(jitter, 0.120)
            self.assertLessEqual(jitter, 0.380)


class TestParsers(unittest.TestCase):
    def setUp(self):
        self.sample_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script type="text/javascript">
                var game_data = {
                    "player": {"id": 998877, "name": "ComandanteTW", "points": 1450, "villages": 2},
                    "village": {"id": 12345, "name": "01 Aldeia Central", "coord": "450|550", "x": 450, "y": 550, "points": 1200, "wood": 1850, "stone": 1200, "iron": 950, "storage_max": 4000, "pop": 310, "pop_max": 650},
                    "csrf": "b8f9e2d1c0a4"
                };
            </script>
        </head>
        <body>
            <span id="wood">1850</span>
            <span id="stone">1200</span>
            <span id="iron">950</span>
            <span id="storage">4000</span>
        </body>
        </html>
        """

    def test_extract_game_data(self):
        data = extract_game_data(self.sample_html)
        self.assertIsNotNone(data)
        self.assertEqual(data["csrf"], "b8f9e2d1c0a4")
        self.assertEqual(data["player"]["name"], "ComandanteTW")
        self.assertEqual(data["village"]["id"], 12345)

    def test_extract_csrf_and_resources(self):
        data = extract_game_data(self.sample_html)
        csrf = extract_csrf_token(self.sample_html, data)
        self.assertEqual(csrf, "b8f9e2d1c0a4")

        res = extract_resources(self.sample_html, data)
        self.assertEqual(res.wood, 1850)
        self.assertEqual(res.stone, 1200)
        self.assertEqual(res.iron, 950)
        self.assertEqual(res.storage_max, 4000)
        self.assertEqual(res.pop, 310)
        self.assertEqual(res.pop_max, 650)
        self.assertEqual(res.free_pop, 340)

    def test_anti_bot_detection(self):
        bot_protect_html = """
        <div id="bot_protect">
            <h3>Proteção contra bots</h3>
            <p>Por favor, resolve o captcha para continuar a jogar.</p>
            <input type="hidden" name="bot_check" value="1" />
        </div>
        """
        self.assertTrue(is_bot_protection_present(bot_protect_html))
        self.assertFalse(is_bot_protection_present(self.sample_html))

    def test_session_expired_detection(self):
        login_html = """
        <form id="login_form" action="/login.php" method="post">
            <input type="text" name="user" />
            <input type="password" name="password" />
        </form>
        """
        self.assertTrue(is_session_expired(login_html))
        self.assertTrue(is_session_expired("", current_url="https://pt117.tribalwars.com.pt/game.php?screen=welcome"))
        self.assertFalse(is_session_expired(self.sample_html))


class TestScheduler(unittest.IsolatedAsyncioTestCase):
    async def test_priority_queue_order(self):
        scheduler = TaskScheduler("TestScheduler")
        scheduler.start()

        execution_log = []

        async def action_farm():
            execution_log.append("farm")

        async def action_alert():
            execution_log.append("alert")

        async def action_build():
            execution_log.append("build")

        # Adiciona em ordem invertida de prioridade
        scheduler.schedule("Build Task", TaskPriority.BUILD, action_build)
        scheduler.schedule("Farm Task", TaskPriority.FARM, action_farm)
        scheduler.schedule("Emergency Alert", TaskPriority.ALERT, action_alert)

        # Aguarda execução das tarefas
        await asyncio.sleep(0.3)
        await scheduler.stop()

        # ALERT (0) deve executar primeiro, seguido por FARM (20), e depois BUILD (40)
        self.assertEqual(execution_log, ["alert", "farm", "build"])

    async def test_bot_protection_pause(self):
        scheduler = TaskScheduler("TestBotScheduler")
        bot_alert_triggered = False

        async def on_bot_alert(err: BotProtectionError):
            nonlocal bot_alert_triggered
            bot_alert_triggered = True

        scheduler.on_bot_protection(on_bot_alert)
        scheduler.start()

        async def malicious_action():
            raise BotProtectionError("Captcha acionado!")

        scheduler.schedule("Check Action", TaskPriority.FARM, malicious_action)

        # Aguarda a tarefa falhar com BotProtectionError
        await asyncio.sleep(0.2)

        # O scheduler deve estar pausado automaticamente e o alerta acionado
        self.assertTrue(scheduler.is_paused)
        self.assertTrue(bot_alert_triggered)

        await scheduler.stop()


class TestTribalAccount(unittest.IsolatedAsyncioTestCase):
    async def test_account_state_and_inspection(self):
        from engine.core.account import TribalAccount
        from curl_cffi.requests import Response

        account = TribalAccount(world="pt117", sid="test_sid_12345")
        await account.init_session()

        sample_html = """
        <script>
            var game_data = {
                "player": {"id": 100, "name": "General"},
                "village": {"id": 200, "name": "Vila Forte", "wood": 500, "stone": 600, "iron": 700, "storage_max": 2000, "pop": 50, "pop_max": 100},
                "csrf": "abc123csrf"
            };
        </script>
        """

        account._update_state_from_html(sample_html)
        self.assertEqual(account.csrf_token, "abc123csrf")
        self.assertEqual(account.current_village_id, 200)
        self.assertEqual(account.resources.wood, 500)
        self.assertEqual(account.resources.stone, 600)
        self.assertEqual(account.resources.iron, 700)
        self.assertEqual(account.resources.free_pop, 50)
        self.assertEqual(account.player.name, "General")

        # Teste de inspeção de erro anti-bot
        fake_response = Response()
        fake_response.status_code = 200
        bot_html = '<div id="bot_protect">Captcha</div>'

        with self.assertRaises(BotProtectionError):
            account._inspect_response(fake_response, bot_html)

        # Teste de rate limit (429)
        fake_429 = Response()
        fake_429.status_code = 429
        from engine.core.exceptions import RateLimitError
        with self.assertRaises(RateLimitError):
            account._inspect_response(fake_429, "<html>Rate limit</html>")

        await account.close()


if __name__ == "__main__":
    unittest.main()
