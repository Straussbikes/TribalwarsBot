"""
Suíte de Testes Unitários para o Módulo de Recrutamento Militar (Item 2.5).
Cobre: parsing do ecrã de treino (Quartel/Estábulo/Oficina), leitura da fila ativa,
cálculo de défice até às metas de exército, limites de lotes (batch sizes),
reserva de população livre da Fazenda e envio de formulário POST action=train.
"""

import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, patch

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from engine.actions.place import PlaceState, UnitsCount
from engine.actions.recruitment import (
    BUILDING_UNITS,
    UNIT_TO_BUILDING,
    RecruitmentManager,
    RecruitmentState,
    TrainingOrder,
)
from engine.config.settings import BotConfig, RecruitmentConfig, load_config
from engine.core.models import Resources, VillageData
from engine.utils.parsers import parse_recruitment_page


SAMPLE_BARRACKS_HTML = """
<!DOCTYPE html>
<html>
<body>
    <form id="train_form" action="/game.php?village=12345&amp;screen=barracks&amp;action=train&amp;h=csrf_abc" method="post">
        <!-- Lanceiro -->
        <tr id="unit_spear">
            <td>Lanceiro</td>
            <td><a id="spear_0_a" href="#" class="unit_link">(35)</a></td>
            <td><input id="spear_0" name="spear" type="text" data-max="35" /></td>
        </tr>

        <!-- Espadachim -->
        <tr id="unit_sword">
            <td>Espadachim</td>
            <td><a id="sword_0_a" href="#" class="unit_link">(20)</a></td>
            <td><input id="sword_0" name="sword" type="text" data-max="20" /></td>
        </tr>

        <!-- Viking -->
        <tr id="unit_axe">
            <td>Viking</td>
            <td><a id="axe_0_a" href="#" class="unit_link">(50)</a></td>
            <td><input id="axe_0" name="axe" type="text" data-max="50" /></td>
        </tr>
    </form>

    <!-- Fila de Treino Ativa -->
    <table id="trainqueue_barracks" class="vis">
        <tr>
            <th>Treinando</th>
            <th>Duração</th>
            <th>Conclusão</th>
            <th>Cancelar</th>
        </tr>
        <tr class="lit trainqueue_barracks">
            <td>25 Lanceiro</td>
            <td><span class="timer">0:45:10</span></td>
            <td>hoje às 18:30:15</td>
            <td><a href="/game.php?village=12345&amp;screen=barracks&amp;action=cancel&amp;id=501">cancelar</a></td>
        </tr>
        <tr class="trainqueue_barracks">
            <td>15 Espadachim</td>
            <td><span class="timer">0:32:00</span></td>
            <td>hoje às 19:02:15</td>
            <td><a href="/game.php?village=12345&amp;screen=barracks&amp;action=cancel&amp;id=502">cancelar</a></td>
        </tr>
    </table>
</body>
</html>
"""

SAMPLE_STABLE_HTML = """
<!DOCTYPE html>
<html>
<body>
    <form id="train_form" action="/game.php?village=12345&amp;screen=stable&amp;action=train&amp;h=csrf_abc" method="post">
        <!-- Explorador -->
        <tr id="unit_spy">
            <td>Explorador</td>
            <td><a id="spy_0_a" href="#">(15)</a></td>
            <td><input id="spy_0" name="spy" type="text" data-max="15" /></td>
        </tr>
        <!-- Cavalaria Leve -->
        <tr id="unit_light">
            <td>Cavalaria Leve</td>
            <td><a id="light_0_a" href="#">(10)</a></td>
            <td><input id="light_0" name="light" type="text" data-max="10" /></td>
        </tr>
    </form>
</body>
</html>
"""


