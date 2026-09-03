"""
Tribal Wars Mobile Automation Engine - World Database
Armazenamento relacional e indexado em SQLite para dados públicos de mundos (dumps de mapa).
Suporta séries temporais, snapshots históricos e consultas geoespaciais e de inatividade.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import math
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("TribalWarsBot.WorldDatabase")


@dataclass
class WorldVillageRecord:
    id: int
    name: str
    x: int
    y: int
    player_id: int
    points: int
    rank: int


@dataclass
class WorldPlayerRecord:
    id: int
    name: str
    ally_id: int
    villages_count: int
    points: int
    rank: int


@dataclass
class WorldAllyRecord:
    id: int
    name: str
    tag: str
    members_count: int
    villages_count: int
    points: int
    all_points: int
    rank: int


class WorldDatabase:
    """
    Gestor de base de dados SQLite dedicada a dados públicos de mundos e séries temporais.
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            import sys
            if getattr(sys, "frozen", False):
                base_dir = Path(sys.executable).resolve().parent
            else:
                base_dir = Path(__file__).resolve().parent.parent.parent
            data_dir = base_dir / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "world_data.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            try:
                conn.close()
            except Exception as e:
                logger.debug(f"Aviso ao fechar conexão SQLite WorldData: {e}")

    def _init_db(self) -> None:
        """Inicializa as tabelas e índices otimizados para séries temporais e buscas rápidas."""
        with self._get_connection() as conn:
            # 1. Snapshots e histórico de sincronizações
            conn.execute("""
                CREATE TABLE IF NOT EXISTS world_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    world TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    datetime_iso TEXT NOT NULL,
                    villages_count INTEGER DEFAULT 0,
                    players_count INTEGER DEFAULT 0,
                    allies_count INTEGER DEFAULT 0,
                    etag_village TEXT,
                    etag_player TEXT,
                    etag_ally TEXT
                )
            """)

            # 2. Aldeias por Snapshot
            conn.execute("""
                CREATE TABLE IF NOT EXISTS world_villages (
                    snapshot_id INTEGER NOT NULL,
                    world TEXT NOT NULL,
                    village_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    x INTEGER NOT NULL,
                    y INTEGER NOT NULL,
                    player_id INTEGER NOT NULL,
                    points INTEGER NOT NULL,
                    rank INTEGER DEFAULT 0,
                    timestamp REAL NOT NULL,
                    PRIMARY KEY (snapshot_id, village_id),
                    FOREIGN KEY (snapshot_id) REFERENCES world_snapshots(id) ON DELETE CASCADE
                )
            """)

            # 3. Jogadores por Snapshot
            conn.execute("""
                CREATE TABLE IF NOT EXISTS world_players (
                    snapshot_id INTEGER NOT NULL,
                    world TEXT NOT NULL,
                    player_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    ally_id INTEGER DEFAULT 0,
                    villages_count INTEGER DEFAULT 0,
                    points INTEGER NOT NULL,
                    rank INTEGER DEFAULT 0,
                    timestamp REAL NOT NULL,
                    PRIMARY KEY (snapshot_id, player_id),
                    FOREIGN KEY (snapshot_id) REFERENCES world_snapshots(id) ON DELETE CASCADE
                )
            """)

            # 4. Tribos por Snapshot
            conn.execute("""
                CREATE TABLE IF NOT EXISTS world_allies (
                    snapshot_id INTEGER NOT NULL,
                    world TEXT NOT NULL,
                    ally_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    members_count INTEGER DEFAULT 0,
                    villages_count INTEGER DEFAULT 0,
                    points INTEGER NOT NULL,
                    all_points INTEGER DEFAULT 0,
                    rank INTEGER DEFAULT 0,
                    timestamp REAL NOT NULL,
                    PRIMARY KEY (snapshot_id, ally_id),
                    FOREIGN KEY (snapshot_id) REFERENCES world_snapshots(id) ON DELETE CASCADE
                )
            """)

            # Índices de Performance para Consultas Rápidas e Cálculos de ΔP
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wv_world_coords ON world_villages(world, x, y)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wv_player ON world_villages(world, player_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wv_snapshot ON world_villages(snapshot_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wp_world_player ON world_players(world, player_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wp_snapshot ON world_players(snapshot_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_wp_ally ON world_players(world, ally_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ws_world_time ON world_snapshots(world, timestamp)")
            conn.commit()

    def save_world_snapshot(
        self,
        world: str,
        villages: List[WorldVillageRecord],
        players: List[WorldPlayerRecord],
        allies: List[WorldAllyRecord],
        etags: Optional[Dict[str, str]] = None,
        custom_timestamp: Optional[float] = None,
    ) -> int:
        """
        Insere um novo snapshot atómico completo do mundo com milhares de aldeias e jogadores em lote (executemany).
        Retorna o snapshot_id gerado.
        """
        now_ts = custom_timestamp or time.time()
        iso_str = datetime.fromtimestamp(now_ts, timezone.utc).isoformat()
        etags_dict = etags or {}

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO world_snapshots (
                    world, timestamp, datetime_iso,
                    villages_count, players_count, allies_count,
                    etag_village, etag_player, etag_ally
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    world.lower().strip(),
                    now_ts,
                    iso_str,
                    len(villages),
                    len(players),
                    len(allies),
                    etags_dict.get("village"),
                    etags_dict.get("player"),
                    etags_dict.get("ally"),
                ),
            )
            snapshot_id = cursor.lastrowid

            # Inserção em Lote Otimizada de Aldeias
            if villages:
                v_rows = [
                    (
                        snapshot_id,
                        world.lower().strip(),
                        v.id,
                        v.name,
                        v.x,
                        v.y,
                        v.player_id,
                        v.points,
                        v.rank,
                        now_ts,
                    )
                    for v in villages
                ]
                cursor.executemany(
                    """
                    INSERT INTO world_villages (
                        snapshot_id, world, village_id, name, x, y, player_id, points, rank, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    v_rows,
                )

            # Inserção em Lote Otimizada de Jogadores
            if players:
                p_rows = [
                    (
                        snapshot_id,
                        world.lower().strip(),
                        p.id,
                        p.name,
                        p.ally_id,
                        p.villages_count,
                        p.points,
                        p.rank,
                        now_ts,
                    )
                    for p in players
                ]
                cursor.executemany(
                    """
                    INSERT INTO world_players (
                        snapshot_id, world, player_id, name, ally_id, villages_count, points, rank, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    p_rows,
                )

            # Inserção em Lote Otimizada de Tribos
            if allies:
                a_rows = [
                    (
                        snapshot_id,
                        world.lower().strip(),
                        a.id,
                        a.name,
                        a.tag,
                        a.members_count,
                        a.villages_count,
                        a.points,
                        a.all_points,
                        a.rank,
                        now_ts,
                    )
                    for a in allies
                ]
                cursor.executemany(
                    """
                    INSERT INTO world_allies (
                        snapshot_id, world, ally_id, name, tag, members_count, villages_count, points, all_points, rank, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    a_rows,
                )

            conn.commit()
            logger.info(
                f"[{world}] Snapshot #{snapshot_id} gravado com sucesso: "
                f"{len(villages)} aldeias, {len(players)} jogadores, {len(allies)} tribos."
            )
            return snapshot_id

    def get_latest_snapshot(self, world: str) -> Optional[Dict[str, Any]]:
        """Retorna o snapshot mais recente registado para o mundo especificado."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM world_snapshots
                WHERE world = ?
                ORDER BY timestamp DESC LIMIT 1
                """,
                (world.lower().strip(),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)

    def get_snapshot_at_or_before(self, world: str, target_timestamp: float) -> Optional[Dict[str, Any]]:
        """Retorna o snapshot mais próximo no passado (ou no momento) do timestamp indicado."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM world_snapshots
                WHERE world = ? AND timestamp <= ?
                ORDER BY timestamp DESC LIMIT 1
                """,
                (world.lower().strip(), target_timestamp),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)

    def get_all_snapshots(self, world: str) -> List[Dict[str, Any]]:
        """Lista todos os snapshots históricos disponíveis para o mundo."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM world_snapshots
                WHERE world = ?
                ORDER BY timestamp DESC
                """,
                (world.lower().strip(),),
            )
            return [dict(r) for r in cursor.fetchall()]

    def cleanup_old_snapshots(self, world: str, retention_days: int = 30) -> int:
        """Remove snapshots com mais de retention_days dias para poupar espaço em disco."""
        cutoff = time.time() - (retention_days * 86400.0)
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id FROM world_snapshots
                WHERE world = ? AND timestamp < ?
                """,
                (world.lower().strip(), cutoff),
            )
            ids_to_delete = [r["id"] for r in cursor.fetchall()]
            if not ids_to_delete:
                return 0

            placeholders = ",".join("?" for _ in ids_to_delete)
            conn.execute(f"DELETE FROM world_villages WHERE snapshot_id IN ({placeholders})", ids_to_delete)
            conn.execute(f"DELETE FROM world_players WHERE snapshot_id IN ({placeholders})", ids_to_delete)
            conn.execute(f"DELETE FROM world_allies WHERE snapshot_id IN ({placeholders})", ids_to_delete)
            conn.execute(f"DELETE FROM world_snapshots WHERE id IN ({placeholders})", ids_to_delete)
            conn.commit()
            logger.info(f"[{world}] Limpeza concluída: {len(ids_to_delete)} snapshots antigos removidos.")
            return len(ids_to_delete)

    def get_inactivity_analysis(
        self,
        world: str,
        origin_x: int,
        origin_y: int,
        max_distance: float = 30.0,
        days_window: float = 7.0,
        max_points_growth: int = 30,
        min_points: int = 100,
        max_points: int = 15000,
        exclude_ally_ids: Optional[List[int]] = None,
        exclude_player_ids: Optional[List[int]] = None,
        blacklist_coords: Optional[List[str]] = None,
        only_tribeless: bool = False,
        include_single_member_tribes: bool = True,
        include_barbarians: bool = False,
        allowed_categories: Optional[List[str]] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Calcula a variação temporal de pontos (ΔP) e aplica filtros táticos avançados:
        - Raio euclidiano e pontuação da aldeia/jogador
        - Exclusão de tribos aliadas/PNA e lista de jogadores bloqueados
        - Filtro de alvos sem tribo ou de tribos com 1 único membro
        - Blacklist de coordenadas protegidas
        - Classificação estocástica de inatividade
        """
        clean_w = world.lower().strip()
        latest_snap = self.get_latest_snapshot(clean_w)
        if not latest_snap:
            return []

        latest_snap_id = latest_snap["id"]
        latest_ts = latest_snap["timestamp"]

        # Localiza o snapshot passado mais próximo de (T_now - days_window dias)
        target_past_ts = latest_ts - (days_window * 86400.0)
        past_snap = self.get_snapshot_at_or_before(clean_w, target_past_ts)
        past_snap_id = past_snap["id"] if past_snap else latest_snap_id
        actual_days_diff = max(0.01, (latest_ts - past_snap["timestamp"]) / 86400.0) if past_snap else 0.0

        with self._get_connection() as conn:
            query = """
                SELECT 
                    v.village_id,
                    v.name AS village_name,
                    v.x,
                    v.y,
                    v.points AS village_points,
                    v.player_id,
                    COALESCE(p.name, 'Aldeia Bárbara') AS player_name,
                    COALESCE(p.points, 0) AS player_points,
                    COALESCE(p.villages_count, 1) AS player_villages_count,
                    COALESCE(a.ally_id, 0) AS ally_id,
                    COALESCE(a.name, '') AS ally_name,
                    COALESCE(a.tag, '') AS ally_tag,
                    COALESCE(a.members_count, 0) AS ally_members_count,
                    past_p.points AS past_player_points,
                    past_v.points AS past_village_points
                FROM world_villages v
                LEFT JOIN world_players p ON p.snapshot_id = v.snapshot_id AND p.player_id = v.player_id
                LEFT JOIN world_allies a ON a.snapshot_id = v.snapshot_id AND a.ally_id = p.ally_id
                LEFT JOIN world_villages past_v ON past_v.snapshot_id = ? AND past_v.village_id = v.village_id
                LEFT JOIN world_players past_p ON past_p.snapshot_id = ? AND past_p.player_id = v.player_id
                WHERE v.snapshot_id = ?
            """
            cursor = conn.execute(query, (past_snap_id, past_snap_id, latest_snap_id))
            rows = cursor.fetchall()

        excluded_allies = set(exclude_ally_ids or [])
        excluded_players = set(exclude_player_ids or [])
        blacklisted = set(blacklist_coords or [])
        allowed_cats = set(allowed_categories or ["stagnant", "regressive", "residual", "unknown", "growing"])
        results: List[Dict[str, Any]] = []

        for row in rows:
            p_id = row["player_id"]
            if not include_barbarians and p_id == 0:
                continue

            if p_id in excluded_players:
                continue

            v_x = row["x"]
            v_y = row["y"]
            coords_str = f"{v_x}|{v_y}"
            if coords_str in blacklisted:
                continue

            dist = math.hypot(v_x - origin_x, v_y - origin_y)
            if dist > max_distance:
                continue

            v_points = row["village_points"]
            if v_points < min_points or v_points > max_points:
                continue

            ally_id = row["ally_id"]
            ally_members = row["ally_members_count"]

            if ally_id in excluded_allies:
                continue

            # Filtro de Tribo: Sem tribo ou tribo de 1 membro
            if only_tribeless:
                if ally_id != 0:
                    if not (include_single_member_tribes and ally_members <= 1):
                        continue

            curr_player_pts = row["player_points"]
            past_player_pts = row["past_player_points"]

            # Cálculo de ΔP (Variação de Pontos do Jogador)
            if past_player_pts is not None and past_snap_id != latest_snap_id:
                delta_p = curr_player_pts - past_player_pts
                has_history = True
            else:
                delta_p = 0
                has_history = False

            # Classificação categórica rigorosa de inatividade
            if not has_history:
                cat = "stagnant" if delta_p == 0 else "unknown"
                cat_label = "Sem Histórico Prévio"
            elif delta_p < 0:
                cat = "regressive"
                cat_label = "Regressão / Limpeza"
            elif delta_p == 0:
                cat = "stagnant"
                cat_label = "Estagnação Total"
            elif delta_p <= max_points_growth:
                cat = "residual"
                cat_label = "Crescimento Residual"
            else:
                cat = "growing"
                cat_label = "Em Crescimento"

            if cat not in allowed_cats:
                continue

            # Tempos de marcha estimados (Cavalaria Leve = 10 min/campo, Espião = 9 min/campo)
            travel_lc_sec = int(round(dist * 600))
            travel_spy_sec = int(round(dist * 540))

            results.append({
                "village_id": row["village_id"],
                "village_name": row["village_name"],
                "x": v_x,
                "y": v_y,
                "coords": coords_str,
                "player_id": p_id,
                "player_name": row["player_name"],
                "player_points": curr_player_pts,
                "player_villages_count": row["player_villages_count"],
                "ally_id": ally_id,
                "ally_name": row["ally_name"],
                "ally_tag": row["ally_tag"],
                "ally_members_count": ally_members,
                "village_points": v_points,
                "past_player_points": past_player_pts if past_player_pts is not None else curr_player_pts,
                "delta_points": delta_p,
                "days_diff": round(actual_days_diff, 1),
                "inactivity_category": cat,
                "inactivity_label": cat_label,
                "distance": round(dist, 2),
                "travel_time_lc_seconds": travel_lc_sec,
                "travel_time_spy_seconds": travel_spy_sec,
                "travel_time_lc_str": f"{travel_lc_sec // 60}m {travel_lc_sec % 60}s",
                "travel_time_spy_str": f"{travel_spy_sec // 60}m {travel_spy_sec % 60}s",
            })

        # Ordenar alvos: prioritariamente por inatividade (regressive/stagnant/residual) e por distância euclidiana
        priority_order = {"regressive": 0, "stagnant": 1, "residual": 2, "unknown": 3, "growing": 4}
        results.sort(key=lambda item: (priority_order.get(item["inactivity_category"], 5), item["distance"]))

        return results[:limit]

    def get_players_in_radius(
        self,
        world: str,
        origin_x: int,
        origin_y: int,
        max_distance: float = 25.0,
    ) -> List[Dict[str, Any]]:
        """
        Retorna todos os jogadores com pelo menos uma aldeia num raio de max_distance campos.
        Calcula a aldeia mais próxima e a distância mínima para cada jogador.
        """
        latest_snap = self.get_latest_snapshot(world)
        if not latest_snap:
            return []

        snap_id = latest_snap["id"]
        box_r = int(math.ceil(max_distance))
        min_x, max_x = origin_x - box_r, origin_x + box_r
        min_y, max_y = origin_y - box_r, origin_y + box_r

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    v.village_id, v.name AS village_name, v.x, v.y, v.points AS village_points,
                    p.player_id, p.name AS player_name, p.points AS player_points,
                    p.villages_count, p.rank AS player_rank,
                    COALESCE(a.ally_id, 0) AS ally_id,
                    COALESCE(a.name, 'Sem Tribo') AS ally_name,
                    COALESCE(a.tag, '') AS ally_tag
                FROM world_villages v
                JOIN world_players p ON p.snapshot_id = v.snapshot_id AND p.player_id = v.player_id
                LEFT JOIN world_allies a ON a.snapshot_id = v.snapshot_id AND a.ally_id = p.ally_id
                WHERE v.snapshot_id = ?
                  AND v.player_id > 0
                  AND v.x BETWEEN ? AND ?
                  AND v.y BETWEEN ? AND ?
                """,
                (snap_id, min_x, max_x, min_y, max_y),
            )
            rows = cursor.fetchall()

        players_map: Dict[int, Dict[str, Any]] = {}
        for r in rows:
            v_x, v_y = r["x"], r["y"]
            dist = math.sqrt((v_x - origin_x) ** 2 + (v_y - origin_y) ** 2)
            if dist > max_distance:
                continue

            p_id = r["player_id"]
            if p_id not in players_map:
                players_map[p_id] = {
                    "player_id": p_id,
                    "player_name": r["player_name"],
                    "player_points": r["player_points"],
                    "villages_count": r["villages_count"],
                    "player_rank": r["player_rank"],
                    "ally_id": r["ally_id"],
                    "ally_name": r["ally_name"],
                    "ally_tag": r["ally_tag"],
                    "nearest_village_id": r["village_id"],
                    "nearest_village_name": r["village_name"],
                    "nearest_coords": f"{v_x}|{v_y}",
                    "nearest_distance": round(dist, 2),
                    "villages_in_radius": [],
                }
            elif dist < players_map[p_id]["nearest_distance"]:
                players_map[p_id]["nearest_village_id"] = r["village_id"]
                players_map[p_id]["nearest_village_name"] = r["village_name"]
                players_map[p_id]["nearest_coords"] = f"{v_x}|{v_y}"
                players_map[p_id]["nearest_distance"] = round(dist, 2)

            players_map[p_id]["villages_in_radius"].append({
                "village_id": r["village_id"],
                "village_name": r["village_name"],
                "coords": f"{v_x}|{v_y}",
                "distance": round(dist, 2),
                "points": r["village_points"],
            })

        result = list(players_map.values())
        result.sort(key=lambda x: x["nearest_distance"])
        return result

    def get_player_timeline(
        self,
        world: str,
        player_id: int,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Retorna a série temporal cronológica de medições de um jogador específico
        gravadas ao longo de sucessivos snapshots da base de dados.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    p.snapshot_id, p.timestamp, p.points, p.villages_count, p.rank,
                    p.ally_id, COALESCE(a.tag, '') AS ally_tag,
                    s.datetime_iso
                FROM world_players p
                JOIN world_snapshots s ON s.id = p.snapshot_id
                LEFT JOIN world_allies a ON a.snapshot_id = p.snapshot_id AND a.ally_id = p.ally_id
                WHERE p.world = ? AND p.player_id = ?
                ORDER BY p.timestamp ASC
                LIMIT ?
                """,
                (world.lower().strip(), player_id, limit),
            )
            rows = cursor.fetchall()

        timeline = []
        prev_points = None
        prev_time = None
        for r in rows:
            pts = r["points"]
            ts = r["timestamp"]
            delta = (pts - prev_points) if prev_points is not None else 0
            time_diff_h = ((ts - prev_time) / 3600.0) if prev_time is not None else 0.0

            timeline.append({
                "snapshot_id": r["snapshot_id"],
                "timestamp": ts,
                "datetime_iso": r["datetime_iso"],
                "date_human": datetime.fromtimestamp(ts).strftime("%d/%m %H:%M"),
                "points": pts,
                "villages_count": r["villages_count"],
                "rank": r["rank"],
                "ally_tag": r["ally_tag"],
                "delta": delta,
                "hours_diff": round(time_diff_h, 1),
            })
            prev_points = pts
            prev_time = ts

        return timeline

    def get_radius_players_evolution(
        self,
        world: str,
        origin_x: int,
        origin_y: int,
        max_distance: float = 25.0,
        limit: int = 100,
        reference_timestamp: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Calcula a evolução estatística completa de todos os jogadores vizinhos no raio de X campos.
        Compara o snapshot atual contra medições passadas (24h, 3 dias, 7 dias).
        """
        players = self.get_players_in_radius(world, origin_x, origin_y, max_distance)
        if not players:
            return []

        latest_snap = self.get_latest_snapshot(world)
        now_ts = reference_timestamp or (latest_snap["timestamp"] if latest_snap else time.time())

        snap_24h = self.get_snapshot_at_or_before(world, now_ts - (0.8 * 86400.0))
        snap_3d = self.get_snapshot_at_or_before(world, now_ts - (2.5 * 86400.0))
        snap_7d = self.get_snapshot_at_or_before(world, now_ts - (6.0 * 86400.0))

        # Se não houver snapshot exatamente de 7 dias, faz fallback para o mais antigo disponível
        all_snaps = self.get_all_snapshots(world)
        if len(all_snaps) > 1:
            oldest_snap = all_snaps[-1]
            if not snap_7d and oldest_snap["id"] != (latest_snap["id"] if latest_snap else -1):
                snap_7d = oldest_snap
            if not snap_24h and oldest_snap["id"] != (latest_snap["id"] if latest_snap else -1):
                snap_24h = oldest_snap

        # Obter dados históricos em lote se os snapshots existirem
        hist_24h: Dict[int, int] = {}
        hist_3d: Dict[int, int] = {}
        hist_7d: Dict[int, int] = {}

        player_ids = [p["player_id"] for p in players]
        placeholders = ",".join("?" for _ in player_ids)

        with self._get_connection() as conn:
            if snap_24h:
                c = conn.execute(
                    f"SELECT player_id, points FROM world_players WHERE snapshot_id = ? AND player_id IN ({placeholders})",
                    [snap_24h["id"]] + player_ids,
                )
                hist_24h = {r["player_id"]: r["points"] for r in c.fetchall()}

            if snap_3d:
                c = conn.execute(
                    f"SELECT player_id, points FROM world_players WHERE snapshot_id = ? AND player_id IN ({placeholders})",
                    [snap_3d["id"]] + player_ids,
                )
                hist_3d = {r["player_id"]: r["points"] for r in c.fetchall()}

            if snap_7d:
                c = conn.execute(
                    f"SELECT player_id, points FROM world_players WHERE snapshot_id = ? AND player_id IN ({placeholders})",
                    [snap_7d["id"]] + player_ids,
                )
                hist_7d = {r["player_id"]: r["points"] for r in c.fetchall()}

        evolution_list: List[Dict[str, Any]] = []
        for p in players:
            p_id = p["player_id"]
            curr_pts = p["player_points"]

            pts_24h = hist_24h.get(p_id, curr_pts)
            pts_3d = hist_3d.get(p_id, curr_pts)
            pts_7d = hist_7d.get(p_id, curr_pts)

            delta_24h = curr_pts - pts_24h
            delta_3d = curr_pts - pts_3d
            delta_7d = curr_pts - pts_7d

            # Classificação de tendência comportamental
            if delta_7d < 0 or delta_24h < -50:
                trend = "regressive"
                trend_label = "📉 Em Queda / Perda"
                trend_color = "var(--neon-rose)"
            elif delta_7d == 0 and delta_24h == 0 and snap_7d is not None:
                trend = "inactive"
                trend_label = "💀 Inativo Total"
                trend_color = "var(--text-muted)"
            elif delta_7d <= 30 and snap_3d is not None:
                trend = "stagnant"
                trend_label = "⏸️ Estagnado"
                trend_color = "var(--neon-amber)"
            elif delta_24h > 400 or (curr_pts > 0 and (delta_24h / curr_pts) > 0.15):
                trend = "accelerating"
                trend_label = "🚀 Crescimento Acelerado"
                trend_color = "var(--neon-emerald)"
            else:
                trend = "growing"
                trend_label = "📈 Ativo Normal"
                trend_color = "var(--neon-cyan)"

            # Últimos pontos para sparkline/micro-gráfico
            timeline_preview = self.get_player_timeline(world, p_id, limit=7)
            points_sparkline = [entry["points"] for entry in timeline_preview] if timeline_preview else [curr_pts]

            evolution_list.append({
                **p,
                "delta_24h": delta_24h,
                "delta_3d": delta_3d,
                "delta_7d": delta_7d,
                "trend": trend,
                "trend_label": trend_label,
                "trend_color": trend_color,
                "points_sparkline": points_sparkline,
                "has_history": len(timeline_preview) > 1,
            })

        return evolution_list[:limit]


