"""
Tribal Wars Mobile Automation Engine - MapManager and Tactical Map
Extração de grelha de mapa, identificação de aldeias de jogadores e bárbaras,
scanner de aldeias bárbaras por proximidade, persistência em cache e
integração com ondas automáticas de farming via Praça de Reunião.
Suporte para parsing de village.txt/player.txt oficiais e screen=map.
"""

from dataclasses import dataclass, field
import json
import logging
import math
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote

from engine.core.account import TribalAccount
from engine.utils.parsers import parse_map_response

logger = logging.getLogger("TribalWars.Map")


@dataclass
class MapVillage:
    """Representação de uma aldeia mapeada no setor tático."""
    id: int
    x: int = 0
    y: int = 0
    name: str = ""
    points: int = 0
    player_id: int = 0
    player_name: str = ""
    tribe_id: int = 0
    tribe_tag: str = ""
    bonus_id: int = 0
    distance: float = 0.0
    bonus: Optional[str] = None
    is_own: bool = False
    wall: int = 0
    is_barbarian: Optional[bool] = None

    def __post_init__(self):
        if self.is_barbarian is None:
            if self.player_id == 0:
                self.is_barbarian = True
            else:
                p_lower = self.player_name.lower().strip() if self.player_name else ""
                self.is_barbarian = bool(p_lower and p_lower in (
                    "bárbaro", "bárbaros", "barbarians", "abandonada", "aldeia de bárbaros"
                ))

    @property
    def coordinates(self) -> str:
        return f"{self.x}|{self.y}"

    @property
    def coords_tuple(self) -> Tuple[int, int]:
        return (self.x, self.y)

    @property
    def is_bonus(self) -> bool:
        return self.bonus_id > 0 or bool(self.bonus)

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
            "bonus": self.bonus,
            "distance": self.distance,
            "is_barbarian": bool(self.is_barbarian),
            "is_bonus": self.is_bonus,
            "is_own": self.is_own,
            "wall": self.wall,
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


@dataclass
class MapData:
    """Estado consolidado do mapa numa determinada área geográfica."""
    center_x: int
    center_y: int
    radius: float
    villages: List[MapVillage] = field(default_factory=list)

    @property
    def total_villages(self) -> int:
        return len(self.villages)

    @property
    def total_barbarians(self) -> int:
        return sum(1 for v in self.villages if v.is_barbarian)

    @property
    def total_players(self) -> int:
        return sum(1 for v in self.villages if not v.is_barbarian and not v.is_own)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "center": {"x": self.center_x, "y": self.center_y},
            "radius": self.radius,
            "total_villages": self.total_villages,
            "total_barbarians": self.total_barbarians,
            "total_players": self.total_players,
            "villages": [v.to_dict() for v in self.villages],
        }


def calculate_distance(x1: int, y1: int, x2: int, y2: int) -> float:
    """Calcula a distância euclidiana exata entre dois pontos no mapa de campos."""
    return round(math.hypot(x2 - x1, y2 - y1), 2)


def parse_village_txt(content: str) -> List[Dict[str, Any]]:
    """
    Parseia o conteúdo de village.txt (CSV oficial do Tribal Wars).
    Formato: village_id,name,x,y,player_id,points,rank
    Nomes são URL-encoded.
    """
    villages = []
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 7:
            continue
        try:
            villages.append({
                "id": int(parts[0]),
                "name": unquote(parts[1].replace("+", " ")),
                "x": int(parts[2]),
                "y": int(parts[3]),
                "player_id": int(parts[4]),
                "points": int(parts[5]),
                "rank": int(parts[6]),
            })
        except (ValueError, IndexError):
            continue
    return villages


def parse_player_txt(content: str) -> Dict[int, str]:
    """
    Parseia o conteúdo de player.txt (CSV oficial do Tribal Wars).
    Formato: player_id,name,tribe_id,villages,points,rank
    Retorna dicionário {player_id: player_name}.
    """
    players = {}
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 6:
            continue
        try:
            p_id = int(parts[0])
            p_name = unquote(parts[1].replace("+", " "))
            players[p_id] = p_name
        except (ValueError, IndexError):
            continue
    return players


