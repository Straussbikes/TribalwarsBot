"""
Testes Unitários Dedicados: Distinção entre Tropas na Aldeia vs. Tropas da Aldeia no Recrutamento
Valida que tropas em ataque/farm/apoio fora da aldeia não causam recrutamento duplicado
e que apoios recebidos de terceiros não impedem o recrutamento do exército próprio da aldeia.
"""

import unittest
from unittest.mock import AsyncMock

from engine.actions.place import PlaceManager, PlaceState, UnitsCount
from engine.actions.recruitment import RecruitmentManager, RecruitmentState
from engine.core.account import TribalAccount
from engine.core.models import Resources, VillageData
from engine.utils.parsers import parse_place_units_screen, parse_recruitment_page


# HTML realístico de quartel com a coluna oficial 'Na aldeia / no total' (0/50 lanças, 10/20 espadas, 30/30 machados)
BARRACKS_HTML_WITH_OWN_TROOPS = """
<!DOCTYPE html>
<html>
<body>
    <form id="train_form" action="/game.php?village=12345&amp;screen=barracks&amp;action=train&amp;h=csrf_abc" method="post">
        <!-- Lanceiro: 0 na aldeia, 50 no total (estão fora a farmar) -->
        <tr id="unit_spear">
            <td><a href="#">Lanceiro</a></td>
            <td>0/50</td>
            <td><span class="cost wood">50</span> <span class="cost stone">30</span> <span class="cost iron">10</span></td>
            <td>0:02:15</td>
            <td><a id="spear_0_a" href="#" class="unit_link">(35)</a><input id="spear_0" name="spear" type="text" data-max="35" /></td>
        </tr>

        <!-- Espadachim: 10 na aldeia, 20 no total -->
        <tr id="unit_sword">
            <td><a href="#">Espadachim</a></td>
            <td>10/20</td>
            <td><span class="cost wood">30</span> <span class="cost stone">30</span> <span class="cost iron">70</span></td>
            <td>0:03:00</td>
            <td><a id="sword_0_a" href="#" class="unit_link">(20)</a><input id="sword_0" name="sword" type="text" data-max="20" /></td>
        </tr>

        <!-- Viking: 0 na aldeia, 0 no total -->
        <tr id="unit_axe">
            <td><a href="#">Viking</a></td>
            <td>0/0</td>
            <td><span class="cost wood">60</span> <span class="cost stone">30</span> <span class="cost iron">40</span></td>
            <td>0:02:40</td>
            <td><a id="axe_0_a" href="#" class="unit_link">(50)</a><input id="axe_0" name="axe" type="text" data-max="50" /></td>
        </tr>
    </form>
</body>
</html>
"""

# HTML realístico da Praça de Reunião no modo Tropas (screen=place&mode=units)
SAMPLE_PLACE_MODE_UNITS_HTML = """
<!DOCTYPE html>
<html>
<body>
    <table class="vis">
        <tr>
            <th>Tropas</th>
            <th><img src="/graphic/unit/unit_spear.png"></th>
            <th><img src="/graphic/unit/unit_sword.png"></th>
            <th><img src="/graphic/unit/unit_axe.png"></th>
            <th><img src="/graphic/unit/unit_spy.png"></th>
            <th><img src="/graphic/unit/unit_light.png"></th>
            <th><img src="/graphic/unit/unit_heavy.png"></th>
            <th><img src="/graphic/unit/unit_ram.png"></th>
            <th><img src="/graphic/unit/unit_catapult.png"></th>
            <th><img src="/graphic/unit/unit_snob.png"></th>
        </tr>
        <tr>
            <td>Daqui</td>
            <td>5</td>
            <td>20</td>
            <td>0</td>
            <td>2</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
        </tr>
        <tr>
            <td>Noutras aldeias</td>
            <td>15</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
        </tr>
        <tr>
            <td>A caminho</td>
            <td>30</td>
            <td>0</td>
            <td>0</td>
            <td>8</td>
            <td>50</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
        </tr>
        <tr>
            <td>No total</td>
            <td>50</td>
            <td>20</td>
            <td>0</td>
            <td>10</td>
            <td>50</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
        </tr>
        <tr>
            <td>Apoio nesta aldeia</td>
            <td>200</td>
            <td>300</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
            <td>0</td>
        </tr>
    </table>
</body>
</html>
"""


