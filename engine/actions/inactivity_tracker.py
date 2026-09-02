"""
Tribal Wars Mobile Automation Engine - Inactivity Tracker (Radar de Inativos & Inno-Farming)
Módulo de análise de séries temporais de pontos (ΔP), cálculo dinâmico de tempos de viagem,
formatação de impacto de tropas e exportação rápida de alvos para a esteira de Farm.
"""

from dataclasses import dataclass, field
from datetime import datetime
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from engine.actions.place import UnitsCount
from engine.storage.world_database import WorldDatabase

logger = logging.getLogger("TribalWarsBot.InactivityTracker")


# Velocidade base de cada unidade em segundos por campo (Velocidade 1.0x)
UNIT_BASE_SPEEDS_SECONDS_PER_FIELD: Dict[str, int] = {
    "spy": 540,        # 9 min / campo
    "light": 600,      # 10 min / campo
    "marcher": 600,    # 10 min / campo
    "heavy": 660,      # 11 min / campo
    "knight": 600,     # 10 min / campo
    "axe": 1080,       # 18 min / campo
    "spear": 1080,     # 18 min / campo
    "archer": 1080,    # 18 min / campo
    "sword": 1320,     # 22 min / campo
    "ram": 1800,       # 30 min / campo
    "catapult": 1800,  # 30 min / campo
    "snob": 2100,      # 35 min / campo
}


def format_duration_seconds(seconds: int) -> str:
    """Formata segundos em HH:MM:SS ou MM:SS."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def calculate_unit_travel_times(
    distance: float,
    world_speed: float = 1.0,
    unit_speed: float = 1.0,
    base_timestamp: Optional[float] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Calcula com precisão matemática os tempos de marcha e horário de impacto estimado (ETA)
    para todas as unidades militares a partir da distância euclidiana.
    """
    now_ts = base_timestamp or time.time()
    effective_factor = max(0.01, world_speed * unit_speed)
    results: Dict[str, Dict[str, Any]] = {}

    for unit, base_sec in UNIT_BASE_SPEEDS_SECONDS_PER_FIELD.items():
        dur_sec = int(round((distance * base_sec) / effective_factor))
        eta_ts = now_ts + dur_sec
        eta_dt = datetime.fromtimestamp(eta_ts)
        results[unit] = {
            "duration_seconds": dur_sec,
            "duration_str": format_duration_seconds(dur_sec),
            "eta_timestamp": eta_ts,
            "eta_str": eta_dt.strftime("%H:%M:%S"),
            "eta_full_str": eta_dt.strftime("%d/%m %H:%M:%S"),
        }

    return results


@dataclass
class InactiveTarget:
    """Representação de um alvo inativo analisado com métricas completas."""

    village_id: int
    village_name: str
    x: int
    y: int
    coords: str
    player_id: int
    player_name: str
    player_points: int
    player_villages_count: int
    ally_id: int
    ally_name: str
    ally_tag: str
    ally_members_count: int = 0
    village_points: int = 0
    past_player_points: int = 0
    delta_points: int = 0
    days_diff: float = 0.0
    inactivity_category: str = "stagnant"  # "stagnant", "regressive", "residual", "growing"
    inactivity_label: str = ""
    distance: float = 0.0
    travel_time_lc_seconds: int = 0
    travel_time_spy_seconds: int = 0
    travel_time_lc_str: str = ""
    travel_time_spy_str: str = ""
    eta_lc_str: str = ""
    eta_spy_str: str = ""

    @property
    def is_highly_inactive(self) -> bool:
        """Retorna True se o alvo for estagnado ou regressivo (alvo ideal para farm)."""
        return self.inactivity_category in ("stagnant", "regressive")

    @property
    def coords_tuple(self) -> Tuple[int, int]:
        return (self.x, self.y)


@dataclass
class InactivityFilterConfig:
    """Configuração dos filtros táticos para seleção de alvos inativos."""

    max_distance: float = 25.0
    days_window: float = 7.0
    max_points_growth: int = 30
    min_points: int = 200
    max_points: int = 6000
    only_tribeless: bool = False
    include_single_member_tribes: bool = True
    include_barbarians: bool = False
    exclude_ally_ids: List[int] = field(default_factory=list)
    exclude_player_ids: List[int] = field(default_factory=list)
    blacklist_coords: List[str] = field(default_factory=list)
    allowed_categories: List[str] = field(
        default_factory=lambda: ["stagnant", "regressive", "residual"]
    )
    limit: int = 200


