"""
Tribal Wars Mobile Automation Engine - MapManager & Map Data Parsers
Módulo para extração de dados do mapa usando os ficheiros oficiais de exportação
do Tribal Wars (village.txt, player.txt), exploração de aldeias vizinhas, cálculo
de distâncias euclidianas e classificação de alvos de farm e jogadores.
"""

from dataclasses import asdict, dataclass, field
import json
import logging
import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote

from engine.core.account import TribalAccount

logger = logging.getLogger(__name__)


@dataclass
class MapVillage:
    """Representação de uma aldeia no mapa do mundo."""
    id: int
    name: str
    x: int
    y: int
    player_id: int = 0
    player_name: str = "Bárbaro"
    points: int = 0
    distance: float = 0.0
    bonus: Optional[str] = None
    is_barbarian: bool = True
    is_own: bool = False
    wall: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
    return round(math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2), 2)


# --- Parsing dos Ficheiros Oficiais de Exportação do TW ---

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
    except Exception:
        pass

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
    Controlador para busca de dados geográficos e aldeias do mapa.
    Usa os ficheiros oficiais de exportação do Tribal Wars (/map/village.txt e /map/player.txt)
    como fonte primária de dados, com cache de 5 minutos para evitar sobrecarga.
    """

    # Cache TTL: 5 minutos para os ficheiros do mundo (atualizam de hora a hora)
    WORLD_DATA_TTL = 300.0

    def __init__(self):
        self._cache: Dict[str, Tuple[float, MapData]] = {}
        # Cache global dos dados brutos do mundo
        self._world_villages: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
        self._world_players: Dict[str, Tuple[float, Dict[int, str]]] = {}

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