class TestRecruitmentParsers(unittest.TestCase):
    def test_parse_barracks_page(self):
        data = parse_recruitment_page(SAMPLE_BARRACKS_HTML)
        avail = data["available_units"]
        self.assertEqual(avail["spear"], 35)
        self.assertEqual(avail["sword"], 20)
        self.assertEqual(avail["axe"], 50)
        self.assertNotIn("light", avail)

        # Fila ativa
        queue = data["queue"]
        self.assertEqual(len(queue), 2)

        q0 = queue[0]
        self.assertEqual(q0["unit"], "spear")
        self.assertEqual(q0["count"], 25)
        self.assertEqual(q0["timer_str"], "0:45:10")
        self.assertIn("18:30:15", q0["finish_time"])

        q1 = queue[1]
        self.assertEqual(q1["unit"], "sword")
        self.assertEqual(q1["count"], 15)

        # Total em treino
        tot = data["total_in_queue"]
        self.assertEqual(tot["spear"], 25)
        self.assertEqual(tot["sword"], 15)
        self.assertEqual(tot["axe"], 0)

    def test_parse_stable_page(self):
        data = parse_recruitment_page(SAMPLE_STABLE_HTML)
        avail = data["available_units"]
        self.assertEqual(avail["spy"], 15)
        self.assertEqual(avail["light"], 10)
        self.assertEqual(len(data["queue"]), 0)

    def test_parse_modern_tw_trainqueue(self):
        modern_html = """
        <table id="trainqueue_barracks" class="vis">
            <tr>
                <th colspan="2">Treinando</th>
                <th>Duração</th>
                <th>Conclusão</th>
                <th>Cancelamento *</th>
            </tr>
            <tr class="lit">
                <td><span class="unit_sprite_smaller spear" title="Lanceiro"></span></td>
                <td>5 Lanceiros</td>
                <td><span class="timer">12:45</span></td>
                <td>hoje às 13:45:00</td>
                <td><a href="/game.php?village=45497&amp;screen=barracks&amp;action=cancel&amp;id=123">cancelar</a></td>
            </tr>
            <tr>
                <td><span class="unit_sprite_smaller sword" title="Espadachim"></span></td>
                <td>10</td>
                <td><span class="timer">0:45:10</span></td>
                <td>hoje às 14:30:10</td>
                <td><a href="/game.php?village=45497&amp;screen=barracks&amp;action=cancel&amp;id=124">cancelar</a></td>
            </tr>
        </table>
        """
        data = parse_recruitment_page(modern_html)
        queue = data["queue"]
        self.assertEqual(len(queue), 2)
        self.assertEqual(queue[0]["unit"], "spear")
        self.assertEqual(queue[0]["count"], 5)
        self.assertEqual(queue[0]["timer_str"], "12:45")
        self.assertEqual(queue[1]["unit"], "sword")
        self.assertEqual(queue[1]["count"], 10)
        self.assertEqual(data["total_in_queue"]["spear"], 5)
        self.assertEqual(data["total_in_queue"]["sword"], 10)