@dataclass
class InactivityReport:
    """Relatório consolidado de varredura de alvos inativos."""

    world: str
    origin_coords: str
    origin_x: int
    origin_y: int
    scan_radius: float
    days_window: float
    total_targets_found: int
    stagnant_count: int
    regressive_count: int
    residual_count: int
    targets: List[InactiveTarget] = field(default_factory=list)


class InactivityTracker:
    """
    Rastreador de inatividade que processa os snapshots da base de dados e devolve alvos classificados
    com suporte a filtros táticos refinados e exportação de comandos de ataque.
    """

    def __init__(self, db: Optional[WorldDatabase] = None):
        self.db = db or WorldDatabase()

    def scan_inactives(
        self,
        world: str,
        origin_x: int,
        origin_y: int,
        filter_config: Optional[InactivityFilterConfig] = None,
        max_distance: Optional[float] = None,
        days_window: Optional[float] = None,
        max_points_growth: Optional[int] = None,
        min_points: Optional[int] = None,
        max_points: Optional[int] = None,
        exclude_ally_ids: Optional[List[int]] = None,
        exclude_player_ids: Optional[List[int]] = None,
        blacklist_coords: Optional[List[str]] = None,
        only_tribeless: Optional[bool] = None,
        include_single_member_tribes: Optional[bool] = None,
        include_barbarians: Optional[bool] = None,
        allowed_categories: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> InactivityReport:
        """
        Executa a varredura geoespacial e analítica de inatividade em torno da aldeia de origem,
        respeitando todos os critérios táticos e calculando os tempos de viagem.
        """
        cfg = filter_config or InactivityFilterConfig()

        f_max_dist = max_distance if max_distance is not None else cfg.max_distance
        f_days = days_window if days_window is not None else cfg.days_window
        f_growth = max_points_growth if max_points_growth is not None else cfg.max_points_growth
        f_min_pts = min_points if min_points is not None else cfg.min_points
        f_max_pts = max_points if max_points is not None else cfg.max_points
        f_excl_ally = exclude_ally_ids if exclude_ally_ids is not None else cfg.exclude_ally_ids
        f_excl_player = exclude_player_ids if exclude_player_ids is not None else cfg.exclude_player_ids
        f_blacklist = blacklist_coords if blacklist_coords is not None else cfg.blacklist_coords
        f_tribeless = only_tribeless if only_tribeless is not None else cfg.only_tribeless
        f_single_tribe = (
            include_single_member_tribes
            if include_single_member_tribes is not None
            else cfg.include_single_member_tribes
        )
        f_barbs = include_barbarians if include_barbarians is not None else cfg.include_barbarians
        f_cats = allowed_categories if allowed_categories is not None else cfg.allowed_categories
        f_limit = limit if limit is not None else cfg.limit

        raw_targets = self.db.get_inactivity_analysis(
            world=world,
            origin_x=origin_x,
            origin_y=origin_y,
            max_distance=f_max_dist,
            days_window=f_days,
            max_points_growth=f_growth,
            min_points=f_min_pts,
            max_points=f_max_pts,
            exclude_ally_ids=f_excl_ally,
            exclude_player_ids=f_excl_player,
            blacklist_coords=f_blacklist,
            only_tribeless=f_tribeless,
            include_single_member_tribes=f_single_tribe,
            include_barbarians=f_barbs,
            allowed_categories=f_cats,
            limit=f_limit,
        )

        now_ts = time.time()
        targets: List[InactiveTarget] = []
        stagnant_count = 0
        regressive_count = 0
        residual_count = 0

        for r in raw_targets:
            dist = r["distance"]
            timing_map = calculate_unit_travel_times(dist, base_timestamp=now_ts)
            lc_info = timing_map.get("light", {})
            spy_info = timing_map.get("spy", {})

            t = InactiveTarget(
                village_id=r["village_id"],
                village_name=r["village_name"],
                x=r["x"],
                y=r["y"],
                coords=r["coords"],
                player_id=r["player_id"],
                player_name=r["player_name"],
                player_points=r["player_points"],
                player_villages_count=r["player_villages_count"],
                ally_id=r["ally_id"],
                ally_name=r["ally_name"],
                ally_tag=r["ally_tag"],
                ally_members_count=r.get("ally_members_count", 0),
                village_points=r["village_points"],
                past_player_points=r["past_player_points"],
                delta_points=r["delta_points"],
                days_diff=r["days_diff"],
                inactivity_category=r["inactivity_category"],
                inactivity_label=r["inactivity_label"],
                distance=dist,
                travel_time_lc_seconds=lc_info.get("duration_seconds", r["travel_time_lc_seconds"]),
                travel_time_spy_seconds=spy_info.get("duration_seconds", r["travel_time_spy_seconds"]),
                travel_time_lc_str=lc_info.get("duration_str", r["travel_time_lc_str"]),
                travel_time_spy_str=spy_info.get("duration_str", r["travel_time_spy_str"]),
                eta_lc_str=lc_info.get("eta_str", ""),
                eta_spy_str=spy_info.get("eta_str", ""),
            )
            if t.inactivity_category == "stagnant":
                stagnant_count += 1
            elif t.inactivity_category == "regressive":
                regressive_count += 1
            elif t.inactivity_category == "residual":
                residual_count += 1

            targets.append(t)

        logger.info(
            f"[{world}] Varredura de inativos concluída em ({origin_x}|{origin_y}, Raio: {f_max_dist}): "
            f"{len(targets)} alvos encontrados ({stagnant_count} estagnados, {regressive_count} regressivos, {residual_count} residuais)."
        )

        return InactivityReport(
            world=world,
            origin_coords=f"{origin_x}|{origin_y}",
            origin_x=origin_x,
            origin_y=origin_y,
            scan_radius=f_max_dist,
            days_window=f_days,
            total_targets_found=len(targets),
            stagnant_count=stagnant_count,
            regressive_count=regressive_count,
            residual_count=residual_count,
            targets=targets,
        )

    def export_targets_to_custom_farm(
        self,
        targets: List[InactiveTarget],
        current_custom_targets: Optional[List[Tuple[int, int]]] = None,
    ) -> List[Tuple[int, int]]:
        """
        Exporta as coordenadas dos alvos inativos selecionados para o formato de alvos customizados de farm,
        unificando e preservando a ordem sem duplicações.
        """
        existing = list(current_custom_targets or [])
        seen: Set[Tuple[int, int]] = set(existing)

        for t in targets:
            coords = (t.x, t.y)
            if coords not in seen:
                seen.add(coords)
                existing.append(coords)

        return existing

    def create_attack_payload(
        self,
        target: InactiveTarget,
        troops: UnitsCount,
        is_attack: bool = True,
    ) -> Dict[str, Any]:
        """
        Gera a estrutura de payload de ataque/apoio para a Praça de Reunião pronta para disparo.
        """
        data = troops.to_dict()
        data["x"] = str(target.x)
        data["y"] = str(target.y)
        data["target_village_id"] = str(target.village_id)
        data["target_player_id"] = str(target.player_id)
        data["action_type"] = "attack" if is_attack else "support"
        return data

    def get_players_evolution_report(
        self,
        world: str,
        origin_x: int,
        origin_y: int,
        max_distance: float = 25.0,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Gera relatório consolidado da evolução temporal de todos os jogadores num raio de X campos.
        """
        players_evolution = self.db.get_radius_players_evolution(
            world=world,
            origin_x=origin_x,
            origin_y=origin_y,
            max_distance=max_distance,
            limit=limit,
        )

        counts = {
            "accelerating": 0,
            "growing": 0,
            "stagnant": 0,
            "regressive": 0,
            "inactive": 0,
        }
        for p in players_evolution:
            t = p.get("trend", "growing")
            counts[t] = counts.get(t, 0) + 1

        return {
            "world": world,
            "origin_coords": f"{origin_x}|{origin_y}",
            "radius": max_distance,
            "total_players_in_radius": len(players_evolution),
            "counts": counts,
            "players": players_evolution,
        }

    def get_player_timeline(
        self,
        world: str,
        player_id: int,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Recupera a linha do tempo histórica de um jogador.
        """
        return self.db.get_player_timeline(world=world, player_id=player_id, limit=limit)

