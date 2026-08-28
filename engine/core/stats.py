"""
Tribal Wars Mobile Automation Engine - Stats & Efficiency Tracker
Registo persistente de recursos farmados, tropas recrutadas, comandos enviados
e cálculos de rendimento horário/diário com agregação temporal em baldes.
"""

from dataclasses import asdict, dataclass, field
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("TribalWars.Stats")


@dataclass
class LootEvent:
    """Registo de um evento de saque/farm."""
    timestamp: float
    village_id: int
    target_x: int
    target_y: int
    wood: int = 0
    stone: int = 0
    iron: int = 0
    total: int = 0
    wall: int = 0
    losses: bool = False
    village_name: str = ""

    def __post_init__(self):
        if self.total == 0:
            self.total = self.wood + self.stone + self.iron

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RecruitmentEvent:
    """Registo de um evento de recrutamento de tropas."""
    timestamp: float
    village_id: int
    unit: str
    count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BuildingEvent:
    """Registo de um evento de ordem de construção."""
    timestamp: float
    village_id: int
    building: str
    target_level: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CommandEvent:
    """Registo de um comando enviado (ataque, farm, apoio)."""
    timestamp: float
    command_type: str  # "farm", "attack", "support"
    target_coords: str  # "500|500"
    units: Dict[str, int] = field(default_factory=dict)
    success: bool = True
    response_time_ms: int = 0
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HourlyBucket:
    """Agregação de métricas numa janela de 1 hora."""
    hour_key: str  # "YYYY-MM-DD HH:00"
    timestamp: float
    wood: int = 0
    stone: int = 0
    iron: int = 0
    total: int = 0
    attacks_count: int = 0
    attacks_successful: int = 0
    villages_farmed: int = 0
    troops_recruited: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StatsTracker:
    """
    Rastreador e agregador de estatísticas de eficiência para uma conta/mundo.
    Mantém histórico temporal em baldes horários (últimas 48h) e diários (últimos 30 dias),
    além de logs recentes de eventos.
    """

    def __init__(self, world: str = "pt117", cache_dir: Optional[Path] = None):
        self.world = world
        self.cache_dir = cache_dir or Path(".stats_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / f"stats_{self.world}.json"

        # Totais acumulados globais
        self.total_wood: int = 0
        self.total_stone: int = 0
        self.total_iron: int = 0
        self.total_attacks_sent: int = 0
        self.total_attacks_successful: int = 0
        self.total_villages_farmed: int = 0
        self.troops_recruited_by_unit: Dict[str, int] = {}
        self.buildings_constructed_count: int = 0

        # Baldes temporais horários: "YYYY-MM-DD HH:00" -> HourlyBucket
        self.hourly_buckets: Dict[str, HourlyBucket] = {}
        
        # Histórico recente de eventos (últimos 100)
        self.recent_loot_events: List[LootEvent] = []
        self.recent_commands: List[CommandEvent] = []
        
        self.created_at: float = time.time()
        self.last_updated: float = time.time()

        self._load_from_disk()

    @property
    def total_looted(self) -> int:
        return self.total_wood + self.total_stone + self.total_iron

    @property
    def success_rate(self) -> float:
        if self.total_attacks_sent == 0:
            return 100.0
        return round((self.total_attacks_successful / self.total_attacks_sent) * 100.0, 1)

    def _get_hour_key(self, ts: float) -> Tuple[str, float]:
        """Calcula a chave horária e o timestamp base da hora."""
        gm = time.gmtime(ts)
        hour_key = time.strftime("%Y-%m-%d %H:00", gm)
        base_ts = time.mktime(time.strptime(hour_key, "%Y-%m-%d %H:00"))
        return hour_key, base_ts

    def _get_or_create_hourly_bucket(self, ts: float) -> HourlyBucket:
        hour_key, base_ts = self._get_hour_key(ts)
        if hour_key not in self.hourly_buckets:
            self.hourly_buckets[hour_key] = HourlyBucket(
                hour_key=hour_key,
                timestamp=base_ts,
            )
        return self.hourly_buckets[hour_key]

    def record_farm_loot(
        self,
        wood: int = 0,
        stone: int = 0,
        iron: int = 0,
        target_x: int = 0,
        target_y: int = 0,
        village_id: int = 0,
        wall: int = 0,
        losses: bool = False,
        village_name: str = "",
        timestamp: Optional[float] = None,
    ) -> LootEvent:
        """Regista um saque de farm e atualiza baldes e totais."""
        ts = timestamp or time.time()
        total = wood + stone + iron
        event = LootEvent(
            timestamp=ts,
            village_id=village_id,
            target_x=target_x,
            target_y=target_y,
            wood=wood,
            stone=stone,
            iron=iron,
            total=total,
            wall=wall,
            losses=losses,
            village_name=village_name,
        )

        # Atualiza totais globais
        self.total_wood += wood
        self.total_stone += stone
        self.total_iron += iron
        self.total_villages_farmed += 1

        # Atualiza balde horário
        bucket = self._get_or_create_hourly_bucket(ts)
        bucket.wood += wood
        bucket.stone += stone
        bucket.iron += iron
        bucket.total += total
        bucket.villages_farmed += 1

        # Mantém histórico recente (máx 100)
        self.recent_loot_events.insert(0, event)
        if len(self.recent_loot_events) > 100:
            self.recent_loot_events = self.recent_loot_events[:100]

        self.last_updated = ts
        self._prune_and_save()
        return event

    def record_recruitment(
        self,
        unit: str,
        count: int,
        village_id: int = 0,
        timestamp: Optional[float] = None,
    ) -> RecruitmentEvent:
        """Regista tropas recrutadas."""
        ts = timestamp or time.time()
        event = RecruitmentEvent(
            timestamp=ts,
            village_id=village_id,
            unit=unit,
            count=count,
        )

        self.troops_recruited_by_unit[unit] = (
            self.troops_recruited_by_unit.get(unit, 0) + count
        )

        bucket = self._get_or_create_hourly_bucket(ts)
        bucket.troops_recruited += count

        self.last_updated = ts
        self._prune_and_save()
        return event

    def record_building(
        self,
        building: str,
        target_level: int = 1,
        village_id: int = 0,
        timestamp: Optional[float] = None,
    ) -> BuildingEvent:
        """Regista uma evolução de edifício iniciada/concluída."""
        ts = timestamp or time.time()
        event = BuildingEvent(
            timestamp=ts,
            village_id=village_id,
            building=building,
            target_level=target_level,
        )
        self.buildings_constructed_count += 1
        self.last_updated = ts
        self._prune_and_save()
        return event

    def record_building_upgrade(
        self,
        building: str = "main",
        target_level: int = 1,
        village_id: int = 0,
        from_level: int = 0,
        to_level: Optional[int] = None,
        timestamp: Optional[float] = None,
    ) -> BuildingEvent:
        """Alias para registo de evolução de edifício."""
        lvl = to_level if to_level is not None else target_level
        return self.record_building(
            building=building,
            target_level=lvl,
            village_id=village_id,
            timestamp=timestamp,
        )

    def record_command(
        self,
        command_type: str,
        target_coords: str,
        units: Optional[Dict[str, int]] = None,
        success: bool = True,
        details: str = "",
        timestamp: Optional[float] = None,
    ) -> CommandEvent:
        """Regista um comando militar enviado."""
        ts = timestamp or time.time()
        event = CommandEvent(
            timestamp=ts,
            command_type=command_type,
            target_coords=target_coords,
            units=units or {},
            success=success,
            details=details,
        )

        self.total_attacks_sent += 1
        if success:
            self.total_attacks_successful += 1

        bucket = self._get_or_create_hourly_bucket(ts)
        bucket.attacks_count += 1
        if success:
            bucket.attacks_successful += 1

        self.recent_commands.insert(0, event)
        if len(self.recent_commands) > 100:
            self.recent_commands = self.recent_commands[:100]

        self.last_updated = ts
        self._prune_and_save()
        return event

    def get_summary(self) -> Dict[str, Any]:
        """Retorna sumário consolidado de KPIs e métricas de rendimento."""
        now = time.time()
        
        # Rendimento nas últimas 24 horas
        last_24h_ts = now - (24 * 3600)
        loot_24h_wood = 0
        loot_24h_stone = 0
        loot_24h_iron = 0
        attacks_24h = 0
        villages_farmed_24h = 0

        # Rendimento na última hora
        last_1h_ts = now - 3600
        loot_1h_total = 0

        for bucket in self.hourly_buckets.values():
            if bucket.timestamp >= last_24h_ts:
                loot_24h_wood += bucket.wood
                loot_24h_stone += bucket.stone
                loot_24h_iron += bucket.iron
                attacks_24h += bucket.attacks_count
                villages_farmed_24h += bucket.villages_farmed
            if bucket.timestamp >= last_1h_ts:
                loot_1h_total += bucket.total

        total_24h = loot_24h_wood + loot_24h_stone + loot_24h_iron
        hourly_rate_24h = round(total_24h / 24.0, 1)

        total_recruited = sum(self.troops_recruited_by_unit.values())

        return {
            "world": self.world,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "totals_all_time": {
                "wood": self.total_wood,
                "stone": self.total_stone,
                "iron": self.total_iron,
                "total": self.total_looted,
                "villages_farmed": self.total_villages_farmed,
                "attacks_sent": self.total_attacks_sent,
                "attacks_successful": self.total_attacks_successful,
                "attacks_failed": max(0, self.total_attacks_sent - self.total_attacks_successful),
                "success_rate": self.success_rate,
                "troops_recruited": total_recruited,
                "buildings_constructed": self.buildings_constructed_count,
            },
            "last_24h": {
                "wood": loot_24h_wood,
                "stone": loot_24h_stone,
                "iron": loot_24h_iron,
                "total": total_24h,
                "villages_farmed": villages_farmed_24h,
                "attacks_sent": attacks_24h,
                "hourly_rate": hourly_rate_24h,
            },
            "current_rate_1h": {
                "total": loot_1h_total,
                "hourly_rate": loot_1h_total,
            },
            "recruitment_by_unit": self.troops_recruited_by_unit,
        }

    def get_history(self, hours: int = 24, days: int = 7) -> Dict[str, Any]:
        """
        Retorna séries temporais horárias e diárias para renderização de gráficos.
        Garante baldes sequenciais preenchidos com 0 caso não haja atividade.
        """
        now = time.time()
        
        # 1. Baldes Horários Sequenciais (ex: últimas 24 horas)
        hourly_series: List[Dict[str, Any]] = []
        curr_hour_ts = (int(now) // 3600) * 3600

        for i in range(hours - 1, -1, -1):
            ts = curr_hour_ts - (i * 3600)
            gm = time.gmtime(ts)
            h_key = time.strftime("%Y-%m-%d %H:00", gm)
            display_hour = time.strftime("%H:00", gm)
            display_label = time.strftime("%d/%m %H:00", gm)

            bucket = self.hourly_buckets.get(h_key)
            if bucket:
                hourly_series.append({
                    "key": h_key,
                    "label": display_label,
                    "hour": display_hour,
                    "timestamp": ts,
                    "wood": bucket.wood,
                    "stone": bucket.stone,
                    "iron": bucket.iron,
                    "total": bucket.total,
                    "attacks": bucket.attacks_count,
                    "villages": bucket.villages_farmed,
                })
            else:
                hourly_series.append({
                    "key": h_key,
                    "label": display_label,
                    "hour": display_hour,
                    "timestamp": ts,
                    "wood": 0,
                    "stone": 0,
                    "iron": 0,
                    "total": 0,
                    "attacks": 0,
                    "villages": 0,
                })

        # 2. Baldes Diários Agregados (ex: últimos 7 dias)
        daily_map: Dict[str, Dict[str, Any]] = {}
        for b in self.hourly_buckets.values():
            day_key = b.hour_key[:10]  # "YYYY-MM-DD"
            if day_key not in daily_map:
                daily_map[day_key] = {
                    "date": day_key,
                    "wood": 0,
                    "stone": 0,
                    "iron": 0,
                    "total": 0,
                    "attacks": 0,
                    "villages": 0,
                }
            daily_map[day_key]["wood"] += b.wood
            daily_map[day_key]["stone"] += b.stone
            daily_map[day_key]["iron"] += b.iron
            daily_map[day_key]["total"] += b.total
            daily_map[day_key]["attacks"] += b.attacks_count
            daily_map[day_key]["villages"] += b.villages_farmed

        daily_series: List[Dict[str, Any]] = []
        curr_day_ts = (int(now) // 86400) * 86400

        for d in range(days - 1, -1, -1):
            ts = curr_day_ts - (d * 86400)
            gm = time.gmtime(ts)
            d_key = time.strftime("%Y-%m-%d", gm)
            display_day = time.strftime("%d/%m", gm)

            d_data = daily_map.get(d_key, {
                "date": d_key,
                "wood": 0,
                "stone": 0,
                "iron": 0,
                "total": 0,
                "attacks": 0,
                "villages": 0,
            })
            d_data_copy = dict(d_data)
            d_data_copy["label"] = display_day
            d_data_copy["timestamp"] = ts
            daily_series.append(d_data_copy)

        return {
            "world": self.world,
            "hourly": hourly_series,
            "daily": daily_series,
            "recent_loot": [e.to_dict() for e in self.recent_loot_events[:30]],
            "recent_commands": [c.to_dict() for c in self.recent_commands[:30]],
        }

    def reset_stats(self) -> None:
        """Reinicia todas as métricas e remove o ficheiro de cache."""
        self.total_wood = 0
        self.total_stone = 0
        self.total_iron = 0
        self.total_attacks_sent = 0
        self.total_attacks_successful = 0
        self.total_villages_farmed = 0
        self.troops_recruited_by_unit = {}
        self.buildings_constructed_count = 0
        self.hourly_buckets = {}
        self.recent_loot_events = []
        self.recent_commands = []
        self.created_at = time.time()
        self.last_updated = time.time()
        self._save_to_disk()

    def _prune_and_save(self) -> None:
        """Descarta baldes com mais de 30 dias para manter o ficheiro leve e grava."""
        cutoff_ts = time.time() - (30 * 86400)
        self.hourly_buckets = {
            k: v for k, v in self.hourly_buckets.items() if v.timestamp >= cutoff_ts
        }
        self._save_to_disk()

    def _save_to_disk(self) -> None:
        """Grava estado atómico em disco."""
        try:
            data = {
                "world": self.world,
                "created_at": self.created_at,
                "last_updated": self.last_updated,
                "total_wood": self.total_wood,
                "total_stone": self.total_stone,
                "total_iron": self.total_iron,
                "total_attacks_sent": self.total_attacks_sent,
                "total_attacks_successful": self.total_attacks_successful,
                "total_villages_farmed": self.total_villages_farmed,
                "troops_recruited_by_unit": self.troops_recruited_by_unit,
                "buildings_constructed_count": self.buildings_constructed_count,
                "hourly_buckets": {
                    k: v.to_dict() for k, v in self.hourly_buckets.items()
                },
                "recent_loot_events": [
                    e.to_dict() for e in self.recent_loot_events[:50]
                ],
                "recent_commands": [
                    c.to_dict() for c in self.recent_commands[:50]
                ],
            }
            tmp_path = self.cache_file.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp_path.replace(self.cache_file)
        except Exception as e:
            logger.debug(f"Erro ao salvar estatísticas em disco ({self.cache_file}): {e}")

    def _load_from_disk(self) -> None:
        """Carrega estado persistido do disco se existir."""
        if not self.cache_file.exists():
            return
        try:
            raw = json.loads(self.cache_file.read_text(encoding="utf-8"))
            self.created_at = float(raw.get("created_at", self.created_at))
            self.last_updated = float(raw.get("last_updated", self.last_updated))
            self.total_wood = int(raw.get("total_wood", 0))
            self.total_stone = int(raw.get("total_stone", 0))
            self.total_iron = int(raw.get("total_iron", 0))
            self.total_attacks_sent = int(raw.get("total_attacks_sent", 0))
            self.total_attacks_successful = int(raw.get("total_attacks_successful", 0))
            self.total_villages_farmed = int(raw.get("total_villages_farmed", 0))
            self.troops_recruited_by_unit = {
                str(k): int(v) for k, v in raw.get("troops_recruited_by_unit", {}).items()
            }
            self.buildings_constructed_count = int(raw.get("buildings_constructed_count", 0))

            raw_buckets = raw.get("hourly_buckets", {})
            self.hourly_buckets = {}
            for k, b in raw_buckets.items():
                self.hourly_buckets[k] = HourlyBucket(
                    hour_key=str(b.get("hour_key", k)),
                    timestamp=float(b.get("timestamp", 0.0)),
                    wood=int(b.get("wood", 0)),
                    stone=int(b.get("stone", 0)),
                    iron=int(b.get("iron", 0)),
                    total=int(b.get("total", 0)),
                    attacks_count=int(b.get("attacks_count", 0)),
                    villages_farmed=int(b.get("villages_farmed", 0)),
                    troops_recruited=int(b.get("troops_recruited", 0)),
                )

            self.recent_loot_events = [
                LootEvent(
                    timestamp=float(e.get("timestamp", 0.0)),
                    village_id=int(e.get("village_id", 0)),
                    target_x=int(e.get("target_x", 0)),
                    target_y=int(e.get("target_y", 0)),
                    wood=int(e.get("wood", 0)),
                    stone=int(e.get("stone", 0)),
                    iron=int(e.get("iron", 0)),
                    total=int(e.get("total", 0)),
                    wall=int(e.get("wall", 0)),
                    losses=bool(e.get("losses", False)),
                    village_name=str(e.get("village_name", "")),
                )
                for e in raw.get("recent_loot_events", [])
            ]

            self.recent_commands = [
                CommandEvent(
                    timestamp=float(c.get("timestamp", 0.0)),
                    command_type=str(c.get("command_type", "farm")),
                    target_coords=str(c.get("target_coords", "")),
                    units={str(uk): int(uv) for uk, uv in c.get("units", {}).items()},
                    success=bool(c.get("success", True)),
                    response_time_ms=int(c.get("response_time_ms", 0)),
                    details=str(c.get("details", "")),
                )
                for c in raw.get("recent_commands", [])
            ]
            logger.info(f"[{self.world}] Estatísticas carregadas: {self.total_looted:,} recursos farmados no total.")
        except Exception as e:
            logger.warning(f"[{self.world}] Falha suave ao carregar estatísticas prévias: {e}")
