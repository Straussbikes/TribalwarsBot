"""
Testes Unitários para WorldDatabase e WorldDataWorker (Ingestão de Dados Públicos do Mundo).
"""

import asyncio
import tempfile
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch
import httpx

from engine.actions.world_data import (
    WorldDataWorker,
    parse_world_dump_allies,
    parse_world_dump_players,
    parse_world_dump_villages,
)
from engine.storage.world_database import (
    WorldAllyRecord,
    WorldDatabase,
    WorldPlayerRecord,
    WorldVillageRecord,
)

SAMPLE_VILLAGE_CSV = """
101,Aldeia+de+B%C3%A1rbaros,450,550,0,120,0
102,Aldeia+Principal,451,551,1001,1520,1
103,Segunda+Aldeia,452,552,1001,2300,2
104,Aldeia+Inimiga,455,555,1002,4500,3
105,Aldeia+Regressiva,453,553,1003,3200,4
"""

SAMPLE_PLAYER_CSV = """
1001,Jogador+Ativo,501,2,3820,1
1002,Jogador+Inativo,0,1,4500,2
1003,Outro+Jogador,502,5,12000,3
"""

SAMPLE_ALLY_CSV = """
501,Tribo+Vencedora,WIN,25,80,150000,180000,1
502,Tribo+Aliada,ALLY,10,30,50000,55000,2
"""


