"""
Tribal Wars Mobile Automation Engine - MapManager (screen=map)
Extração de grelha de mapa, identificação de aldeias de jogadores e bárbaras,
scanner de aldeias bárbaras por proximidade euclidiana, cache local e
integração com farming automatizado (Map-Driven Farming).
"""

from dataclasses import asdict, dataclass, field
import json
import logging
import math
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

from engine.core.account import TribalAccount
from engine.utils.parsers import parse_map_response

logger = logging.getLogger(__name__)


@dataclass
class MapVillage:
    """Representação de uma aldeia mapeada no setor tático."""
    id: int
    x: int
    y: int
    name: str
    points: int = 0
    player_id: int = 0
    player_name: str = ""
    tribe_id: int = 0
    tribe_tag: str = ""
    bonus_id: int = 0
    distance: float = 0.0

    @property
    def coordinates(self) -> str:
        return f"{self.x}|{self.y}"

    @property
    def coords_tuple(self) -> Tuple[int, int]:
        return (self.x, self.y)

    @property
    def is_barbarian(self) -> bool:
        if self.player_id == 0:
            return True
        p_lower = self.player_name.lower().strip()
        if not p_lower or p_lower in ("bárbaros", "barbarians", "abandonada", "aldeia de bárbaros"):
            return True
        return False

    @property
    def is_bonus(self) -> bool:
        return self.bonus_id > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "name": self.name,
            "points": self.points,
            "player_id": self.player_id,
            "player_name": self.player_name,
            "tribe_id": self.tribe_id,
            "tribe_tag": self.tribe_tag,
            "bonus_id": self.bonus_id,
            "distance": self.distance,
            "is_barbarian": self.is_barbarian,
            "is_bonus": self.is_bonus,
            "coordinates": self.coordinates,
        }


@dataclass
class MapState:
    """Estado do mapa centrado numa determinada coordenada."""
    center_x: int
    center_y: int
    radius: float
    villages: List[MapVillage] = field(default_factory=list)
    last_scanned: float = 0.0

    @property
    def barbarians(self) -> List[MapVillage]:
        return [v for v in self.villages if v.is_barbarian]

    @property
    def players(self) -> List[MapVillage]:
        return [v for v in self.villages if not v.is_barbarian]