def build_map_villages(
    raw_villages: List[Dict[str, Any]],
    player_names: Dict[int, str],
    center_x: int,
    center_y: int,
    own_player_id: Optional[int] = None,
    own_village_ids: Optional[set] = None,
    radius: float = 15.0,
) -> List[MapVillage]:
    """
    Converte aldeias cruas do village.txt em MapVillage filtradas por raio.
    """
    result: List[MapVillage] = []
    own_ids = own_village_ids or set()

    for v in raw_villages:
        vx = v["x"]
        vy = v["y"]
        dist = calculate_distance(center_x, center_y, vx, vy)

        # Filtrar por raio (0 ou negativo = sem filtro)
        if radius > 0 and dist > radius:
            continue

        p_id = v["player_id"]
        is_barbarian = (p_id == 0)
        is_own = (
            v["id"] in own_ids
            or (own_player_id is not None and p_id == own_player_id and p_id > 0)
        )

        p_name = "Bárbaro"
        if not is_barbarian:
            p_name = player_names.get(p_id, f"Jogador {p_id}")

        result.append(MapVillage(
            id=v["id"],
            name=v["name"],
            x=vx,
            y=vy,
            player_id=p_id,
            player_name=p_name,
            points=v["points"],
            distance=dist,
            is_barbarian=is_barbarian,
            is_own=is_own,
        ))

    result.sort(key=lambda v: v.distance)
    return result


# --- Parsing HTML do screen=map (Fallback) ---

def parse_map_screen_data(
    content: str,
    center_x: int,
    center_y: int,
    own_village_id: Optional[int] = None,
    own_player_id: Optional[int] = None,
    radius: float = 15.0,
) -> List[MapVillage]:
    """
    Extrai aldeias a partir do HTML ou payloads JSON do ecrã de mapa ('screen=map').
    Suporta formatos 'TWMap.sectorPreCache', 'map_info' e estruturas JSON de setores.
    NOTA: Este parser é um fallback — o método principal usa village.txt/player.txt.
    """
    villages: Dict[int, MapVillage] = {}

    if not content:
        return []

    # 1. Tentar decodificar se for diretamente uma resposta JSON (AJAX)
    try:
        if content.strip().startswith("{") or content.strip().startswith("["):
            data = json.loads(content)
            _extract_from_json_obj(
                data, villages, center_x, center_y, own_village_id, own_player_id
            )
    except Exception as e:
        logger.debug(f"Falha ao interpretar resposta como JSON direto: {e}")

    # 2. Extrair blocos JSON embutidos em scripts (TWMap.sectorPreCache ou TWMap.initMap)
    sector_matches = re.findall(
        r'(?:sectorPreCache|TWMap\.initMap|villages)\s*=\s*([\[{].*?[\]}]);',
        content,
        re.DOTALL,
    )
    for match_str in sector_matches:
        try:
            parsed = json.loads(match_str)
            _extract_from_json_obj(
                parsed, villages, center_x, center_y, own_village_id, own_player_id
            )
        except Exception:
            continue

    # 3. Extrair via regex para estruturas JSON de aldeias comuns no script do jogo
    village_json_pattern = re.compile(
        r'\{\s*"id"\s*:\s*(\d+)\s*,\s*"name"\s*:\s*"([^"]+)"\s*,\s*"x"\s*:\s*(\d+)\s*,\s*"y"\s*:\s*(\d+)'
    )
    for v_match in village_json_pattern.finditer(content):
        v_id = int(v_match.group(1))
        v_name = v_match.group(2)
        vx = int(v_match.group(3))
        vy = int(v_match.group(4))

        if v_id not in villages:
            dist = calculate_distance(center_x, center_y, vx, vy)
            is_own = (own_village_id is not None and v_id == own_village_id)
            villages[v_id] = MapVillage(
                id=v_id,
                name=v_name,
                x=vx,
                y=vy,
                player_id=0,
                player_name="Bárbaro",
                points=100,
                distance=dist,
                is_barbarian=True,
                is_own=is_own,
            )

    # 4. Fallback: Se for a própria aldeia e ainda não constar, garante que ela surge no mapa
    if own_village_id and own_village_id not in villages:
        villages[own_village_id] = MapVillage(
            id=own_village_id,
            name="Minha Aldeia",
            x=center_x,
            y=center_y,
            player_id=own_player_id or 1,
            player_name="Eu",
            points=500,
            distance=0.0,
            is_barbarian=False,
            is_own=True,
        )

    # Filtrar por raio e ordenar por distância
    village_list = [
        v for v in villages.values()
        if radius <= 0 or v.distance <= radius
    ]
    village_list.sort(key=lambda v: v.distance)
    return village_list