class TestRecruitmentActions(unittest.IsolatedAsyncioTestCase):
    async def test_run_recruitment_cycle_deficit_and_batching(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345

        # Mock da aldeia com bastante população livre (pop=100)
        account.refresh_state = AsyncMock(return_value=VillageData(
            id=12345,
            name="Aldeia Teste",
            x=450,
            y=550,
            resources=Resources(wood=5000, stone=5000, iron=5000, storage_max=10000, pop=50, pop_max=150),
        ))

        manager = RecruitmentManager()

        # Mock das tropas na aldeia: 30 lanceiros, 45 espadachins
        manager.place_manager.get_state = AsyncMock(return_value=PlaceState(
            village_id=12345,
            units=UnitsCount(spear=30, sword=45, axe=0),
        ))

        # Mock do get_screen para retornar SAMPLE_BARRACKS_HTML no quartel
        account.get_screen = AsyncMock(return_value=SAMPLE_BARRACKS_HTML)
        account.post_action = AsyncMock(return_value=SAMPLE_BARRACKS_HTML)

        # Metas:
        # spear: meta 100. (30 na aldeia + 25 na fila = 55). Faltam 45. Batch limit = 15. Max = 35. -> Treinar 15
        # sword: meta 50. (45 na aldeia + 15 na fila = 60). Meta já superada -> Treinar 0
        # axe: meta 40. (0 na aldeia + 0 na fila = 0). Faltam 40. Batch limit = 10. Max = 50. -> Treinar 10
        targets = {"spear": 100, "sword": 50, "axe": 40}
        batch_sizes = {"spear": 15, "sword": 10, "axe": 10}

        recruited = await manager.run_recruitment_cycle(
            account=account,
            targets=targets,
            batch_sizes=batch_sizes,
            min_free_pop=10,
            max_queue_elements=5,
        )

        self.assertEqual(recruited.get("spear"), 15)
        self.assertEqual(recruited.get("axe"), 10)
        self.assertNotIn("sword", recruited)

        # Valida chamada ao post_action
        account.post_action.assert_called_once()
        call_kwargs = account.post_action.call_args.kwargs
        self.assertEqual(call_kwargs["screen"], "barracks")
        self.assertEqual(call_kwargs["action"], "train")
        self.assertEqual(call_kwargs["data"]["spear"], "15")
        self.assertEqual(call_kwargs["data"]["axe"], "10")
        self.assertNotIn("sword", call_kwargs["data"])

    async def test_run_recruitment_cycle_pop_limit(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345

        # População livre baixa (apenas 5 vagas, quando min_free_pop = 10)
        account.refresh_state = AsyncMock(return_value=VillageData(
            id=12345,
            name="Aldeia Teste",
            x=450,
            y=550,
            resources=Resources(wood=5000, stone=5000, iron=5000, storage_max=10000, pop=95, pop_max=100),
        ))

        manager = RecruitmentManager()
        account.post_action = AsyncMock()

        recruited = await manager.run_recruitment_cycle(
            account=account,
            targets={"spear": 100},
            batch_sizes={"spear": 10},
            min_free_pop=10,
        )

        # Nenhuma tropa recrutada para não quebrar a evolução da Fazenda
        self.assertEqual(len(recruited), 0)
        account.post_action.assert_not_called()

    async def test_train_units_records_stats_telemetry(self):
        import tempfile
        from pathlib import Path
        from engine.core.account import TribalAccount
        from engine.core.stats import StatsTracker

        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345
        account.csrf_token = "token_h"
        account.post_action = AsyncMock(return_value="<div>Sucesso</div>")

        temp_dir = tempfile.mkdtemp()
        tracker = StatsTracker(world="pt117", account_id="test_stats_acc", cache_dir=Path(temp_dir))
        account.stats_tracker = tracker

        manager = RecruitmentManager()
        success = await manager.train_units(
            account=account,
            building="barracks",
            orders={"spear": 20, "sword": 15},
            village_id=12345,
        )

        self.assertTrue(success)
        summary = tracker.get_summary()
        self.assertEqual(summary["totals_all_time"]["troops_recruited"], 35)
        self.assertEqual(summary["recruitment_by_unit"]["spear"], 20)
        self.assertEqual(summary["recruitment_by_unit"]["sword"], 15)

    async def test_run_recruitment_skips_unbuilt_buildings_and_unresearched_units(self):
        from engine.core.account import TribalAccount
        from engine.actions.place import PlaceState

        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345

        # Aldeia tem apenas Edifício Principal 5 e Quartel 1 (Estábulo 0, Oficina 0, Ferreiro 0)
        account.refresh_state = AsyncMock(return_value=VillageData(
            id=12345,
            name="Aldeia Inicial",
            x=450,
            y=550,
            resources=Resources(wood=5000, stone=5000, iron=5000, storage_max=10000, pop=20, pop_max=100),
            buildings={"main": 5, "barracks": 1, "stable": 0, "garage": 0, "smith": 0},
        ))

        mock_place = AsyncMock()
        mock_place.get_state.return_value = PlaceState(village_id=12345, units=UnitsCount(spear=10, sword=0, axe=0, light=0, ram=0))
        manager = RecruitmentManager(place_manager=mock_place)

        # Quartel apenas tem spear disponível (axe e sword não pesquisados/sem requisitos)
        manager.get_building_state = AsyncMock()
        manager.get_building_state.return_value = RecruitmentState(
            building="barracks",
            available_units={"spear": 50},  # 'axe' e 'sword' ausentes
            queue=[],
            total_in_queue={"spear": 0, "sword": 0, "axe": 0},
        )

        account.post_action = AsyncMock()

        # Pede para treinar spear, axe, light (estábulo) e ram (oficina)
        recruited = await manager.run_recruitment_cycle(
            account=account,
            targets={"spear": 30, "axe": 50, "light": 20, "ram": 10},
            batch_sizes={"spear": 10, "axe": 10, "light": 5, "ram": 5},
            min_free_pop=10,
        )

        # Apenas spear deve ser treinado
        self.assertEqual(recruited.get("spear"), 10)
        self.assertNotIn("axe", recruited)
        self.assertNotIn("light", recruited)
        self.assertNotIn("ram", recruited)

        # get_building_state só deve ter sido chamado para 'barracks' (nunca para stable ou garage a nível 0)
        manager.get_building_state.assert_called_once_with(account, "barracks", village_id=12345)

    async def test_dynamic_resource_checking_and_cheapest_first_priority(self):
        from engine.core.account import TribalAccount
        from engine.actions.place import PlaceState

        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345

        # Aldeia com recursos suficientes apenas para lanceiros (Madeira: 300, Argila: 180, Ferro: 60)
        # 5 lanceiros = 250M, 150A, 50F (resta: 50M, 30A, 10F)
        # Bárbaro requer 60M, 30A, 40F (Ferro insuficiente para bárbaros após lanceiros)
        account.refresh_state = AsyncMock(return_value=VillageData(
            id=12345,
            name="Aldeia Recursos Limitados",
            x=450,
            y=550,
            resources=Resources(wood=300, stone=180, iron=60, storage_max=10000, pop=20, pop_max=100),
            buildings={"main": 5, "barracks": 5, "smith": 5},
        ))

        mock_place = AsyncMock()
        mock_place.get_state.return_value = PlaceState(village_id=12345, units=UnitsCount(spear=0, axe=0))
        manager = RecruitmentManager(place_manager=mock_place)

        manager.get_building_state = AsyncMock()
        manager.get_building_state.return_value = RecruitmentState(
            building="barracks",
            available_units={"spear": 50, "axe": 50},
            queue=[],
            total_in_queue={"spear": 0, "axe": 0},
        )

        account.post_action = AsyncMock(return_value="<html></html>")

        # Metas para lanceiro e bárbaro
        recruited = await manager.run_recruitment_cycle(
            account=account,
            targets={"spear": 20, "axe": 20},
            batch_sizes={"spear": 5, "axe": 5},
            min_free_pop=2,
        )

        # Lanceiro é o mais barato (custo 90 vs 130 do bárbaro), portanto treina 5 lanceiros primeiro
        self.assertEqual(recruited.get("spear"), 5)
        # Bárbaro não pôde ser treinado por falta de recursos restantes
        self.assertNotIn("axe", recruited)
        account.post_action.assert_called_once()
        call_kwargs = account.post_action.call_args.kwargs
        self.assertEqual(call_kwargs["data"]["spear"], "5")

    async def test_max_queue_elements_limit(self):
        from engine.core.account import TribalAccount

        account = TribalAccount(world="pt117", sid="test_sid")
        account.current_village_id = 12345
        account.refresh_state = AsyncMock(return_value=VillageData(
            id=12345,
            name="Aldeia Teste",
            x=450,
            y=550,
            resources=Resources(wood=50000, stone=50000, iron=50000, storage_max=100000, pop=50, pop_max=1000),
        ))

        manager = RecruitmentManager()
        manager.place_manager.get_state = AsyncMock(return_value=PlaceState(
            village_id=12345,
            units=UnitsCount(spear=0, sword=0, axe=0),
        ))

        # Caso 1: Quartel já tem 3 ordens ativas na fila
        mock_b_state = RecruitmentState(
            building="barracks",
            available_units={"spear": 100, "sword": 100, "axe": 100},
            queue=[
                TrainingOrder(unit="spear", count=10),
                TrainingOrder(unit="sword", count=10),
                TrainingOrder(unit="axe", count=10),
            ],
            total_in_queue={"spear": 10, "sword": 10, "axe": 10},
        )
        manager.get_building_state = AsyncMock(return_value=mock_b_state)
        account.post_action = AsyncMock(return_value=SAMPLE_BARRACKS_HTML)

        targets = {"spear": 500, "sword": 500, "axe": 500}
        batch_sizes = {"spear": 10, "sword": 10, "axe": 10}

        recruited = await manager.run_recruitment_cycle(
            account=account,
            targets=targets,
            batch_sizes=batch_sizes,
            min_free_pop=10,
            max_queue_elements=3,
        )

        # Fila já tinha 3 elementos -> nenhuma nova ordem deve ser submetida!
        self.assertEqual(len(recruited), 0)
        account.post_action.assert_not_called()

        # Caso 2: Quartel tem 2 ordens ativas -> só pode adicionar 1 ordem (slots_available = 1)
        mock_b_state_2 = RecruitmentState(
            building="barracks",
            available_units={"spear": 100, "sword": 100, "axe": 100},
            queue=[
                TrainingOrder(unit="spear", count=10),
                TrainingOrder(unit="sword", count=10),
            ],
            total_in_queue={"spear": 10, "sword": 10},
        )
        manager.get_building_state = AsyncMock(return_value=mock_b_state_2)
        account.post_action = AsyncMock(return_value=SAMPLE_BARRACKS_HTML)

        recruited_2 = await manager.run_recruitment_cycle(
            account=account,
            targets=targets,
            batch_sizes=batch_sizes,
            min_free_pop=10,
            max_queue_elements=3,
        )

        # Apenas 1 nova ordem (spear, menor custo total) deve ser recrutada!
        self.assertEqual(len(recruited_2), 1)
        self.assertIn("spear", recruited_2)
        account.post_action.assert_called_once()


class TestRecruitmentConfig(unittest.TestCase):
    def test_recruitment_config_defaults(self):
        r_cfg = RecruitmentConfig(
            enabled=True,
            targets={"spear": 200, "light": 50},
            batch_sizes={"spear": 20, "light": 5},
            min_free_pop=15,
            interval_minutes=4.0,
        )
        self.assertTrue(r_cfg.enabled)
        self.assertEqual(r_cfg.targets["spear"], 200)
        self.assertEqual(r_cfg.targets["light"], 50)
        self.assertEqual(r_cfg.batch_sizes["spear"], 20)
        self.assertEqual(r_cfg.min_free_pop, 15)
        self.assertEqual(r_cfg.interval_minutes, 4.0)
        self.assertIn("attack", r_cfg.models)
        self.assertIn("defense", r_cfg.models)
        self.assertEqual(r_cfg.models["attack"]["axe"], 6000)
        self.assertEqual(r_cfg.models["defense"]["spear"], 7000)

    def test_get_village_recruitment_targets_by_model(self):
        from engine.config.settings import VillageConfig

        cfg = BotConfig()
        cfg.villages["12345"] = VillageConfig(category="attack")
        cfg.villages["67890"] = VillageConfig(category="defense")
        cfg.recruitment.models["attack"]["axe"] = 7500
        cfg.recruitment.models["defense"]["heavy"] = 1200

        targets_attack = cfg.get_village_recruitment_targets("12345")
        targets_defense = cfg.get_village_recruitment_targets("67890")

        self.assertEqual(targets_attack.get("axe"), 7500)
        self.assertEqual(targets_defense.get("heavy"), 1200)

    def test_get_village_recruitment_targets_custom_model(self):
        from engine.config.settings import VillageConfig

        cfg = BotConfig()
        cfg.recruitment.models["nuke"] = {"axe": 8000, "light": 3300, "ram": 350, "catapult": 20}
        cfg.villages["999"] = VillageConfig(category="nuke")

        targets_nuke = cfg.get_village_recruitment_targets("999")
        self.assertEqual(targets_nuke.get("axe"), 8000)
        self.assertEqual(targets_nuke.get("ram"), 350)


class TestRecruitmentModelsApi(unittest.TestCase):
    def test_get_and_save_recruitment_models_context(self):
        from engine.api.context import EngineContext
        from engine.core.scheduler import TaskScheduler

        cfg = BotConfig()
        scheduler = TaskScheduler()
        ctx = EngineContext(scheduler=scheduler, config=cfg)
        ctx.config.recruitment.models = {
            "attack": {"axe": 5500, "light": 2800},
            "defense": {"spear": 6500, "sword": 6500},
        }

        res = ctx.get_recruitment_models()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["models"]["attack"]["axe"], 5500)
        self.assertEqual(res["models"]["defense"]["spear"], 6500)

        with patch.object(ctx, "update_config_and_save", return_value={"status": "success"}):
            res_save = ctx.save_recruitment_models(
                attack={"axe": 6200, "light": 3100, "ram": 300},
                defense={"spear": 8000, "sword": 8000, "heavy": 1500},
            )
            self.assertEqual(res_save["status"], "success")
            self.assertEqual(ctx.config.recruitment.models["attack"]["axe"], 6200)
            self.assertEqual(ctx.config.recruitment.models["defense"]["spear"], 8000)

    def test_save_and_delete_custom_models(self):
        from engine.api.context import EngineContext
        from engine.core.scheduler import TaskScheduler

        cfg = BotConfig()
        scheduler = TaskScheduler()
        ctx = EngineContext(scheduler=scheduler, config=cfg)

        with patch.object(ctx, "update_config_and_save", return_value={"status": "success"}):
            res = ctx.save_recruitment_models(models={
                "attack": {"axe": 6000},
                "defense": {"spear": 7000},
                "nuke_speed": {"axe": 7500, "light": 3200, "ram": 300},
            })
            self.assertEqual(res["status"], "success")
            self.assertIn("nuke_speed", ctx.config.recruitment.models)
            self.assertEqual(ctx.config.recruitment.models["nuke_speed"]["light"], 3200)

            # Deleta modelo customizado
            del_res = ctx.delete_recruitment_model("nuke_speed")
            self.assertEqual(del_res["status"], "success")
            self.assertNotIn("nuke_speed", ctx.config.recruitment.models)

            # Tentar deletar attack dá erro
            del_attack = ctx.delete_recruitment_model("attack")
            self.assertEqual(del_attack["status"], "error")

    def test_recruitment_config_max_queue_elements(self):
        from engine.config.settings import parse_config_dict
        cfg = BotConfig()
        self.assertEqual(cfg.recruitment.max_queue_elements, 3)

        parsed = parse_config_dict({"recruitment": {"max_queue_elements": 2}})
        self.assertEqual(parsed.recruitment.max_queue_elements, 2)

    def test_parse_desktop_tw_queue_items(self):
        """Valida que parse_recruitment_page extrai ordens da fila com layout moderno de divs (.queueItem)."""
        desktop_html = """
        <div id="trainqueue_barracks">
            <div class="queueItem" data-order="2046991">
                <div style="margin-bottom: 6px">
                    <div style="max-width: 220px; float: left">
                        <img src="https://dspt.innogamescdn.com/asset/db281c7a/graphic/unit/unit_spear.webp" /> 10 Lanceiro
                    </div>
                    <div style="float: right">
                        <span class="timer">0:04:24</span>
                    </div>
                </div>
                <div style="clear: both; max-width: 220px; float: left; margin-top: 7px">
                    hoje às 16:24:42
                </div>
                <div style="float: right">
                    <a class="btn btn-cancel" onclick="return TrainOverview.cancelOrder(2046991)" href="/game.php?village=6662&amp;screen=barracks&amp;action=cancel&amp;id=2035306&amp;h=38e2da63">Cancelar</a>
                </div>
            </div>
            <div class="queueItem" data-order="2048313">
                <div style="margin-bottom: 6px">
                    <div style="max-width: 220px; float: left">
                        <img src="https://dspt.innogamescdn.com/asset/db281c7a/graphic/unit/unit_axe.webp" /> 25 Bárbaro
                    </div>
                    <div style="float: right">
                        0:15:30
                    </div>
                </div>
                <div style="clear: both; max-width: 220px; float: left; margin-top: 7px">
                    hoje às 16:39:42
                </div>
                <div style="float: right">
                    <a class="btn btn-cancel" onclick="return TrainOverview.cancelOrder(2048313)" href="/game.php?village=6662&amp;screen=barracks&amp;action=cancel&amp;id=2035307&amp;h=38e2da63">Cancelar</a>
                </div>
            </div>
        </div>
        """
        data = parse_recruitment_page(desktop_html)
        self.assertEqual(len(data["queue"]), 2)
        self.assertEqual(data["queue"][0]["unit"], "spear")
        self.assertEqual(data["queue"][0]["count"], 10)
        self.assertEqual(data["queue"][0]["timer_str"], "0:04:24")
        self.assertIn("action=cancel", data["queue"][0]["cancel_url"])
        self.assertEqual(data["queue"][1]["unit"], "axe")
        self.assertEqual(data["queue"][1]["count"], 25)
        self.assertEqual(data["total_in_queue"]["spear"], 10)
        self.assertEqual(data["total_in_queue"]["axe"], 25)


if __name__ == "__main__":
    unittest.main()