class TestWorldData(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_world.db"
        self.db = WorldDatabase(db_path=self.db_path)
        self.worker = WorldDataWorker(db=self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_world_dumps(self):
        villages = parse_world_dump_villages(SAMPLE_VILLAGE_CSV)
        self.assertEqual(len(villages), 5)
        self.assertEqual(villages[0].name, "Aldeia de Bárbaros")
        self.assertEqual(villages[0].x, 450)
        self.assertEqual(villages[0].y, 550)
        self.assertEqual(villages[0].player_id, 0)
        self.assertEqual(villages[1].name, "Aldeia Principal")
        self.assertEqual(villages[1].player_id, 1001)

        players = parse_world_dump_players(SAMPLE_PLAYER_CSV)
        self.assertEqual(len(players), 3)
        self.assertEqual(players[0].name, "Jogador Ativo")
        self.assertEqual(players[0].ally_id, 501)
        self.assertEqual(players[1].name, "Jogador Inativo")
        self.assertEqual(players[1].ally_id, 0)

        allies = parse_world_dump_allies(SAMPLE_ALLY_CSV)
        self.assertEqual(len(allies), 2)
        self.assertEqual(allies[0].name, "Tribo Vencedora")
        self.assertEqual(allies[0].tag, "WIN")

    def test_world_database_snapshot_crud(self):
        villages = parse_world_dump_villages(SAMPLE_VILLAGE_CSV)
        players = parse_world_dump_players(SAMPLE_PLAYER_CSV)
        allies = parse_world_dump_allies(SAMPLE_ALLY_CSV)

        # 1. Salvar snapshot inicial
        ts1 = 1700000000.0
        snap_id1 = self.db.save_world_snapshot(
            world="pt117",
            villages=villages,
            players=players,
            allies=allies,
            etags={"village": "etag_v1"},
            custom_timestamp=ts1,
        )
        self.assertTrue(snap_id1 > 0)

        # 2. Obter latest snapshot
        latest = self.db.get_latest_snapshot("pt117")
        self.assertIsNotNone(latest)
        self.assertEqual(latest["id"], snap_id1)
        self.assertEqual(latest["villages_count"], 5)
        self.assertEqual(latest["players_count"], 3)
        self.assertEqual(latest["allies_count"], 2)

        # 3. Salvar segundo snapshot (3 dias depois)
        ts2 = ts1 + (3 * 86400.0)
        snap_id2 = self.db.save_world_snapshot(
            world="pt117",
            villages=villages,
            players=players,
            allies=allies,
            custom_timestamp=ts2,
        )

        all_snaps = self.db.get_all_snapshots("pt117")
        self.assertEqual(len(all_snaps), 2)

        # 4. Busca por timestamp
        snap_past = self.db.get_snapshot_at_or_before("pt117", ts1 + 100)
        self.assertIsNotNone(snap_past)
        self.assertEqual(snap_past["id"], snap_id1)

    async def test_worker_sync_world_data(self):
        async def mock_fetch_dump(client, url, cached_etag=None):
            if "village.txt" in url:
                return SAMPLE_VILLAGE_CSV, "etag_v_new", True
            elif "player.txt" in url:
                return SAMPLE_PLAYER_CSV, "etag_p_new", True
            elif "ally.txt" in url:
                return SAMPLE_ALLY_CSV, "etag_a_new", True
            return None, None, False

        with patch.object(self.worker, "_fetch_dump_file", side_effect=mock_fetch_dump):
            result = await self.worker.sync_world_data(world="pt117", domain="tribalwars.com.pt")

            self.assertTrue(result.is_updated)
            self.assertEqual(result.villages_count, 5)
            self.assertEqual(result.players_count, 3)
            self.assertEqual(result.allies_count, 2)
            self.assertIsNotNone(result.snapshot_id)

    async def test_worker_sync_http_304_not_modified(self):
        # Primeiro sync grava snapshot
        self.db.save_world_snapshot(
            world="pt117",
            villages=parse_world_dump_villages(SAMPLE_VILLAGE_CSV),
            players=parse_world_dump_players(SAMPLE_PLAYER_CSV),
            allies=parse_world_dump_allies(SAMPLE_ALLY_CSV),
            etags={"village": "v_etag", "player": "p_etag", "ally": "a_etag"},
        )

        async def mock_304_fetch(client, url, cached_etag=None):
            return None, cached_etag, False

        with patch.object(self.worker, "_fetch_dump_file", side_effect=mock_304_fetch):
            result = await self.worker.sync_world_data(world="pt117", force=False)

            self.assertFalse(result.is_updated)
            self.assertEqual(result.villages_count, 5)
            self.assertIsNotNone(result.snapshot_id)

    def test_inactivity_analysis_delta_p_and_categories(self):
        from engine.actions.inactivity_tracker import InactivityTracker

        # Snapshot Passado (7 dias atrás)
        ts_past = 1700000000.0
        past_players = [
            WorldPlayerRecord(id=1001, name="Jogador Ativo", ally_id=501, villages_count=2, points=3000, rank=1),
            WorldPlayerRecord(id=1002, name="Jogador Inativo", ally_id=0, villages_count=1, points=4500, rank=2),
            WorldPlayerRecord(id=1003, name="Outro Jogador", ally_id=502, villages_count=5, points=14000, rank=3),
        ]
        self.db.save_world_snapshot(
            world="pt117",
            villages=parse_world_dump_villages(SAMPLE_VILLAGE_CSV),
            players=past_players,
            allies=parse_world_dump_allies(SAMPLE_ALLY_CSV),
            custom_timestamp=ts_past,
        )

        # Snapshot Atual (agora)
        # 1001 subiu de 3000 -> 3820 (ΔP = +820 -> growing)
        # 1002 manteve 4500 -> 4500 (ΔP = 0 -> stagnant)
        # 1003 desceu de 14000 -> 12000 (ΔP = -2000 -> regressive)
        ts_now = ts_past + (7 * 86400.0)
        curr_players = parse_world_dump_players(SAMPLE_PLAYER_CSV)
        self.db.save_world_snapshot(
            world="pt117",
            villages=parse_world_dump_villages(SAMPLE_VILLAGE_CSV),
            players=curr_players,
            allies=parse_world_dump_allies(SAMPLE_ALLY_CSV),
            custom_timestamp=ts_now,
        )

        tracker = InactivityTracker(db=self.db)
        report = tracker.scan_inactives(
            world="pt117",
            origin_x=450,
            origin_y=550,
            max_distance=20.0,
            days_window=7.0,
        )

        self.assertEqual(report.world, "pt117")
        self.assertEqual(report.origin_coords, "450|550")
        self.assertTrue(report.total_targets_found >= 2)
        self.assertEqual(report.stagnant_count, 1)    # 1002 (ΔP = 0)
        self.assertEqual(report.regressive_count, 1)  # 1003 (ΔP = -2000)
        # Verifica dados detalhados do jogador inativo
        inact = next(t for t in report.targets if t.player_id == 1002)
        self.assertEqual(inact.delta_points, 0)
        self.assertEqual(inact.inactivity_category, "stagnant")
        self.assertTrue(inact.is_highly_inactive)
        self.assertEqual(inact.ally_tag, "")
        self.assertTrue(inact.travel_time_lc_seconds > 0)

    def test_inactivity_tactical_filters(self):
        from engine.actions.inactivity_tracker import InactivityFilterConfig, InactivityTracker

        # Snapshot 1
        ts1 = 1700000000.0
        self.db.save_world_snapshot(
            world="pt117",
            villages=parse_world_dump_villages(SAMPLE_VILLAGE_CSV),
            players=parse_world_dump_players(SAMPLE_PLAYER_CSV),
            allies=parse_world_dump_allies(SAMPLE_ALLY_CSV),
            custom_timestamp=ts1,
        )

        tracker = InactivityTracker(db=self.db)

        # 1. Filtro por Blacklist de Coordenadas
        cfg_black = InactivityFilterConfig(
            max_distance=30.0,
            blacklist_coords=["451|551"],  # Aldeia 102
        )
        rep_black = tracker.scan_inactives("pt117", origin_x=450, origin_y=550, filter_config=cfg_black)
        self.assertFalse(any(t.coords == "451|551" for t in rep_black.targets))

        # 2. Filtro de Exclusão de Tribo (Tribo 501 - Jogador 1001)
        cfg_ally = InactivityFilterConfig(
            max_distance=30.0,
            exclude_ally_ids=[501],
        )
        rep_ally = tracker.scan_inactives("pt117", origin_x=450, origin_y=550, filter_config=cfg_ally)
        self.assertFalse(any(t.ally_id == 501 for t in rep_ally.targets))

        # 3. Filtro Apenas Sem Tribo (Tribeless)
        cfg_tribeless = InactivityFilterConfig(
            max_distance=30.0,
            only_tribeless=True,
            include_single_member_tribes=False,
        )
        rep_tribeless = tracker.scan_inactives("pt117", origin_x=450, origin_y=550, filter_config=cfg_tribeless)
        self.assertTrue(all(t.ally_id == 0 for t in rep_tribeless.targets))

    def test_travel_times_and_farm_export(self):
        from engine.actions.inactivity_tracker import (
            InactiveTarget,
            InactivityTracker,
            calculate_unit_travel_times,
            format_duration_seconds,
        )
        from engine.actions.place import UnitsCount

        # 1. Teste de formatação e cálculo de tempos de marcha
        self.assertEqual(format_duration_seconds(65), "01:05")
        self.assertEqual(format_duration_seconds(3665), "01:01:05")

        timing = calculate_unit_travel_times(distance=10.0, base_timestamp=1700000000.0)
        self.assertEqual(timing["light"]["duration_seconds"], 6000)  # 10 * 600s
        self.assertEqual(timing["spy"]["duration_seconds"], 5400)    # 10 * 540s
        self.assertEqual(timing["light"]["duration_str"], "01:40:00")
        self.assertEqual(timing["spy"]["duration_str"], "01:30:00")

        # 2. Teste de exportação de alvos inativos para lista customizada de farm
        tracker = InactivityTracker(db=self.db)
        dummy_targets = [
            InactiveTarget(
                village_id=1, village_name="V1", x=450, y=551, coords="450|551",
                player_id=10, player_name="P1", player_points=500, player_villages_count=1,
                ally_id=0, ally_name="", ally_tag="",
            ),
            InactiveTarget(
                village_id=2, village_name="V2", x=452, y=553, coords="452|553",
                player_id=20, player_name="P2", player_points=800, player_villages_count=1,
                ally_id=0, ally_name="", ally_tag="",
            ),
        ]
        exported = tracker.export_targets_to_custom_farm(dummy_targets, current_custom_targets=[(450, 550)])
        self.assertEqual(len(exported), 3)
        self.assertIn((450, 550), exported)
        self.assertIn((450, 551), exported)
        self.assertIn((452, 553), exported)

        # 3. Teste de geração de payload de ataque
        troops = UnitsCount(spear=10, spy=2, light=5)
        payload = tracker.create_attack_payload(dummy_targets[0], troops=troops, is_attack=True)
        self.assertEqual(payload["x"], "450")
        self.assertEqual(payload["y"], "551")
        self.assertEqual(payload["target_village_id"], "1")
        self.assertEqual(payload["action_type"], "attack")
        self.assertEqual(payload["spear"], 10)
        self.assertEqual(payload["light"], 5)

    def test_radius_players_evolution_and_timeline(self):
        """Testa o cálculo da evolução dos jogadores no raio de X campos e sua linha do tempo."""
        villages_old = [
            WorldVillageRecord(id=101, name="V1", x=450, y=551, player_id=201, points=500, rank=1),
            WorldVillageRecord(id=102, name="V2", x=451, y=552, player_id=202, points=1200, rank=2),
            WorldVillageRecord(id=103, name="V3", x=490, y=590, player_id=203, points=800, rank=3), # Fora do raio
        ]
        players_old = [
            WorldPlayerRecord(id=201, name="Jogador Alfa", ally_id=301, villages_count=1, points=500, rank=10),
            WorldPlayerRecord(id=202, name="Jogador Beta", ally_id=0, villages_count=1, points=1200, rank=5),
            WorldPlayerRecord(id=203, name="Jogador Longe", ally_id=0, villages_count=1, points=800, rank=8),
        ]
        allies = [WorldAllyRecord(id=301, name="T1", tag="TAG1", members_count=5, villages_count=10, points=5000, all_points=5000, rank=1)]

        # Snapshot 1 (7 dias atrás)
        now = 1700000000.0
        self.db.save_world_snapshot("pt117", villages_old, players_old, allies, custom_timestamp=now - (7 * 86400.0))

        # Snapshot 2 (Agora)
        villages_now = [
            WorldVillageRecord(id=101, name="V1", x=450, y=551, player_id=201, points=1800, rank=1),
            WorldVillageRecord(id=102, name="V2", x=451, y=552, player_id=202, points=1200, rank=2),
            WorldVillageRecord(id=103, name="V3", x=490, y=590, player_id=203, points=800, rank=3),
        ]
        players_now = [
            WorldPlayerRecord(id=201, name="Jogador Alfa", ally_id=301, villages_count=1, points=1800, rank=4), # Cresceu +1300
            WorldPlayerRecord(id=202, name="Jogador Beta", ally_id=0, villages_count=1, points=1200, rank=5),  # Estagnado (delta 0)
            WorldPlayerRecord(id=203, name="Jogador Longe", ally_id=0, villages_count=1, points=800, rank=8),
        ]
        self.db.save_world_snapshot("pt117", villages_now, players_now, allies, custom_timestamp=now)

        # 1. Teste get_players_in_radius
        players_radius = self.db.get_players_in_radius("pt117", origin_x=450, origin_y=550, max_distance=10.0)
        self.assertEqual(len(players_radius), 2)
        p_ids = [p["player_id"] for p in players_radius]
        self.assertIn(201, p_ids)
        self.assertIn(202, p_ids)
        self.assertNotIn(203, p_ids)

        # 2. Teste get_radius_players_evolution
        evo = self.db.get_radius_players_evolution("pt117", origin_x=450, origin_y=550, max_distance=10.0)
        self.assertEqual(len(evo), 2)
        alfa = next(p for p in evo if p["player_id"] == 201)
        beta = next(p for p in evo if p["player_id"] == 202)

        self.assertEqual(alfa["player_points"], 1800)
        self.assertEqual(alfa["delta_7d"], 1300)
        self.assertIn(alfa["trend"], ["accelerating", "growing"])

        self.assertEqual(beta["player_points"], 1200)
        self.assertEqual(beta["delta_7d"], 0)
        self.assertIn(beta["trend"], ["stagnant", "inactive"])

        # 3. Teste get_player_timeline
        timeline_alfa = self.db.get_player_timeline("pt117", player_id=201)
        self.assertEqual(len(timeline_alfa), 2)
        self.assertEqual(timeline_alfa[0]["points"], 500)
        self.assertEqual(timeline_alfa[1]["points"], 1800)
        self.assertEqual(timeline_alfa[1]["delta"], 1300)


if __name__ == "__main__":
    unittest.main()

