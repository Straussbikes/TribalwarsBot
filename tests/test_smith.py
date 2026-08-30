"""
Unit tests for SmithManager (screen=smith)
Valida parsing do Ferreiro, tecnologias militares, ordens ativas na fila e auto-pesquisa.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from engine.actions.smith import (
    ResearchOrder,
    SmithManager,
    SmithState,
    SmithUnitInfo,
    parse_smith_page,
)
from engine.core.account import TribalAccount
from engine.core.models import VillageData


SAMPLE_SMITH_HTML = """
<!DOCTYPE html>
<html>
<body>
<table id="smith_overview">
  <tr id="unit_smith_spear">
    <td>Lanceiro</td>
    <td>Nível 1 (Pesquisado)</td>
  </tr>
  <tr id="unit_smith_sword">
    <td>Espadachim</td>
    <td>Nível 1 (Pesquisado)</td>
  </tr>
  <tr id="unit_smith_axe">
    <td>Bárbaro / Viking</td>
    <td><span class="icon header wood"></span> 700 <span class="icon header stone"></span> 840 <span class="icon header iron"></span> 820</td>
    <td><a class="btn btn-default" href="/game.php?village=12345&screen=smith&action=research&id=axe&h=mock_csrf">Pesquisar</a></td>
  </tr>
  <tr id="unit_smith_spy">
    <td>Espião / Batedor</td>
    <td>Requisitos não atingidos (Estábulo Nível 1)</td>
  </tr>
</table>

<table id="research_queue" class="lit researchqueue_main">
  <tr>
    <td>A pesquisar Cavalaria Leve</td>
    <td><span class="timer">0:14:22</span></td>
    <td><a href="/game.php?village=12345&screen=smith&action=cancel&id=light&h=mock_csrf">Cancelar</a></td>
  </tr>
</table>
</body>
</html>
"""


class TestSmithParsers(unittest.TestCase):
    def test_parse_smith_page(self):
        data = parse_smith_page(SAMPLE_SMITH_HTML)
        units = data["units"]
        queue = data["queue"]

        # 1. Fila ativa
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["unit"], "light")
        self.assertEqual(queue[0]["timer_str"], "0:14:22")
        self.assertEqual(queue[0]["timer_seconds"], 14 * 60 + 22)

        # 2. Unidades
        self.assertEqual(units["spear"]["status"], "researched")
        self.assertEqual(units["sword"]["status"], "researched")

        self.assertEqual(units["axe"]["status"], "can_research")
        self.assertIn("action=research&id=axe", units["axe"]["research_url"])
        self.assertEqual(units["axe"]["wood"], 700)
        self.assertEqual(units["axe"]["stone"], 840)
        self.assertEqual(units["axe"]["iron"], 820)

        self.assertEqual(units["light"]["status"], "researching")
        self.assertEqual(units["spy"]["status"], "unavailable")


    def test_parse_smith_page_insufficient_resources_not_falsely_researched(self):
        # Quando faltam recursos, o botão é desabilitado (<span class="btn-disabled">)
        html = """
        <table>
          <tr id="unit_smith_axe">
            <td>Bárbaro</td>
            <td><span class="icon header wood"></span> 700 <span class="icon header stone"></span> 840 <span class="icon header iron"></span> 820</td>
            <td><span class="btn btn-default btn-disabled">Recursos insuficientes</span></td>
          </tr>
        </table>
        """
        data = parse_smith_page(html)
        axe_info = data["units"]["axe"]
        # Não deve ser marcado falsamente como 'researched'!
        self.assertFalse(axe_info["status"] == "researched")
        self.assertEqual(axe_info["status"], "can_research")
        self.assertEqual(axe_info["wood"], 700)
        self.assertEqual(axe_info["stone"], 840)
        self.assertEqual(axe_info["iron"], 820)

    def test_parse_smith_page_mobile_layout_without_ids(self):
        # Layout mobile do TW sem id no <tr>, apenas com imagem e nome
        html = """
        <table class="vis">
          <tr>
            <td><img src="https://dspt.innogamescdn.com/asset/123/graphic/unit/unit_axe.png"> Viking</td>
            <td><span class="cost_wood"></span> 700 <span class="cost_stone"></span> 840 <span class="cost_iron"></span> 820</td>
            <td><a class="btn btn-default" href="/game.php?village=6810&screen=smith&action=research&id=axe&h=token123">Pesquisar</a></td>
          </tr>
        </table>
        """
        data = parse_smith_page(html)
        axe_info = data["units"]["axe"]
        self.assertEqual(axe_info["status"], "can_research")
        self.assertIsNotNone(axe_info["research_url"])


class TestSmithAsyncActions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.account = MagicMock(spec=TribalAccount)
        self.account.world = "pt117"
        self.account.current_village_id = 12345
        self.account.csrf_token = "mock_csrf"
        self.account.host = "pt117.tribalwars.com.pt"
        self.account.villages = {
            12345: VillageData(
                id=12345,
                name="Aldeia Principal",
                x=500,
                y=500,
                buildings={"main": 10, "barracks": 5, "smith": 5},
            )
        }
        self.manager = SmithManager()

    async def test_get_smith_state(self):
        self.account.get_screen = AsyncMock(return_value=SAMPLE_SMITH_HTML)

        state = await self.manager.get_smith_state(self.account, village_id=12345)
        self.assertEqual(state.village_id, 12345)
        self.assertEqual(state.smith_level, 5)
        self.assertTrue(state.is_researching_any)
        self.assertEqual(state.units["axe"].can_research, True)
        self.assertEqual(state.units["spear"].is_researched, True)

    async def test_research_unit(self):
        self.account.get_screen = AsyncMock(return_value="<html>OK</html>")

        success = await self.manager.research_unit(self.account, "axe", village_id=12345)
        self.assertTrue(success)
        self.account.get_screen.assert_called_once()
        call_kwargs = self.account.get_screen.call_args[1]
        self.assertEqual(call_kwargs["screen"], "smith")
        self.assertEqual(call_kwargs["extra_params"]["action"], "research")
        self.assertEqual(call_kwargs["extra_params"]["id"], "axe")

    async def test_auto_research_needed_units(self):
        # HTML onde axe está pronto para pesquisar e fila está vazia
        html_idle_smith = """
        <table id="smith_overview">
          <tr id="unit_smith_axe">
            <td>Bárbaro</td>
            <td><a class="btn" href="/game.php?action=research&id=axe&h=mock_csrf">Pesquisar</a></td>
          </tr>
        </table>
        """
        self.account.get_screen = AsyncMock(return_value=html_idle_smith)

        researched = await self.manager.auto_research_needed_units(
            self.account,
            village_id=12345,
            needed_units=["axe", "light"],
        )

        self.assertIn("axe", researched)
        self.assertEqual(len(researched), 1)


if __name__ == "__main__":
    unittest.main()