class MapManager:
    """
    Controlador do Mapa Tático e Scanner de Aldeias Bárbaras.
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path(".map_cache")

    @staticmethod
    def calculate_distance(x1: int, y1: int, x2: int, y2: int) -> float:
        """Calcula a distância euclidiana exata entre dois pontos no mapa."""
        return round(math.hypot(x2 - x1, y2 - y1), 2)

    def _get_cache_path(self, world: str) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir / f"map_{world}.json"

    def load_cache(self, world: str) -> Tuple[List[MapVillage], float]:
        """Carrega a lista de aldeias em cache para o mundo especificado."""
        c_path = self._get_cache_path(world)
        if not c_path.exists():
            return [], 0.0

        try:
            data = json.loads(c_path.read_text(encoding="utf-8"))
            timestamp = float(data.get("timestamp", 0.0))
            raw_villages = data.get("villages", [])
            villages = []
            for item in raw_villages:
                villages.append(
                    MapVillage(
                        id=int(item["id"]),
                        x=int(item["x"]),
                        y=int(item["y"]),
                        name=str(item.get("name", "")),
                        points=int(item.get("points", 0)),
                        player_id=int(item.get("player_id", 0)),
                        player_name=str(item.get("player_name", "")),
                        tribe_id=int(item.get("tribe_id", 0)),
                        tribe_tag=str(item.get("tribe_tag", "")),
                        bonus_id=int(item.get("bonus_id", 0)),
                    )
                )
            return villages, timestamp
        except Exception as e:
            logger.warning(f"Erro ao ler cache do mapa ({world}): {e}")
            return [], 0.0

    def save_cache(self, world: str, villages: List[MapVillage]) -> None:
        """Persiste em disco o mapa de aldeias do mundo."""
        c_path = self._get_cache_path(world)
        try:
            payload = {
                "timestamp": time.time(),
                "world": world,
                "count": len(villages),
                "villages": [
                    {
                        "id": v.id,
                        "x": v.x,
                        "y": v.y,
                        "name": v.name,
                        "points": v.points,
                        "player_id": v.player_id,
                        "player_name": v.player_name,
                        "tribe_id": v.tribe_id,
                        "tribe_tag": v.tribe_tag,
                        "bonus_id": v.bonus_id,
                    }
                    for v in villages
                ],
            }
            c_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Erro ao gravar cache do mapa ({world}): {e}")

    async def fetch_map_data(
        self,
        account: TribalAccount,
        center_x: int,
        center_y: int,
        radius: float = 15.0,
        village_id: Optional[int] = None,
    ) -> List[MapVillage]:
        """
        Consulta os dados do mapa a partir do jogo (screen=map e AJAX de mapa).
        Calcula as distâncias em relação ao centro (center_x, center_y).
        """
        v_id = village_id or account.current_village_id
        villages_raw: List[Dict[str, Any]] = []

        # 1. Tenta o endpoint AJAX oficial de setores do Tribal Wars: /map.php?v=2&e={ts}&{sx}_{sy}=1
        try:
            sectors = set()
            r_int = int(math.ceil(radius))
            for x in range(center_x - r_int, center_x + r_int + 20, 20):
                for y in range(center_y - r_int, center_y + r_int + 20, 20):
                    sx = int(x - x % 20)
                    sy = int(y - y % 20)
                    sectors.add(f"{sx}_{sy}")

            query = "&".join(f"{s}=1" for s in sorted(sectors))
            ts = int(time.time() * 1000)
            map_url = f"https://{account.host}/map.php?v=2&e={ts}&{query}"

            if hasattr(account, "session") and account.session:
                resp = await account.session.get(map_url)
                if hasattr(resp, "status_code") and resp.status_code == 200:
                    try:
                        json_sectors = resp.json()
                        villages_raw = parse_map_response(json_sectors)
                    except Exception:
                        villages_raw = parse_map_response(getattr(resp, "text", ""))
            elif hasattr(account, "get"):
                resp_val = await account.get(map_url)
                if resp_val:
                    villages_raw = parse_map_response(resp_val)
        except Exception as e:
            logger.debug(f"[{account.world}] Tentativa /map.php falhou: {e}")

        # 2. Fallback: requisita o ecrã screen=map padrão (onde reside TWMap.sectorPrefech)
        if not villages_raw:
            try:
                html = await account.get_screen(
                    "map",
                    village_id=v_id,
                    extra_params={"cur_x": str(center_x), "cur_y": str(center_y)},
                )
                villages_raw = parse_map_response(html)
            except Exception as e:
                logger.error(f"[{account.world}] Erro ao carregar screen=map: {e}")

        # 3. Fallback 3: consulta o dump público mundial /map/village.txt se necessário
        if not villages_raw:
            try:
                txt_url = f"https://{account.host}/map/village.txt"
                if account.session:
                    txt_resp = await account.session.get(txt_url)
                    if txt_resp.status_code == 200:
                        villages_raw = parse_map_response(txt_resp.text)
            except Exception as e:
                logger.error(f"[{account.world}] Erro ao consultar /map/village.txt: {e}")

        # Converte para instâncias MapVillage e calcula distâncias
        result: List[MapVillage] = []
        for item in villages_raw:
            vx = int(item["x"])
            vy = int(item["y"])
            dist = self.calculate_distance(center_x, center_y, vx, vy)
            result.append(
                MapVillage(
                    id=int(item["id"]),
                    x=vx,
                    y=vy,
                    name=str(item["name"]),
                    points=int(item.get("points", 0)),
                    player_id=int(item.get("player_id", 0)),
                    player_name=str(item.get("player_name", "")),
                    tribe_id=int(item.get("tribe_id", 0)),
                    tribe_tag=str(item.get("tribe_tag", "")),
                    bonus_id=int(item.get("bonus_id", 0)),
                    distance=dist,
                )
            )

        return result

    async def scan_nearby_barbarians(
        self,
        account: TribalAccount,
        center_x: int,
        center_y: int,
        radius: float = 15.0,
        village_id: Optional[int] = None,
        use_cache: bool = True,
        cache_ttl_hours: float = 12.0,
    ) -> List[MapVillage]:
        """
        Descobre e devolve todas as aldeias bárbaras dentro do raio especificado,
        ordenadas da mais próxima para a mais distante.
        Utiliza cache em disco se disponível e válida.
        """
        cached_villages, timestamp = self.load_cache(account.world)
        cache_age_hours = (time.time() - timestamp) / 3600.0

        all_villages: List[MapVillage] = []

        if use_cache and cached_villages and cache_age_hours < cache_ttl_hours:
            logger.debug(
                f"[{account.world}] Utilizando cache local do mapa ({len(cached_villages)} aldeias, idade: {cache_age_hours:.1f}h)."
            )
            # Recalcula distâncias para o centro atual
            for v in cached_villages:
                v.distance = self.calculate_distance(center_x, center_y, v.x, v.y)
            all_villages = cached_villages
        else:
            logger.info(
                f"[{account.world}] A efetuar varredura ativa do mapa em torno de ({center_x}|{center_y}) num raio de {radius:.0f}..."
            )
            all_villages = await self.fetch_map_data(
                account=account,
                center_x=center_x,
                center_y=center_y,
                radius=radius,
                village_id=village_id,
            )
            if all_villages:
                existing_dict = {v.id: v for v in cached_villages}
                for v in all_villages:
                    existing_dict[v.id] = v
                self.save_cache(account.world, list(existing_dict.values()))

        # Filtra apenas bárbaras no raio e ordena por proximidade
        barbarians = [
            v for v in all_villages
            if v.is_barbarian and v.distance <= radius and not (v.x == center_x and v.y == center_y)
        ]
        barbarians.sort(key=lambda v: v.distance)

        logger.info(
            f"[{account.world}] Scanner de Bárbaras: {len(barbarians)} bárbaras encontradas até {radius:.1f} campos de ({center_x}|{center_y})."
        )
        return barbarians

    def get_cached_barbarians(
        self,
        world: str,
        center_x: int,
        center_y: int,
        radius: float = 15.0,
    ) -> List[MapVillage]:
        """
        Retorna as bárbaras em cache sem realizar pedidos de rede.
        """
        cached_villages, _ = self.load_cache(world)
        barbarians = []
        for v in cached_villages:
            v.distance = self.calculate_distance(center_x, center_y, v.x, v.y)
            if v.is_barbarian and v.distance <= radius and not (v.x == center_x and v.y == center_y):
                barbarians.append(v)
        barbarians.sort(key=lambda v: v.distance)
        return barbarians

    async def run_map_farm_wave(
        self,
        account: TribalAccount,
        farm_manager: Any,
        troops: Any,
        max_attacks: int = 30,
        radius: float = 15.0,
        village_id: Optional[int] = None,
        use_cache: bool = True,
    ) -> int:
        """
        Executa uma onda de saques via Praça de Reunião alimentada automaticamente
        pelo Scanner de Aldeias Bárbaras mais próximas.
        """
        v_id = village_id or account.current_village_id
        curr_v = account.villages.get(v_id) if account.villages else None

        if not curr_v:
            logger.warning(f"[{account.world}] Aldeia {v_id} não encontrada para mapa de farm.")
            return 0

        barbarians = await self.scan_nearby_barbarians(
            account=account,
            center_x=curr_v.x,
            center_y=curr_v.y,
            radius=radius,
            village_id=v_id,
            use_cache=use_cache,
        )

        if not barbarians:
            logger.info(f"[{account.world}] Nenhuma aldeia bárbara encontrada no raio de {radius:.1f} campos.")
            return 0

        target_coords = [b.coords_tuple for b in barbarians]
        logger.info(
            f"[{account.world}] A iniciar onda de Map-Driven Farming para as {len(target_coords)} bárbaras mais próximas..."
        )

        sent_count = await farm_manager.run_place_farm_wave(
            account=account,
            targets=target_coords,
            troops=troops,
            max_attacks=max_attacks,
            village_id=v_id,
        )

        return sent_count