class TestRecruitmentOwnTroops(unittest.IsolatedAsyncioTestCase):
    def test_parse_recruitment_page_extracts_own_and_in_village_counts(self):
        """Valida que parse_recruitment_page extrai corretamente X/Y (na aldeia / total)."""
        data = parse_recruitment_page(BARRACKS_HTML_WITH_OWN_TROOPS)

        # Lanças: 0 na aldeia, 50 no total
        self.assertEqual(data["own_units"]["spear"], 50)
        self.assertEqual(data["in_village_units"]["spear"], 0)
        self.assertEqual(data["unit_counts"]["spear"]["total"], 50)
        self.assertEqual(data["unit_counts"]["spear"]["in_village"], 0)

        # Espadas: 10 na aldeia, 20 no total
        self.assertEqual(data["own_units"]["sword"], 20)
        self.assertEqual(data["in_village_units"]["sword"], 10)

        # Machados: 0 na aldeia, 0 no total
        self.assertEqual(data["own_units"]["axe"], 0)
        self.assertEqual(data["in_village_units"]["axe"], 0)

    def test_parse_place_units_screen(self):
        """Valida a extração da tabela matricial de tropas em screen=place&mode=units."""
        matrix = parse_place_units_screen(SAMPLE_PLACE_MODE_UNITS_HTML)

        # Daqui (in_village)
        self.assertEqual(matrix["in_village"]["spear"], 5)
        self.assertEqual(matrix["in_village"]["sword"], 20)

        # Noutras aldeias (outside)
        self.assertEqual(matrix["outside"]["spear"], 15)

        # A caminho (in_transit)
        self.assertEqual(matrix["in_transit"]["spear"], 30)
        self.assertEqual(matrix["in_transit"]["light"], 50)

        # No total (soma de próprias = 5 + 15 + 30 = 50 lanças)
        self.assertEqual(matrix["total"]["spear"], 50)
        self.assertEqual(matrix["total"]["sword"], 20)
        self.assertEqual(matrix["total"]["light"], 50)

        # Apoio de outras aldeias presentes nesta aldeia
        self.assertEqual(matrix["support_in_village"]["spear"], 200)
        self.assertEqual(matrix["support_in_village"]["sword"], 300)

    async def test_recruitment_cycle_does_not_overrecruit_when_spears_are_attacking_outside(self):
        """
        Cenário Crítico Reportado:
        A aldeia tem 50 lanças da aldeia (todas fora em ataque de farm, logo 0 na aldeia).
        A meta do modelo é 50 lanças.
        O bot NÃO deve recrutar lanças adicionais porque a meta da aldeia já está 100% atingida.
        """
        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345

        # Aldeia com bastante recursos e população
        village = VillageData(
            id=12345,
            name="Aldeia Teste",
            x=450,
            y=550,
            resources=Resources(wood=5000, stone=5000, iron=5000, storage_max=10000, pop=50, pop_max=200),
            buildings={"main": 10, "barracks": 5, "stable": 0, "garage": 0, "smith": 5},
        )
        account.refresh_state = AsyncMock(return_value=village)
        account.villages[12345] = village

        manager = RecruitmentManager()

        # Praça de Reunião reporta 0 lanças na aldeia (porque estão todas fora em ataque de farm!)
        manager.place_manager.get_state = AsyncMock(return_value=PlaceState(
            village_id=12345,
            units=UnitsCount(spear=0, sword=10, axe=0),
        ))

        # Quartel reporta: Lanceiro 0/50 (0 na aldeia / 50 no total), Espada 10/20, Viking 0/0
        account.get_screen = AsyncMock(return_value=BARRACKS_HTML_WITH_OWN_TROOPS)
        account.post_action = AsyncMock(return_value=BARRACKS_HTML_WITH_OWN_TROOPS)

        # Metas:
        # spear: meta 50. Como a aldeia já tem 50 no total, faltam 0 -> NÃO RECRUTAR
        # sword: meta 30. A aldeia tem 20 no total, faltam 10 -> Treinar 10
        # axe: meta 25. A aldeia tem 0 no total, faltam 25 -> Treinar 10 (batch_size)
        targets = {"spear": 50, "sword": 30, "axe": 25}
        batch_sizes = {"spear": 10, "sword": 10, "axe": 10}

        recruited = await manager.run_recruitment_cycle(
            account=account,
            targets=targets,
            batch_sizes=batch_sizes,
            min_free_pop=10,
            max_queue_elements=5,
        )

        # Validação estrita: SPEAR NÃO FOI RECRUTADO!
        self.assertNotIn("spear", recruited, "Erro: Spear não devia ser recrutado porque a aldeia já possui 50 lanças!")
        self.assertEqual(recruited.get("sword"), 10)
        self.assertEqual(recruited.get("axe"), 10)

        # Validação da submissão HTTP
        account.post_action.assert_called_once()
        post_data = account.post_action.call_args.kwargs["data"]
        self.assertNotIn("spear", post_data)
        self.assertEqual(post_data["sword"], "10")
        self.assertEqual(post_data["axe"], "10")

    async def test_recruitment_cycle_with_external_support_does_not_block_own_recruitment(self):
        """
        Cenário Inverso:
        A aldeia tem 500 lanças de APOIO recebidas de terceiros na Praça de Reunião,
        mas a aldeia tem apenas 10 lanças próprias (10/10 no quartel).
        A meta é 50 lanças próprias da aldeia.
        O bot deve perceber que as tropas próprias da aldeia são apenas 10 e recrutar as 40 restantes.
        """
        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345

        village = VillageData(
            id=12345,
            name="Aldeia Defesa",
            x=450,
            y=550,
            resources=Resources(wood=5000, stone=5000, iron=5000, storage_max=10000, pop=50, pop_max=200),
            buildings={"main": 10, "barracks": 5},
        )
        account.refresh_state = AsyncMock(return_value=village)
        account.villages[12345] = village

        manager = RecruitmentManager()

        # Praça de Reunião mostra 500 lanças (devido ao apoio de aliados)
        manager.place_manager.get_state = AsyncMock(return_value=PlaceState(
            village_id=12345,
            units=UnitsCount(spear=500, sword=0, axe=0),
        ))

        # HTML do quartel mostrando que a aldeia só tem 10/10 lanças próprias
        html_quartel_com_poucas_proprias = """
        <form id="train_form" action="/game.php?village=12345&amp;screen=barracks&amp;action=train" method="post">
            <tr id="unit_spear">
                <td>Lanceiro</td>
                <td>10/10</td>
                <td><input id="spear_0" name="spear" type="text" data-max="30" /></td>
            </tr>
        </form>
        """
        account.get_screen = AsyncMock(return_value=html_quartel_com_poucas_proprias)
        account.post_action = AsyncMock(return_value=html_quartel_com_poucas_proprias)

        targets = {"spear": 50}
        batch_sizes = {"spear": 15}

        recruited = await manager.run_recruitment_cycle(
            account=account,
            targets=targets,
            batch_sizes=batch_sizes,
            min_free_pop=10,
        )

        # Como tem 10 próprias e a meta é 50, faltam 40. Com batch de 15, deve recrutar 15!
        self.assertEqual(recruited.get("spear"), 15)
        account.post_action.assert_called_once()
        self.assertEqual(account.post_action.call_args.kwargs["data"]["spear"], "15")

    async def test_place_manager_get_village_units_overview(self):
        """Valida que PlaceManager.get_village_units_overview atualiza own_troops em VillageData."""
        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345
        v = VillageData(id=12345, name="Aldeia")
        account.villages[12345] = v

        account.get_screen = AsyncMock(return_value=SAMPLE_PLACE_MODE_UNITS_HTML)

        place_mgr = PlaceManager()
        overview = await place_mgr.get_village_units_overview(account, village_id=12345)

        self.assertEqual(overview["total"]["spear"], 50)
        self.assertEqual(v.own_troops["spear"], 50)
        self.assertEqual(v.troops_in_village["spear"], 5)

    def test_parse_stable_html_with_sprites_and_class_rows(self):
        """
        Valida que o estábulo com HTML realístico (classes row_a/row_b, sprites CSS,
        e ausência de id="unit_light") extrai com perfeição 2 CL na aldeia / 15 totais pertencentes.
        """
        stable_html = """
        <form id="train_form" action="/game.php?village=12345&amp;screen=stable&amp;action=train" method="post">
            <table class="vis">
                <tr>
                    <th>Unidade</th>
                    <th>Na aldeia / no total</th>
                    <th>Custos</th>
                    <th>Tempo</th>
                    <th>Recrutar</th>
                </tr>
                <tr class="row_a">
                    <td>
                        <a href="#" onclick="return UnitPopup.open('spy')">
                            <span class="unit_sprite spy"></span> Batedor
                        </a>
                    </td>
                    <td>1/5</td>
                    <td><span class="cost wood">50</span> <span class="cost stone">50</span> <span class="cost iron">20</span></td>
                    <td>0:01:30</td>
                    <td>
                        <input id="spy_0" name="spy" type="text" class="recruit_unit" data-max="20" />
                        <a id="spy_0_a" href="javascript:set_max('spy', 20)">(20)</a>
                    </td>
                </tr>
                <tr class="row_b">
                    <td>
                        <a href="#" onclick="return UnitPopup.open('light')">
                            <span class="unit_sprite unit_sprite_smaller light"></span> Cavalaria leve
                        </a>
                    </td>
                    <td>2/15</td>
                    <td><span class="cost wood">125</span> <span class="cost stone">100</span> <span class="cost iron">250</span></td>
                    <td>0:06:40</td>
                    <td>
                        <input id="light_0" name="light" type="text" class="recruit_unit" data-max="30" />
                        <a id="light_0_a" href="javascript:set_max('light', 30)">(30)</a>
                    </td>
                </tr>
                <tr class="row_a">
                    <td>
                        <a href="#" onclick="return UnitPopup.open('heavy')">
                            <span class="unit_sprite heavy"></span> Cavalaria pesada
                        </a>
                    </td>
                    <td colspan="4" class="inactive">A unidade não foi pesquisada. (<a href="#">Ferreiro</a>)</td>
                </tr>
            </table>
        </form>
        """
        data = parse_recruitment_page(stable_html)

        # Cavalaria Leve: 2 na aldeia, 15 no total pertencente
        self.assertEqual(data["own_units"].get("light"), 15)
        self.assertEqual(data["in_village_units"].get("light"), 2)
        self.assertEqual(data["unit_counts"]["light"]["in_village"], 2)
        self.assertEqual(data["unit_counts"]["light"]["total"], 15)
        self.assertEqual(data["available_units"].get("light"), 30)

        # Batedor: 1 na aldeia, 5 no total pertencente
        self.assertEqual(data["own_units"].get("spy"), 5)
        self.assertEqual(data["in_village_units"].get("spy"), 1)
        self.assertEqual(data["available_units"].get("spy"), 20)

        # Cavalaria pesada: não pesquisada (sem input ativo)
        self.assertNotIn("heavy", data["available_units"])

    async def test_stable_recruitment_cycle_respects_total_belonging_cl(self):
        """
        Valida que tendo 2 CL na aldeia e 15 pertencentes no total (obtidos do estábulo),
        se a meta for 15 CL, não recruta nada (needed = 0).
        Se a meta for 20 CL, recruta apenas 5 (20 - 15 = 5), e NÃO 18 (20 - 2).
        """
        stable_html = """
        <form id="train_form" action="/game.php?village=12345&amp;screen=stable&amp;action=train" method="post">
            <tr class="row_b">
                <td><span class="unit_sprite light"></span> Cavalaria leve</td>
                <td>2/15</td>
                <td><input id="light_0" name="light" type="text" class="recruit_unit" data-max="30" /></td>
            </tr>
        </form>
        """
        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345
        village = VillageData(
            id=12345,
            name="Aldeia CL",
            resources=Resources(wood=10000, stone=10000, iron=10000, pop=100, pop_max=1000),
            troops={"light": 2},  # Só 2 estão na aldeia!
            buildings={"stable": 3, "smith": 3},
        )
        account.villages[12345] = village

        manager = RecruitmentManager()
        account.get_screen = AsyncMock(return_value=stable_html)
        account.post_action = AsyncMock(return_value=stable_html)

        # Caso 1: Meta = 15 CL. Aldeia tem 15 pertencentes (2 em casa, 13 a farmar).
        recruited = await manager.run_recruitment_cycle(
            account=account,
            targets={"light": 15},
            batch_sizes={"light": 10},
            min_free_pop=10,
        )
        # Nenhuma CL deve ser recrutada!
        self.assertEqual(recruited.get("light", 0), 0)
        account.post_action.assert_not_called()

        # Caso 2: Meta = 20 CL. Faltam exatamente 5 (20 - 15 = 5).
        recruited_2 = await manager.run_recruitment_cycle(
            account=account,
            targets={"light": 20},
            batch_sizes={"light": 10},
            min_free_pop=10,
        )
        self.assertEqual(recruited_2.get("light"), 5)
        account.post_action.assert_called_once()
        self.assertEqual(account.post_action.call_args.kwargs["data"]["light"], "5")


if __name__ == "__main__":
    unittest.main()