def _extract_from_json_obj(
    obj: Any,
    villages: Dict[int, MapVillage],
    center_x: int,
    center_y: int,
    own_village_id: Optional[int],
    own_player_id: Optional[int],
) -> None:
    """Função auxiliar recursiva para ler aldeias de nós JSON arbitrários."""
    if isinstance(obj, dict):
        if "id" in obj and "x" in obj and "y" in obj:
            try:
                v_id = int(obj["id"])
                vx = int(obj["x"])
                vy = int(obj["y"])
                v_name = str(obj.get("name", f"Aldeia ({vx}|{vy})"))
                p_id = int(obj.get("player", 0) or obj.get("player_id", 0) or 0)
                p_name = str(obj.get("player_name", "Bárbaro" if p_id == 0 else f"Jogador {p_id}"))
                pts = int(obj.get("points", 0) or 0)
                bonus = obj.get("bonus")

                is_barbarian = (p_id == 0)
                is_own = (
                    (own_village_id is not None and v_id == own_village_id)
                    or (own_player_id is not None and p_id == own_player_id and p_id > 0)
                )

                dist = calculate_distance(center_x, center_y, vx, vy)
                villages[v_id] = MapVillage(
                    id=v_id,
                    name=v_name,
                    x=vx,
                    y=vy,
                    player_id=p_id,
                    player_name="Bárbaro" if is_barbarian else p_name,
                    points=pts,
                    distance=dist,
                    bonus=bonus,
                    is_barbarian=is_barbarian,
                    is_own=is_own,
                )
            except (ValueError, TypeError):
                pass

        for val in obj.values():
            _extract_from_json_obj(val, villages, center_x, center_y, own_village_id, own_player_id)

    elif isinstance(obj, list):
        for item in obj:
            _extract_from_json_obj(item, villages, center_x, center_y, own_village_id, own_player_id)



class MapManager:
    """
    Controlador do Mapa Tático e Scanner de Aldeias Bárbaras.
    Combina exploração por setores/AJAX oficiais e ficheiros de exportação do mundo (village.txt).
    """

    WORLD_DATA_TTL = 300.0

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path(".map_cache")
        self._cache: Dict[str, Tuple[float, MapData]] = {}
        self._world_villages: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
        self._world_players: Dict[str, Tuple[float, Dict[int, str]]] = {}

    @staticmethod
    def calculate_distance(x1: int, y1: int, x2: int, y2: int) -> float:
        """Calcula a distância euclidiana exata entre dois pontos no mapa."""
        return calculate_distance(x1, y1, x2, y2)

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
        is_large_dump = len(villages_raw) > 500
        own_ids = set(account.villages.keys()) if hasattr(account, "villages") else set()
        if account.current_village_id:
            own_ids.add(account.current_village_id)

        for item in villages_raw:
            try:
                vx = int(item["x"])
                vy = int(item["y"])
            except (ValueError, TypeError):
                continue
            dist = self.calculate_distance(center_x, center_y, vx, vy)
            if is_large_dump and radius > 0 and dist > radius + 20:
                continue
            v_id_val = int(item["id"])
            is_own_val = v_id_val in own_ids or (hasattr(account, "player") and account.player and item.get("player_id") == account.player.id)
            result.append(
                MapVillage(
                    id=v_id_val,
                    x=vx,
                    y=vy,
                    name=str(item.get("name", "")),
                    points=int(item.get("points", 0)),
                    player_id=int(item.get("player_id", 0)),
                    player_name=str(item.get("player_name", "")),
                    tribe_id=int(item.get("tribe_id", 0)),
                    tribe_tag=str(item.get("tribe_tag", "")),
                    bonus_id=int(item.get("bonus_id", 0)),
                    distance=dist,
                    is_own=bool(is_own_val),
                )
            )

        result.sort(key=lambda v: v.distance)
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

    async def _fetch_world_file(
        self, account: TribalAccount, filename: str
    ) -> str:
        """
        Descarrega um ficheiro de exportação do mundo (/map/<filename>).
        Usa a sessão HTTP existente da conta para autenticação.
        """
        url = f"https://{account.host}/map/{filename}"
        try:
            response = await account.session.get(url, timeout=15.0)
            if response.status_code == 200:
                return response.text
            logger.warning(
                f"[{account.world}] Falha ao descarregar {filename}: HTTP {response.status_code}"
            )
        except Exception as e:
            logger.warning(f"[{account.world}] Erro ao descarregar {filename}: {e}")
        return ""

    async def _get_world_villages(
        self, account: TribalAccount
    ) -> List[Dict[str, Any]]:
        """Obtém a lista completa de aldeias do mundo, com cache."""
        now = time.time()
        cache_key = account.world

        if cache_key in self._world_villages:
            ts, cached = self._world_villages[cache_key]
            if now - ts < self.WORLD_DATA_TTL:
                return cached

        content = await self._fetch_world_file(account, "village.txt")
        villages = parse_village_txt(content)

        if villages:
            self._world_villages[cache_key] = (now, villages)
            logger.info(
                f"[{account.world}] village.txt carregado: {len(villages)} aldeias no mundo."
            )
        else:
            logger.warning(f"[{account.world}] village.txt vazio ou inacessível.")
            # Retornar cache expirado se existir
            if cache_key in self._world_villages:
                return self._world_villages[cache_key][1]

        return villages

    async def _get_world_players(
        self, account: TribalAccount
    ) -> Dict[int, str]:
        """Obtém o mapeamento player_id -> player_name do mundo, com cache."""
        now = time.time()
        cache_key = account.world

        if cache_key in self._world_players:
            ts, cached = self._world_players[cache_key]
            if now - ts < self.WORLD_DATA_TTL:
                return cached

        content = await self._fetch_world_file(account, "player.txt")
        players = parse_player_txt(content)

        if players:
            self._world_players[cache_key] = (now, players)
            logger.info(
                f"[{account.world}] player.txt carregado: {len(players)} jogadores no mundo."
            )
        else:
            logger.warning(f"[{account.world}] player.txt vazio ou inacessível.")
            if cache_key in self._world_players:
                return self._world_players[cache_key][1]

        return players

    async def get_map(
        self,
        account: TribalAccount,
        center_x: Optional[int] = None,
        center_y: Optional[int] = None,
        radius: float = 15.0,
        village_id: Optional[int] = None,
    ) -> MapData:
        """
        Carrega os dados do mapa em torno das coordenadas especificadas (ou da aldeia ativa).
        Usa village.txt/player.txt como fonte primária, com fallback para screen=map.
        """
        v_id = village_id or account.current_village_id or 0
        curr_village = account.villages.get(v_id)

        cx = center_x if center_x is not None else (curr_village.x if curr_village else 500)
        cy = center_y if center_y is not None else (curr_village.y if curr_village else 500)

        # Obter IDs das aldeias do jogador
        own_ids = set(account.villages.keys()) if account.villages else set()
        p_id = account.player.id if account.player else None

        # 1. Fonte primária: village.txt + player.txt (dados oficiais do mundo)
        raw_villages = await self._get_world_villages(account)
        player_names = await self._get_world_players(account)

        villages: List[MapVillage] = []

        if raw_villages:
            villages = build_map_villages(
                raw_villages=raw_villages,
                player_names=player_names,
                center_x=cx,
                center_y=cy,
                own_player_id=p_id,
                own_village_ids=own_ids,
                radius=radius,
            )
        else:
            # 2. Fallback: tentar parsear screen=map (dados limitados na versão mobile)
            logger.info(f"[{account.world}] Fallback para screen=map...")
            try:
                html = await account.get_screen("map", village_id=v_id)
            except Exception as e:
                logger.warning(f"[{account.world}] Não foi possível carregar 'screen=map': {e}")
                html = ""

            villages = parse_map_screen_data(
                content=html,
                center_x=cx,
                center_y=cy,
                own_village_id=v_id,
                own_player_id=p_id,
                radius=radius,
            )

        map_data = MapData(
            center_x=cx,
            center_y=cy,
            radius=radius,
            villages=villages,
        )

        logger.info(
            f"[{account.world}] Mapa carregado em torno de ({cx}|{cy}): "
            f"{map_data.total_villages} aldeias detetadas ({map_data.total_barbarians} bárbaras)."
        )
        return map_data
