"""
Tribal Wars Mobile Automation Engine - Parsers de Dados e Evasão
Extração resiliente de 'game_data', tokens CSRF, recursos e deteção de bot protect.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse

from engine.core.models import Resources, VillageData, PlayerData

logger = logging.getLogger(__name__)

# Regex robusto para localizar o início do objeto JavaScript global 'game_data'
GAME_DATA_START_REGEX = re.compile(
    r"(?:var\s+game_data\s*=|TribalWars\.updateGameData\()\s*(\{)",
    re.IGNORECASE,
)
GAME_DATA_REGEX = re.compile(
    r"(?:var\s+game_data\s*=|TribalWars\.updateGameData\()\s*(\{.+?\})\s*(?:\);|;)",
    re.DOTALL | re.IGNORECASE,
)

# Regex de fallback para extração direta de chaves individuais do game_data
CSRF_REGEX = re.compile(r'["\']csrf["\']\s*:\s*["\']([a-f0-9]+)["\']', re.IGNORECASE)
VILLAGE_ID_REGEX = re.compile(r'["\']village["\']\s*:\s*\{[^}]*?["\']id["\']\s*:\s*(\d+)', re.IGNORECASE)
RESOURCE_SPAN_REGEX = {
    "wood": re.compile(r'<span[^>]*id=["\']wood["\'][^>]*>([\d\.]+)</span>', re.IGNORECASE),
    "stone": re.compile(r'<span[^>]*id=["\']stone["\'][^>]*>([\d\.]+)</span>', re.IGNORECASE),
    "iron": re.compile(r'<span[^>]*id=["\']iron["\'][^>]*>([\d\.]+)</span>', re.IGNORECASE),
    "storage": re.compile(r'<span[^>]*id=["\']storage["\'][^>]*>([\d\.]+)</span>', re.IGNORECASE),
    "pop_current": re.compile(r'<span[^>]*id=["\']pop_current(?:_label)?["\'][^>]*>([\d\.]+)</span>', re.IGNORECASE),
    "pop_max": re.compile(r'<span[^>]*id=["\']pop_max(?:_label)?["\'][^>]*>([\d\.]+)</span>', re.IGNORECASE),
}

# Padrões indicadores de tela de verificação anti-bot (captcha)
BOT_PROTECT_PATTERNS = [
    re.compile(r'id=["\']bot_protect["\']', re.IGNORECASE),
    re.compile(r'name=["\']bot_check["\']', re.IGNORECASE),
    re.compile(r'bot_protect', re.IGNORECASE),
    re.compile(r'bot_check', re.IGNORECASE),
    re.compile(r'Proteção\s+(?:contra\s+)?bots', re.IGNORECASE),
    re.compile(r'Bot\s+protection', re.IGNORECASE),
    re.compile(r'screen=bot_protect', re.IGNORECASE),
]

# Padrões indicadores de sessão expirada / tela de login
SESSION_EXPIRED_PATTERNS = [
    re.compile(r'id=["\']login_form["\']', re.IGNORECASE),
    re.compile(r'name=["\']password["\']', re.IGNORECASE),
    re.compile(r'Sessão\s+expirada', re.IGNORECASE),
    re.compile(r'Session\s+expired', re.IGNORECASE),
    re.compile(r'screen=welcome', re.IGNORECASE),
]


def extract_game_data(html: str) -> Optional[Dict[str, Any]]:
    """
    Localiza e decodifica o JSON do 'game_data' embutido nas páginas do Tribal Wars.
    Utiliza JSONDecoder.raw_decode para consumir estritamente o objeto JSON até ao fecho de chavetas,
    suportando tanto 'var game_data = {...};' como 'TribalWars.updateGameData({...});'.
    """
    if not html:
        return None

    # 1. Extração robusta via JSONDecoder.raw_decode a partir da chaveta inicial
    match_start = GAME_DATA_START_REGEX.search(html)
    if match_start:
        start_idx = match_start.start(1)
        try:
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(html, idx=start_idx)
            if isinstance(obj, dict):
                return obj
        except Exception as e:
            logger.debug(f"raw_decode inicial falhou: {e}")

    # 2. Fallback de regex tradicional com tolerância a JS imperfeito
    match_legacy = GAME_DATA_REGEX.search(html)
    if match_legacy:
        raw_json = match_legacy.group(1)
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError:
            try:
                repaired = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', raw_json)
                return json.loads(repaired)
            except Exception as e:
                logger.warning(f"Falha ao decodificar JSON do game_data: {e}")
                return None
    return None



def extract_csrf_token(html: str, game_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Extrai o token CSRF (parâmetro 'h') a partir do game_data ou de regex no HTML.
    """
    if game_data and "csrf" in game_data:
        csrf = str(game_data["csrf"]).strip()
        if csrf:
            return csrf

    match = CSRF_REGEX.search(html)
    if match:
        return match.group(1)

    # Procura em URLs nos links da página (ex.: game.php?...&h=123456)
    url_match = re.search(r'[?&]h=([a-f0-9]{4,32})', html, re.IGNORECASE)
    if url_match:
        return url_match.group(1)

    return None


def extract_resources(html: str, game_data: Optional[Dict[str, Any]] = None) -> Resources:
    """
    Extrai a quantidade de recursos, capacidade de armazém e população da aldeia.
    Prioriza o game_data.village, usando os elementos HTML como fallback.
    """
    res = Resources()

    if game_data and "village" in game_data and isinstance(game_data["village"], dict):
        v = game_data["village"]
        res.wood = int(v.get("wood", 0))
        res.stone = int(v.get("stone", 0))
        res.iron = int(v.get("iron", 0))
        res.storage_max = int(v.get("storage_max", 0))
        res.pop = int(v.get("pop", 0))
        res.pop_max = int(v.get("pop_max", 0))
        return res

    # Fallback via regex nos elementos HTML
    def parse_val(pattern_key: str) -> int:
        match = RESOURCE_SPAN_REGEX[pattern_key].search(html)
        if match:
            clean = match.group(1).replace(".", "").strip()
            try:
                return int(clean)
            except ValueError:
                return 0
        return 0

    res.wood = parse_val("wood")
    res.stone = parse_val("stone")
    res.iron = parse_val("iron")
    res.storage_max = parse_val("storage")
    res.pop = parse_val("pop_current")
    res.pop_max = parse_val("pop_max")
    return res


def extract_village_and_player(
    html: str, game_data: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[VillageData], Optional[PlayerData]]:
    """
    Extrai os objetos VillageData e PlayerData consolidados.
    """
    village = None
    player = None

    if game_data:
        if "village" in game_data and isinstance(game_data["village"], dict):
            v = game_data["village"]
            village = VillageData(
                id=int(v.get("id", 0)),
                name=str(v.get("name", "")),
                x=int(v.get("x", 0)),
                y=int(v.get("y", 0)),
                points=int(v.get("points", 0)),
            )

        if "player" in game_data and isinstance(game_data["player"], dict):
            p = game_data["player"]
            villages_count = 0
            if "villages" in p:
                if isinstance(p["villages"], dict) or isinstance(p["villages"], list):
                    villages_count = len(p["villages"])
                elif isinstance(p["villages"], int):
                    villages_count = p["villages"]

            player = PlayerData(
                id=int(p.get("id", 0)),
                name=str(p.get("name", "")),
                points=int(p.get("points", 0)),
                villages_count=villages_count,
            )

    return village, player


def extract_all_villages(
    html: str, game_data: Optional[Dict[str, Any]] = None
) -> Dict[int, VillageData]:
    """
    Extrai todas as aldeias pertencentes à conta a partir do game_data e de elementos HTML.
    Retorna um dicionário mapeado por village_id.
    """
    villages: Dict[int, VillageData] = {}

    # 1. Extração prioritária via game_data
    if game_data and isinstance(game_data, dict):
        # Aldeia ativa
        curr_v = game_data.get("village")
        if isinstance(curr_v, dict) and curr_v.get("id"):
            v_id = int(curr_v["id"])
            villages[v_id] = VillageData(
                id=v_id,
                name=str(curr_v.get("name", "")),
                x=int(curr_v.get("x", 0)),
                y=int(curr_v.get("y", 0)),
                points=int(curr_v.get("points", 0)),
            )

        # Múltiplas aldeias do jogador em game_data.player.villages
        p = game_data.get("player")
        if isinstance(p, dict):
            raw_vills = p.get("villages")
            if isinstance(raw_vills, dict):
                for k, v in raw_vills.items():
                    try:
                        v_id = int(k)
                        if isinstance(v, dict):
                            x_val = int(v.get("x", 0))
                            y_val = int(v.get("y", 0))
                            if not x_val and "coord" in v:
                                parts = str(v["coord"]).split("|")
                                if len(parts) == 2:
                                    x_val, y_val = int(parts[0]), int(parts[1])
                            villages[v_id] = VillageData(
                                id=v_id,
                                name=str(v.get("name", "")),
                                x=x_val,
                                y=y_val,
                                points=int(v.get("points", 0)),
                            )
                        elif isinstance(v, (str, int)):
                            if v_id not in villages:
                                villages[v_id] = VillageData(id=v_id, name=f"Aldeia {v_id}")
                    except (ValueError, TypeError):
                        continue
            elif isinstance(raw_vills, list):
                for item in raw_vills:
                    if isinstance(item, dict) and "id" in item:
                        try:
                            v_id = int(item["id"])
                            villages[v_id] = VillageData(
                                id=v_id,
                                name=str(item.get("name", "")),
                                x=int(item.get("x", 0)),
                                y=int(item.get("y", 0)),
                                points=int(item.get("points", 0)),
                            )
                        except (ValueError, TypeError):
                            continue

    # 2. Extração via select options (mobile/desktop dropdown de aldeias)
    if html:
        matches = re.findall(
            r'<option[^>]*value=["\'](\d+)["\'][^>]*>(.*?)</option>', html, re.DOTALL
        )
        for v_id_str, raw_label in matches:
            try:
                v_id = int(v_id_str)
                # Procura coordenadas no formato (123|456) ou 123|456
                coord_match = re.search(r'\(?(\d{1,3})\|(\d{1,3})\)?', raw_label)
                if coord_match:
                    x = int(coord_match.group(1))
                    y = int(coord_match.group(2))
                    # Remove tags HTML e coordenadas do nome
                    name = raw_label[:coord_match.start()].strip()
                    name = re.sub(r'<[^>]+>', '', name).strip()
                    if not name:
                        name = f"Aldeia ({x}|{y})"
                    if v_id not in villages:
                        villages[v_id] = VillageData(id=v_id, name=name, x=x, y=y)
                    elif not villages[v_id].x:
                        villages[v_id].name = name
                        villages[v_id].x = x
                        villages[v_id].y = y
                else:
                    clean_name = re.sub(r'<[^>]+>', '', raw_label).strip()
                    if v_id not in villages and clean_name:
                        villages[v_id] = VillageData(id=v_id, name=clean_name)
            except (ValueError, TypeError):
                continue

        # 3. Extração via links de aldeia com parâmetros village=ID
        link_matches = re.findall(
            r'<a[^>]*href=["\'][^"\']*?[?&]village=(\d+)[^"\']*["\'][^>]*>(.*?)</a>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        for v_id_str, raw_label in link_matches:
            try:
                v_id = int(v_id_str)
                coord_match = re.search(r'\(?(\d{1,3})\|(\d{1,3})\)?', raw_label)
                if coord_match and v_id not in villages:
                    x = int(coord_match.group(1))
                    y = int(coord_match.group(2))
                    clean_name = raw_label[:coord_match.start()].strip()
                    clean_name = re.sub(r'<[^>]+>', '', clean_name).strip()
                    villages[v_id] = VillageData(
                        id=v_id,
                        name=clean_name or f"Aldeia ({x}|{y})",
                        x=x,
                        y=y,
                    )
            except (ValueError, TypeError):
                continue

    return villages


def parse_overview_villages(html: str) -> Dict[int, VillageData]:
    """
    Analisa a página de visão geral de produção de aldeias ('screen=overview_villages&mode=prod').
    Extrai em lote todas as aldeias do jogador com recursos, capacidade de armazém e população.
    """
    villages: Dict[int, VillageData] = {}
    if not html:
        return villages

    # Regex para localizar linhas de aldeia na tabela de produção
    # Formato padrão: <tr ... data-id="12345" ...> ou linhas com link village=ID
    row_pattern = re.compile(
        r'<tr[^>]*?(?:data-id=["\'](?P<row_id>\d+)["\'])?[^>]*?>(?P<row_content>.*?)</tr>',
        re.DOTALL | re.IGNORECASE,
    )

    for row_match in row_pattern.finditer(html):
        row_html = row_match.group("row_content")
        row_id_str = row_match.group("row_id")

        # Localiza o ID e nome da aldeia no link
        v_link_match = re.search(
            r'<a[^>]*href=["\'][^"\']*?[?&]village=(?P<v_id>\d+)[^"\']*["\'][^>]*>(?P<v_name>.*?)</a>',
            row_html,
            re.DOTALL | re.IGNORECASE,
        )
        if not v_link_match and not row_id_str:
            continue

        v_id = int(v_link_match.group("v_id") if v_link_match else row_id_str)
        raw_name = v_link_match.group("v_name") if v_link_match else ""

        # Extrai coordenadas
        x, y = 0, 0
        coord_match = re.search(r'\(?(\d{1,3})\|(\d{1,3})\)?', raw_name or row_html)
        if coord_match:
            x = int(coord_match.group(1))
            y = int(coord_match.group(2))

        clean_name = re.sub(r'<[^>]+>', '', raw_name).strip()
        if coord_match and clean_name:
            c_start = clean_name.find(coord_match.group(0))
            if c_start > 0:
                clean_name = clean_name[:c_start].strip()

        # Extrai recursos (Madeira, Argila, Ferro)
        # 1. Padrões com classes span: wood, stone, iron
        wood_m = re.search(r'<span[^>]*class=["\'][^"\']*wood[^"\']*["\'][^>]*>([\d\.]+)</span>', row_html, re.I)
        stone_m = re.search(r'<span[^>]*class=["\'][^"\']*stone[^"\']*["\'][^>]*>([\d\.]+)</span>', row_html, re.I)
        iron_m = re.search(r'<span[^>]*class=["\'][^"\']*iron[^"\']*["\'][^>]*>([\d\.]+)</span>', row_html, re.I)
        storage_m = re.search(r'<span[^>]*class=["\'][^"\']*storage[^"\']*["\'][^>]*>([\d\.]+)</span>', row_html, re.I)
        
        # 2. Padrão de população (pop/pop_max)
        pop_m = re.search(r'(\d{1,6})/(\d{1,6})', row_html)

        # 3. Pontos
        points_m = re.search(r'<td[^>]*class=["\'][^"\']*points[^"\']*["\'][^>]*>([\d\.]+)</td>', row_html, re.I)

        def clean_int(val_str: Optional[str]) -> int:
            if not val_str:
                return 0
            return int(val_str.replace(".", "").replace(",", "").strip())

        wood = clean_int(wood_m.group(1)) if wood_m else 0
        stone = clean_int(stone_m.group(1)) if stone_m else 0
        iron = clean_int(iron_m.group(1)) if iron_m else 0
        storage = clean_int(storage_m.group(1)) if storage_m else 1000
        points = clean_int(points_m.group(1)) if points_m else 0

        pop_curr = int(pop_m.group(1)) if pop_m else 0
        pop_max = int(pop_m.group(2)) if pop_m else 240

        res_obj = Resources(
            wood=wood,
            stone=stone,
            iron=iron,
            storage_max=storage,
            pop=pop_curr,
            pop_max=pop_max,
        )

        villages[v_id] = VillageData(
            id=v_id,
            name=clean_name or f"Aldeia {v_id}",
            x=x,
            y=y,
            points=points,
            resources=res_obj,
        )

    # Fallback 1: Procura elementos com classe quickedit-vn
    if not villages:
        for qe_match in re.finditer(r'class=["\'][^"\']*quickedit-vn[^"\']*["\'][^>]*data-id=["\'](\d+)["\'][^>]*>(.*?)</span>', html, re.I | re.DOTALL):
            vid = int(qe_match.group(1))
            vname = re.sub(r'<[^>]+>', '', qe_match.group(2)).strip()
            x, y = 0, 0
            cm = re.search(r'\(?(\d{1,3})\|(\d{1,3})\)?', vname)
            if cm:
                x, y = int(cm.group(1)), int(cm.group(2))
            villages[vid] = VillageData(id=vid, name=vname or f"Aldeia {vid}", x=x, y=y)

    # Fallback 2: Extrai todas as aldeias através de seletores e links genéricos
    if not villages:
        extracted = extract_all_villages(html)
        if extracted:
            villages.update(extracted)

    return villages


def extract_player_worlds(html: str, domain: str = "tribalwars.com.pt") -> List[str]:
    """
    Extrai a lista de subdomínios de mundos onde o utilizador possui conta/aldeias ativas.
    """
    if not html:
        return []
    
    worlds = set()
    # Padrão: https://pt117.tribalwars.com.pt ou links com mundo
    pattern = re.compile(
        r'https?://(?P<world>[a-z0-9_]+)\.' + re.escape(domain),
        re.IGNORECASE,
    )
    for m in pattern.finditer(html):
        w = m.group("world").lower()
        if w not in ("www", "forum", "help", "blog", "api"):
            worlds.add(w)

    # Padrão: data-world="pt117" ou class="world_button... data-id="pt117"
    attr_pattern = re.compile(r'data-world=["\'](?P<world>[a-z0-9_]+)["\']', re.I)
    for m in attr_pattern.finditer(html):
        w = m.group("world").lower()
        if w not in ("www", "forum", "help"):
            worlds.add(w)

    return sorted(list(worlds))



def is_bot_protection_present(html: str) -> bool:
    """Verifica se a resposta HTML contém indícios inequívocos de verificação humana/captcha."""
    if not html:
        return False
    return any(p.search(html) is not None for p in BOT_PROTECT_PATTERNS)


def is_session_expired(html: str, current_url: str = "") -> bool:
    """Verifica se a sessão expirou ou redirecionou para tela de login/boas-vindas."""
    if "screen=welcome" in current_url or "/index.php" in current_url:
        return True
    if not html:
        return False
    # Se contém formulário de login explícito
    return any(p.search(html) is not None for p in SESSION_EXPIRED_PATTERNS)


# Regex para edifícios e fila de construção (screen=main)
BUILD_QUEUE_ROW_REGEX = re.compile(
    r'(?:<tr[^>]*class=["\'](?:lit\s+)?buildorder_([a-z_]+)[^>]*>|<tr[^>]*>).*?'
    r'([A-Za-zÀ-ÿ\s]+)\s*(?:\(Nível\s+(\d+)\)|\(Level\s+(\d+)\)).*?'
    r'(?:<span[^>]*class=["\']timer["\'][^>]*>([\d:]+)</span>|data-endtime=["\'](\d+)["\'])?.*?'
    r'<a[^>]*href=["\']([^"\']*(?:action=cancel[^"\']*[?&]id=(\d+)|[?&]id=(\d+)[^"\']*action=cancel)[^"\']*)["\']',
    re.DOTALL | re.IGNORECASE,
)

BUILDING_ROW_REGEX = re.compile(
    r'(?:<tr|<div)[^>]*id=["\']main_buildrow_([a-z_]+)["\'][^>]*>(.*?)(?:</tr>|<div\s+class=["\']mobileBlock\s+buildingBlock["\']|<div\s+id=["\']main_buildrow_|$)',
    re.DOTALL | re.IGNORECASE,
)


BUILD_COST_REGEX = {
    "wood": re.compile(r'(?:cost_wood|icon header wood)[^>]*>.*?([\d\.]+)', re.IGNORECASE | re.DOTALL),
    "stone": re.compile(r'(?:cost_stone|icon header stone)[^>]*>.*?([\d\.]+)', re.IGNORECASE | re.DOTALL),
    "iron": re.compile(r'(?:cost_iron|icon header iron)[^>]*>.*?([\d\.]+)', re.IGNORECASE | re.DOTALL),
    "pop": re.compile(r'(?:cost_pop|icon header pop)[^>]*>.*?([\d\.]+)', re.IGNORECASE | re.DOTALL),
}


def parse_building_levels(html: str, game_data: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
    """
    Extrai o nível atual de cada edifício da aldeia.
    Prioriza o game_data.village.buildings; caso ausente, efetua fallback via HTML.
    """
    levels: Dict[str, int] = {}

    if game_data and "village" in game_data and isinstance(game_data["village"], dict):
        buildings = game_data["village"].get("buildings")
        if isinstance(buildings, dict):
            for b_name, b_level in buildings.items():
                try:
                    levels[str(b_name).lower()] = int(b_level)
                except (ValueError, TypeError):
                    continue
            if levels:
                return levels

    # Fallback no HTML buscando por main_buildrow_<building>
    for match in BUILDING_ROW_REGEX.finditer(html):
        b_name = match.group(1).lower()
        row_content = match.group(2)
        lvl_match = re.search(
            r'<span[^>]*class=["\']level["\'][^>]*>(\d+)</span>|'
            r'(?:Nível|Level)\s*<span[^>]*class=["\']level["\'][^>]*>(\d+)</span>|'
            r'\(Nível\s+(\d+)\)|\(Level\s+(\d+)\)|data-level=["\'](\d+)["\']',
            row_content,
            re.IGNORECASE,
        )
        if lvl_match:
            val = next(g for g in lvl_match.groups() if g is not None)
            try:
                levels[b_name] = int(val)
            except ValueError:
                levels[b_name] = 0
        else:
            levels[b_name] = 0

    return levels


def parse_timer_to_seconds(timer_str: str) -> Optional[int]:
    """
    Converte strings de timer do Tribal Wars para segundos totais.
    Exemplos: '0:02:45' -> 165, '2:45' -> 165, '0:00:15' -> 15, '1:10:05' -> 4205.
    """
    if not timer_str:
        return None
    cleaned = re.sub(r'[^\d:]', '', str(timer_str).strip())
    parts = cleaned.split(":")
    try:
        if len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:
            m, s = int(parts[0]), int(parts[1])
            return m * 60 + s
        elif len(parts) == 1 and parts[0]:
            return int(parts[0])
    except ValueError:
        pass
    return None


def parse_build_queue(html: str) -> List[Dict[str, Any]]:
    """
    Extrai as ordens ativas na fila de construção do Edifício Principal.
    Suporta tanto a versão Desktop (#buildqueue table) como a versão Mobile (#buildqueue_wrap div.queueItem).
    Retorna uma lista de dicionários com: order_id, building_raw, target_level, timer_str, timer_seconds, cancel_url, instant_build_url.
    """
    queue: List[Dict[str, Any]] = []
    if not html:
        return queue

    # Normaliza entidades HTML comuns em URLs
    normalized_html = html.replace("&amp;", "&")

    # 1. Suporte à Versão Mobile: div.queueItem com data-order="(\d+)"
    mobile_items = list(re.finditer(
        r'<div[^>]*class=["\'][^"\']*queueItem[^"\']*["\'][^>]*data-order=["\'](\d+)["\'][^>]*>(.*?)'
        r'(?=<div[^>]*class=["\'][^"\']*queueItem|<div\s+id=["\']building_wrapper|<script|$)',
        normalized_html,
        re.DOTALL | re.IGNORECASE,
    ))

    if mobile_items:
        for m in mobile_items:
            order_id = m.group(1)
            content = m.group(2)

            name_match = re.search(
                r'([A-Za-zÀ-ÿ\s]+)\s*(?:\(Nível\s+(\d+)\)|\(Level\s+(\d+)\)|\(nível\s+(\d+)\))',
                content,
                re.IGNORECASE,
            )
            building_raw = name_match.group(1).strip() if name_match else "Desconhecido"
            target_level = 0
            if name_match:
                lvl_val = next((g for g in name_match.groups()[1:] if g is not None), "0")
                try:
                    target_level = int(lvl_val)
                except ValueError:
                    target_level = 0

            timer_match = re.search(r'<span[^>]*class=["\']timer["\'][^>]*>([\d:]+)</span>', content, re.IGNORECASE)
            timer_str = timer_match.group(1) if timer_match else None
            timer_sec = parse_timer_to_seconds(timer_str) if timer_str else None

            # Deteção do botão de conclusão instantânea/grátis (< 3 min)
            instant_m = re.search(
                r'<a[^>]*href=["\']([^"\']*[?&]action=(?:instant_build|instant_finish|complete_order|free_finish)[^"\']*)["\']|<button[^>]*class=["\'][^"\']*\b(?:btn-instant-free|btn-instant)\b[^"\']*["\']',
                content,
                re.IGNORECASE,
            )
            instant_build_url = instant_m.group(1) if (instant_m and instant_m.group(1)) else None
            if not instant_build_url and timer_sec is not None and timer_sec <= 180:
                instant_build_url = f"/game.php?screen=main&action=instant_build&id={order_id}"

            queue.append({
                "order_id": order_id,
                "building_raw": building_raw,
                "target_level": target_level,
                "timer_str": timer_str,
                "timer_seconds": timer_sec,
                "cancel_url": f"/game.php?screen=main&action=cancel_order&id={order_id}",
                "instant_build_url": instant_build_url,
            })
        return queue

    # 2. Suporte à Versão Desktop: Busca a tabela ou seção do buildqueue
    queue_section_match = re.search(
        r'<table[^>]*id=["\']buildqueue["\'][^>]*>(.*?)</table>',
        normalized_html,
        re.DOTALL | re.IGNORECASE,
    )

    search_scope = queue_section_match.group(1) if queue_section_match else normalized_html

    # Localiza todas as ordens com cancel link
    cancel_links = list(re.finditer(
        r'<a[^>]*href=["\']([^"\']*[?&]action=cancel[^"\']*)["\'][^>]*>(.*?)</a>',
        search_scope,
        re.DOTALL | re.IGNORECASE,
    ))

    # Para cada link de cancelamento, busca o contexto anterior da linha da tabela
    for link_match in cancel_links:
        full_cancel_url = link_match.group(1)
        id_match = re.search(r'[?&]id=(\d+)', full_cancel_url)
        order_id = id_match.group(1) if id_match else ""

        # Obter o bloco precedente que contém o nome do edifício e nível
        start_pos = max(0, link_match.start() - 600)
        end_pos = min(len(search_scope), link_match.end() + 300)
        preceding_text = search_scope[start_pos:link_match.start()]
        surrounding_text = search_scope[start_pos:end_pos]

        name_match = re.search(
            r'([A-Za-zÀ-ÿ\s]+?)\s*(?:\(Nível\s+(\d+)\)|\(Level\s+(\d+)\)|Nível\s+(\d+))',
            preceding_text,
            re.IGNORECASE,
        )

        b_name_raw = ""
        target_lvl = 1
        if name_match:
            b_name_raw = name_match.group(1).strip()
            # Limpa tags HTML residuais
            b_name_raw = re.sub(r'<[^>]+>', '', b_name_raw).strip()
            lvl_val = next((g for g in name_match.groups()[1:] if g is not None), "1")
            try:
                target_lvl = int(lvl_val)
            except ValueError:
                target_lvl = 1

        # Timer
        timer_match = re.search(r'<span[^>]*class=["\']timer["\'][^>]*>([\d:]+)</span>', preceding_text, re.IGNORECASE)
        timer_str = timer_match.group(1) if timer_match else ""
        timer_sec = parse_timer_to_seconds(timer_str) if timer_str else None

        # Deteção do link/botão de conclusão instantânea/grátis
        instant_m = re.search(
            r'<a[^>]*href=["\']([^"\']*[?&]action=(?:instant_build|instant_finish|complete_order|free_finish)[^"\']*)["\']',
            surrounding_text,
            re.IGNORECASE,
        )
        instant_build_url = instant_m.group(1) if instant_m else None
        if not instant_build_url and timer_sec is not None and timer_sec <= 180 and order_id:
            instant_build_url = f"/game.php?screen=main&action=instant_build&id={order_id}"

        queue.append({
            "order_id": order_id,
            "building_raw": b_name_raw,
            "target_level": target_lvl,
            "timer_str": timer_str,
            "timer_seconds": timer_sec,
            "cancel_url": full_cancel_url,
            "instant_build_url": instant_build_url,
        })

    return queue


def parse_building_upgrades(html: str) -> Dict[str, Dict[str, Any]]:
    """
    Extrai os custos de melhoria, requisitos e estado de elegibilidade de cada edifício.
    Prioriza a extração do JSON nativo 'BuildingMain.buildings' (mobile e desktop).
    Caso ausente, efetua fallback resiliente via blocos HTML.
    """
    upgrades: Dict[str, Dict[str, Any]] = {}
    if not html:
        return upgrades

    # 1. Prioridade: Extração do JSON nativo 'BuildingMain.buildings = {...};'
    m_bm = re.search(r'BuildingMain\.buildings\s*=\s*(\{)', html)
    if m_bm:
        try:
            decoder = json.JSONDecoder()
            bm_data, _ = decoder.raw_decode(html, idx=m_bm.start(1))
            if isinstance(bm_data, dict):
                for b_name, b_info in bm_data.items():
                    if isinstance(b_info, dict):
                        b_canon = b_name.lower().strip()
                        current_lvl = int(b_info.get("level", 0))
                        target_lvl = int(b_info.get("level_next", current_lvl + 1))
                        wood = int(b_info.get("wood", 0))
                        stone = int(b_info.get("stone", 0))
                        iron = int(b_info.get("iron", 0))
                        pop = int(b_info.get("pop", 0))
                        can_build = bool(b_info.get("can_build", False))
                        error_reason = b_info.get("error")
                        build_url = (
                            b_info.get("build_url")
                            or b_info.get("url")
                            or b_info.get("build_link")
                            or b_info.get("upgrade_url")
                            or b_info.get("link")
                        )

                        # Se não estiver no JSON, tenta localizar link de construção específico no HTML
                        if not build_url:
                            b_link_m = re.search(
                                rf'<a[^>]*href=["\']([^"\']*[?&]id={b_canon}[^"\']*[?&]action=(?:build|upgrade_building)[^"\']*)["\']|'
                                rf'<a[^>]*href=["\']([^"\']*[?&]action=(?:build|upgrade_building)[^"\']*[?&]id={b_canon}[^"\']*)["\']',
                                html,
                                re.IGNORECASE,
                            )
                            if b_link_m:
                                build_url = b_link_m.group(1) or b_link_m.group(2)

                        upgrades[b_canon] = {
                            "building": b_canon,
                            "current_level": current_lvl,
                            "target_level": target_lvl,
                            "wood": wood,
                            "stone": stone,
                            "iron": iron,
                            "pop": pop,
                            "can_build": can_build,
                            "error_reason": error_reason,
                            "build_url": build_url,
                        }
                if upgrades:
                    return upgrades
        except Exception as e:
            logger.debug(f"raw_decode BuildingMain.buildings falhou: {e}")

    # 2. Fallback via HTML regex
    normalized_html = html.replace("&amp;", "&")

    for match in BUILDING_ROW_REGEX.finditer(normalized_html):
        b_name = match.group(1).lower()
        content = match.group(2)


        # Custos
        def parse_cost(cost_type: str) -> int:
            rgx = BUILD_COST_REGEX.get(cost_type)
            if not rgx:
                return 0
            m = rgx.search(content)
            if m:
                clean = m.group(1).replace(".", "").strip()
                try:
                    return int(clean)
                except ValueError:
                    return 0
            return 0

        wood = parse_cost("wood")
        stone = parse_cost("stone")
        iron = parse_cost("iron")
        pop = parse_cost("pop")

        # Nível atual
        lvl_match = re.search(
            r'<span[^>]*class=["\']level["\'][^>]*>(\d+)</span>|'
            r'(?:Nível|Level)\s*<span[^>]*class=["\']level["\'][^>]*>(\d+)</span>|'
            r'\(Nível\s+(\d+)\)|\(Level\s+(\d+)\)|data-level=["\'](\d+)["\']',
            content,
            re.IGNORECASE,
        )
        current_lvl = 0
        if lvl_match:
            val = next((g for g in lvl_match.groups() if g is not None), "0")
            try:
                current_lvl = int(val)
            except ValueError:
                current_lvl = 0

        # Link ou botão de construção
        build_link_match = re.search(
            r'<a[^>]*href=["\']([^"\']*[?&]action=(?:upgrade_building|build)[^"\']*)["\'][^>]*>|<button[^>]*class=["\'][^"\']*btn-build[^"\']*["\'][^>]*>',
            content,
            re.IGNORECASE,
        )
        can_build = build_link_match is not None
        build_url = build_link_match.group(1) if (build_link_match and build_link_match.group(1)) else None


        # Identificação de motivo de indisponibilidade
        error_reason = None
        if not can_build:
            if "Armazém muito pequeno" in content or "warehouse too small" in content.lower():
                error_reason = "storage_too_small"
            elif "População máxima" in content or "farm too small" in content.lower():
                error_reason = "insufficient_pop"
            elif "Recursos insuficientes" in content or "not enough resources" in content.lower():
                error_reason = "insufficient_resources"
            elif "Edifício totalmente construído" in content or "fully constructed" in content.lower():
                error_reason = "max_level"
            elif "Requisitos não preenchidos" in content or "requirements not met" in content.lower():
                error_reason = "requirements_not_met"
            elif "Fila de construção cheia" in content or "queue full" in content.lower():
                error_reason = "queue_full"
            else:
                error_reason = "unknown_lock"

        upgrades[b_name] = {
            "building": b_name,
            "current_level": current_lvl,
            "target_level": current_lvl + 1,
            "wood": wood,
            "stone": stone,
            "iron": iron,
            "pop": pop,
            "can_build": can_build,
            "error_reason": error_reason,
            "build_url": build_url,
        }

    return upgrades


# Regex para Praça de Reunião (screen=place)
ALL_UNITS = (
    "spear", "sword", "axe", "archer", "spy", "light",
    "marcher", "heavy", "ram", "catapult", "knight", "snob"
)

UNIT_LINK_ALL_REGEX = re.compile(
    r'(?:id=["\']unit_input_([a-z_]+)_all["\']|data-unit=["\']([a-z_]+)["\'][^>]*class=["\']units-entry-all["\']|class=["\']units-entry-all["\'][^>]*data-unit=["\']([a-z_]+)["\'])[^>]*>\s*\((\d+)\)\s*</a>',
    re.IGNORECASE,
)

UNIT_INPUT_ALL_REGEX = re.compile(
    r'<input[^>]*id=["\']unit_input_([a-z_]+)["\'][^>]*data-all-count=["\'](\d+)["\']|<input[^>]*data-all-count=["\'](\d+)["\'][^>]*id=["\']unit_input_([a-z_]+)["\']',
    re.IGNORECASE,
)

COMMAND_ROW_REGEX = re.compile(
    r'<tr[^>]*class=["\'](?:command-row|nowrap)[^>]*>(.*?)</tr>|<tr[^>]*id=["\']command_(\d+)["\'][^>]*>(.*?)</tr>',
    re.DOTALL | re.IGNORECASE,
)


def parse_available_units(html: str) -> Dict[str, int]:
    """
    Extrai a quantidade de tropas disponíveis na aldeia a partir do ecrã da Praça de Reunião (screen=place).
    Retorna um dicionário com todas as 12 unidades (0 se ausente).
    """
    units: Dict[str, int] = {u: 0 for u in ALL_UNITS}
    if not html:
        return units

    normalized = html.replace("&amp;", "&")

    # 1. Busca por links do tipo <a id="unit_input_spear_all">(150)</a> ou data-unit="spear">(150)</a>
    for match in UNIT_LINK_ALL_REGEX.finditer(normalized):
        unit_name = next(g for g in match.groups()[:3] if g is not None).lower().strip()
        count_str = match.group(4)
        if unit_name in units:
            try:
                units[unit_name] = max(units[unit_name], int(count_str))
            except ValueError:
                pass

    # 2. Busca por inputs com data-all-count="150"
    for match in UNIT_INPUT_ALL_REGEX.finditer(normalized):
        g1, g2, g3, g4 = match.groups()
        if g1 and g2:
            unit_name = g1.lower().strip()
            count_str = g2
        elif g3 and g4:
            unit_name = g4.lower().strip()
            count_str = g3
        else:
            continue

        if unit_name in units:
            try:
                units[unit_name] = max(units[unit_name], int(count_str))
            except ValueError:
                pass

    # 3. Fallback genérico para elementos simples com id="units_entry_all_<unit>"
    for unit_key in ALL_UNITS:
        rgx = re.compile(rf'id=["\'](?:units_entry_all_{unit_key}|unit_input_{unit_key}_all)["\'][^>]*>\s*\(?(\d+)\)?\s*<', re.IGNORECASE)
        m = rgx.search(normalized)
        if m:
            try:
                units[unit_key] = max(units[unit_key], int(m.group(1)))
            except ValueError:
                pass

    return units


def parse_place_commands(html: str) -> List[Dict[str, Any]]:
    """
    Extrai os comandos de tropas em andamento (ataques, apoios e tropas a regressar)
    listados na Praça de Reunião.
    """
    commands: List[Dict[str, Any]] = []
    if not html:
        return commands

    normalized = html.replace("&amp;", "&")

    # Localiza blocos ou linhas de comandos
    # Exemplo: <a href="...screen=info_command&id=12345...">Ataque a Aldeia Bárbara (452|550)</a>
    cmd_link_matches = re.finditer(
        r'<a[^>]*href=["\'][^"\']*[?&]screen=info_command[^"\']*[?&]id=(\d+)[^"\']*["\'][^>]*>(.*?)</a>',
        normalized,
        re.DOTALL | re.IGNORECASE,
    )

    for match in cmd_link_matches:
        cmd_id = match.group(1)
        raw_text = re.sub(r'<[^>]+>', '', match.group(2)).strip()

        # Determina o tipo de movimento
        m_lower = raw_text.lower()
        if "ataque" in m_lower or "attack" in m_lower:
            cmd_type = "attack"
        elif "apoio" in m_lower or "support" in m_lower:
            cmd_type = "support"
        elif "regresso" in m_lower or "return" in m_lower:
            cmd_type = "return"
        else:
            cmd_type = "command"

        # Extrai coordenadas (xxx|yyy)
        coords_match = re.search(r'\((\d{1,3}\|\d{1,3})\)', raw_text)
        coords = coords_match.group(1) if coords_match else ""

        # Extrai nome do alvo
        target_name = raw_text
        if coords_match:
            target_name = raw_text[:coords_match.start()].strip()

        # Procura timer adjacente
        start_idx = match.end()
        surrounding_text = normalized[start_idx:start_idx + 300]
        timer_match = re.search(r'<span[^>]*class=["\']timer["\'][^>]*>([\d:]+)</span>', surrounding_text, re.IGNORECASE)
        timer_str = timer_match.group(1) if timer_match else ""

        commands.append({
            "command_id": cmd_id,
            "type": cmd_type,
            "raw_text": raw_text,
            "target_name": target_name,
            "target_coords": coords,
            "timer_str": timer_str,
        })

    return commands


def parse_command_confirmation(html: str) -> Dict[str, Any]:
    """
    Analisa a página de confirmação de envio de comandos (screen=place&try=confirm).
    Extrai todos os inputs ocultos necessários para a confirmação final (action=command),
    além de verificar caixas de erro do jogo.
    """
    result: Dict[str, Any] = {
        "success": True,
        "error_message": "",
        "hidden_fields": {},
        "target_name": "",
        "target_coords": "",
        "duration_str": "",
        "arrival_time": "",
    }

    if not html:
        result["success"] = False
        result["error_message"] = "Resposta HTML vazia."
        return result

    normalized = html.replace("&amp;", "&")

    # 1. Verifica erros retornados pelo jogo (ex.: proteção de iniciantes, aldeia inválida)
    error_match = re.search(r'<div[^>]*class=["\'](?:error_box|info_box\s+error)["\'][^>]*>(.*?)</div>', normalized, re.DOTALL | re.IGNORECASE)
    if error_match:
        err_msg = re.sub(r'<[^>]+>', '', error_match.group(1)).strip()
        result["success"] = False
        result["error_message"] = err_msg
        return result

    # 2. Extrai todos os campos input hidden do formulário de confirmação
    hidden_inputs = re.findall(
        r'<input[^>]*type=["\']hidden["\'][^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']|<input[^>]*value=["\']([^"\']*)["\'][^>]*type=["\']hidden["\'][^>]*name=["\']([^"\']+)["\']',
        normalized,
        re.IGNORECASE,
    )

    for g1, g2, g3, g4 in hidden_inputs:
        if g1:
            name, val = g1, g2
        else:
            name, val = g4, g3
        result["hidden_fields"][name] = val

    # 3. Duração da marcha
    dur_match = re.search(
        r'(?:Duração|Duration)\s*:?\s*</td>\s*<td>\s*(?:<span[^>]*>)?\s*([\d]+:[\d]+(?::[\d]+)?)\s*(?:</span>)?\s*</td>|'
        r'(?:Duração|Duration)\s*:\s*([\d]+:[\d]+(?::[\d]+)?)',
        normalized,
        re.IGNORECASE,
    )
    if dur_match:
        result["duration_str"] = next(g for g in dur_match.groups() if g is not None)


    # 4. Chegada
    arrival_match = re.search(r'Chegada:?\s*</td>\s*<td>\s*(.*?)(?:<span|</td>)', normalized, re.DOTALL | re.IGNORECASE)
    if arrival_match:
        result["arrival_time"] = re.sub(r'<[^>]+>', '', arrival_match.group(1)).strip()

    # 5. Coordenadas do alvo
    coords_match = re.search(r'\((\d{1,3}\|\d{1,3})\)', normalized)
    if coords_match:
        result["target_coords"] = coords_match.group(1)

    # Validação mínima: campo 'chck' ou 'action_id' ou 'h'
    if not result["hidden_fields"]:
        # Se não encontrou campos ocultos, pode não ser a página de confirmação
        if "action=command" not in normalized and "try=confirm" not in normalized:
            result["success"] = False
            result["error_message"] = "Formulário de confirmação não localizado na página."

    return result


# Regex para Assistente de Farm (screen=am_farm)
PLUNDER_ROW_REGEX = re.compile(
    r'<tr[^>]*id=["\']village_(\d+)["\'][^>]*>(.*?)</tr>',
    re.DOTALL | re.IGNORECASE,
)


def parse_am_farm_targets(html: str) -> List[Dict[str, Any]]:
    """
    Extrai a lista de aldeias bárbaras disponíveis no Assistente de Farm (screen=am_farm).
    Retorna uma lista de dicionários contendo: target_id, target_name, target_coords,
    distance, report_color, wall_level, template_a_id, template_b_id, template_a_available, template_b_available.
    """
    targets: List[Dict[str, Any]] = []
    if not html:
        return targets

    normalized = html.replace("&amp;", "&")

    # Localiza cada linha da tabela de saques (tr id="village_12345")
    for row_match in PLUNDER_ROW_REGEX.finditer(normalized):
        target_id = row_match.group(1)
        row_content = row_match.group(2)

        # 1. Coordenadas (xxx|yyy) e Nome
        coords_match = re.search(r'\((\d{1,3}\|\d{1,3})\)', row_content)
        coords = coords_match.group(1) if coords_match else ""

        name_match = re.search(
            r'<a[^>]*screen=info_village[^>]*>(.*?)</a>',
            row_content,
            re.DOTALL | re.IGNORECASE,
        )
        target_name = ""
        if name_match:
            raw_n = re.sub(r'<[^>]+>', '', name_match.group(1)).strip()
            # Remove as coordenadas se estiverem dentro do nome
            target_name = re.sub(r'\(\d{1,3}\|\d{1,3}\)', '', raw_n).strip()

        # 2. Distância
        dist_match = re.search(r'(\d+\.\d+)\s*(?:campos|fields)?|<td>(\d+(?:\.\d+)?)</td>', row_content, re.IGNORECASE)
        distance = 0.0
        if dist_match:
            val = next(g for g in dist_match.groups() if g is not None)
            try:
                distance = float(val)
            except ValueError:
                distance = 0.0

        # 3. Status do último relatório (verde, amarelo, vermelho, azul)
        report_color = "none"
        if "dots/green" in row_content or "dot green" in row_content or "max_loot/1" in row_content:
            report_color = "green"
        elif "dots/yellow" in row_content or "dot yellow" in row_content:
            report_color = "yellow"
        elif "dots/red" in row_content or "dot red" in row_content:
            report_color = "red"
        elif "dots/blue" in row_content or "dot blue" in row_content:
            report_color = "blue"

        # 4. Nível de muralha
        wall_level = 0
        wall_match = re.search(
            r'(?:Muralha|Wall)[:\s]*<span[^>]*>(\d+)</span>|(?:Muralha|Wall)[:\s]*(\d+)|<td[^>]*class=["\']wall["\'][^>]*>(\d+)</td>',
            row_content,
            re.IGNORECASE,
        )
        if wall_match:
            w_val = next(g for g in wall_match.groups() if g is not None)
            try:
                wall_level = int(w_val)
            except ValueError:
                wall_level = 0

        # 5. Botões do Modelo A e Modelo B
        # Exemplo: href="...action=farm&target=12345&template_id=987&h=..."
        # ou class="farm_icon farm_icon_a"
        def extract_template_btn(tmpl_letter: str) -> Tuple[Optional[str], bool]:
            # Captura a tag completa <a> do modelo correspondente
            btn_match = re.search(
                rf'(<a\s+[^>]*class=["\'][^"\']*farm_icon_{tmpl_letter}[^"\']*["\'][^>]*>)',
                row_content,
                re.IGNORECASE,
            )
            if not btn_match:
                # Fallback por URL com action=farm e template_id
                btn_match = re.search(
                    rf'(<a\s+[^>]*href=["\'][^"\']*[?&]action=farm[^"\']*[?&]target={target_id}[^"\']*[?&]template_id=(\d+)[^"\']*["\'][^>]*>)',
                    row_content,
                    re.IGNORECASE,
                )

            if btn_match:
                tag_str = btn_match.group(1)
                # Extrai template_id da URL contida no atributo href
                t_id_m = re.search(r'[?&]template_id=(\d+)', tag_str)
                t_id = t_id_m.group(1) if t_id_m else None
                # Verifica se este botão específico possui classe disabled
                is_disabled = "farm_icon_disabled" in tag_str or "disabled" in tag_str.lower()
                return t_id, not is_disabled
            return None, False


        tmpl_a_id, tmpl_a_avail = extract_template_btn("a")
        tmpl_b_id, tmpl_b_avail = extract_template_btn("b")

        targets.append({
            "target_id": target_id,
            "target_name": target_name,
            "target_coords": coords,
            "distance": distance,
            "report_color": report_color,
            "wall_level": wall_level,
            "template_a_id": tmpl_a_id,
            "template_b_id": tmpl_b_id,
            "template_a_available": tmpl_a_avail,
            "template_b_available": tmpl_b_avail,
        })

    return targets


def parse_am_farm_templates(html: str) -> Dict[str, Dict[str, int]]:
    """
    Extrai as contagens de tropas configuradas para o Modelo A e Modelo B no Assistente de Farm.
    """
    templates: Dict[str, Dict[str, int]] = {
        "a": {u: 0 for u in ALL_UNITS},
        "b": {u: 0 for u in ALL_UNITS},
    }
    if not html:
        return templates

    normalized = html.replace("&amp;", "&")

    for tmpl in ("a", "b"):
        for unit in ALL_UNITS:
            # Padrão: <input name="a[spear]" value="5" /> ou name="template_a[spear]"
            pattern = re.compile(
                rf'<input[^>]*name=["\'](?:template_)?{tmpl}\[{unit}\]["\'][^>]*value=["\'](\d+)["\']|'
                rf'<input[^>]*value=["\'](\d+)["\'][^>]*name=["\'](?:template_)?{tmpl}\[{unit}\]["\']',
                re.IGNORECASE,
            )
            m = pattern.search(normalized)
            if m:
                val = next(g for g in m.groups() if g is not None)
                try:
                    templates[tmpl][unit] = int(val)
                except ValueError:
                    templates[tmpl][unit] = 0

    return templates



# Mapeamento de nomes de unidades para identificadores canónicos
UNIT_NAME_TO_KEY: Dict[str, str] = {
    "lanceiro": "spear",
    "lanceiros": "spear",
    "spear": "spear",
    "spearman": "spear",
    "espadachim": "sword",
    "espadachins": "sword",
    "sword": "sword",
    "swordsman": "sword",
    "viking": "axe",
    "vikings": "axe",
    "bárbaro": "axe",
    "barbaro": "axe",
    "axe": "axe",
    "axeman": "axe",
    "arqueiro": "archer",
    "arqueiros": "archer",
    "archer": "archer",
    "explorador": "spy",
    "exploradores": "spy",
    "espião": "spy",
    "espiao": "spy",
    "spy": "spy",
    "scout": "spy",
    "cavalaria leve": "light",
    "cavalarias leves": "light",
    "light": "light",
    "light cavalry": "light",
    "arqueiro a cavalo": "marcher",
    "arqueiros a cavalo": "marcher",
    "marcher": "marcher",
    "mounted archer": "marcher",
    "cavalaria pesada": "heavy",
    "cavalarias pesadas": "heavy",
    "heavy": "heavy",
    "heavy cavalry": "heavy",
    "aríete": "ram",
    "ariete": "ram",
    "aríetes": "ram",
    "arietes": "ram",
    "ram": "ram",
    "catapulta": "catapult",
    "catapultas": "catapult",
    "catapult": "catapult",
    "paladino": "knight",
    "knight": "knight",
    "nobre": "snob",
    "nobres": "snob",
    "snob": "snob",
    "nobleman": "snob",
}


def parse_recruitment_page(html: str) -> Dict[str, Any]:
    """
    Analisa a página de recrutamento militar (screen=barracks, screen=stable ou screen=garage).
    Extrai:
    - available_units: mapa de {unidade: max_recrutavel}
    - queue: lista de ordens em treino com quantidade, timer e hora de conclusão
    - total_in_queue: mapa de {unidade: total_sendo_treinado_na_fila}
    """
    result: Dict[str, Any] = {
        "available_units": {},
        "queue": [],
        "total_in_queue": {u: 0 for u in ALL_UNITS},
    }

    if not html:
        return result

    normalized = html.replace("&amp;", "&")

    # 1. Extração de unidades desbloqueadas e quantidade máxima recrutável
    # Padrão 1: <a id="spear_0_a" ...>(15)</a> ou >15<
    # Padrão 2: <input id="spear_0" name="spear" ... data-max="15" ... />
    # Padrão 3: javascript:insertUnit(...) ou set_max(...)
    for unit_key in ALL_UNITS:
        # Verifica se o input da unidade existe (indica que está desbloqueada no edifício)
        input_match = re.search(
            rf'<input[^>]*(?:name=["\'](?:units\[)?{unit_key}(?:\])?["\']|id=["\']{unit_key}(?:_\d+)?["\'])[^>]*>',
            normalized,
            re.IGNORECASE,
        )
        if not input_match:
            continue

        max_val = 0
        # a) <a id="spear_0_a" ...>(15)</a>
        link_max = re.search(
            rf'id=["\']{unit_key}_\d+_a["\'][^>]*>\s*\(?(\d+)\)?\s*<',
            normalized,
            re.IGNORECASE,
        )
        if link_max:
            try:
                max_val = int(link_max.group(1))
            except ValueError:
                pass
        
        if max_val <= 0:
            # b) data-max="15"
            data_max = re.search(
                rf'name=["\']{unit_key}["\'][^>]*data-max=["\'](\d+)["\']|data-max=["\'](\d+)["\'][^>]*name=["\']{unit_key}["\']',
                normalized,
                re.IGNORECASE,
            )
            if data_max:
                val = next((g for g in data_max.groups() if g is not None), None)
                if val:
                    try:
                        max_val = int(val)
                    except ValueError:
                        pass

        if max_val <= 0:
            # c) javascript:insertUnit(...) ou set_max(...)
            js_max = re.search(
                rf'(?:insertUnit|set_max|selectAllUnits)\([^)]*?["\']?{unit_key}["\']?[^)]*?,\s*(\d+)\)',
                normalized,
                re.IGNORECASE,
            )
            if js_max:
                try:
                    max_val = int(js_max.group(1))
                except ValueError:
                    pass

        # Se o input de recrutamento existe na página mas o número exato do link não foi capturado,
        # define fallback de 999 para permitir o envio do lote pretendido (o servidor valida os recursos)
        if max_val <= 0:
            max_val = 999

        result["available_units"][unit_key] = max_val

    # 2. Extração da fila ativa de recrutamento (#trainqueue_... ou .trainqueue ou linhas de treino)
    # Exemplo: <td>20 Lanceiro</td> ou <td>20 Spear</td> seguido de timer e horário
    queue_row_regex = re.compile(
        r'<tr[^>]*class=["\'](?:lit\s+)?trainqueue_[^"\']*["\'][^>]*>(.*?)</tr>|<tr[^>]*>(.*?<span[^>]*class=["\']timer["\'][^>]*>[\d:]+</span>.*?)</tr>',
        re.DOTALL | re.IGNORECASE,
    )

    for row_m in queue_row_regex.finditer(normalized):
        row_content = row_m.group(1) or row_m.group(2)
        if not row_content:
            continue

        # Procura padrão de quantidade + nome de tropa (ex: "25 Lanceiro", "10 Cavalaria Leve")
        unit_found = None
        count_found = 0

        # Verifica cada unidade conhecida
        for name_key, canonic_key in UNIT_NAME_TO_KEY.items():
            pattern = re.compile(rf'(\d+)\s+{re.escape(name_key)}\b', re.IGNORECASE)
            m = pattern.search(row_content)
            if m:
                count_found = int(m.group(1))
                unit_found = canonic_key
                break

        if not unit_found or count_found <= 0:
            continue

        # Timer
        timer_match = re.search(r'<span[^>]*class=["\']timer["\'][^>]*>([\d:]+)</span>', row_content, re.IGNORECASE)
        timer_str = timer_match.group(1) if timer_match else ""

        # Conclusão / hora
        finish_match = re.search(r'(?:hoje|amanhã|today|tomorrow|[0-9]{1,2}\.[0-9]{1,2}\.)\s*(?:às\s*)?[\d:]+', row_content, re.IGNORECASE)
        finish_time = finish_match.group(0).strip() if finish_match else ""

        # Link de cancelamento se existir
        cancel_match = re.search(r'href=["\']([^"\']*[?&]action=cancel[^"\']*)["\']', row_content, re.IGNORECASE)
        cancel_url = cancel_match.group(1) if cancel_match else None

        result["queue"].append({
            "unit": unit_found,
            "count": count_found,
            "timer_str": timer_str,
            "finish_time": finish_time,
            "cancel_url": cancel_url,
        })
        result["total_in_queue"][unit_found] += count_found

    return result


def parse_quest_screen(html: str, game_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extrai o estado das missões a partir do HTML de 'screen=quest', 'screen=main' e/ou do 'game_data.quest'.
    Identifica missões ativas, recompensas de níveis de edifícios concluídos, recompensas em recursos,
    tropas/população e URLs de claim nativas (action=reward).
    """
    normalized = html.replace("&amp;", "&") if html else ""
    normalized = re.sub(r'<!--.*?-->', '', normalized, flags=re.DOTALL)
    quests: List[Dict[str, Any]] = []
    seen_ids = set()

    # 1. Extração via game_data se disponível
    if game_data and isinstance(game_data, dict):
        q_data = game_data.get("quest") or game_data.get("quests") or game_data.get("Quests")
        if isinstance(q_data, dict):
            raw_list = q_data.get("quests") or q_data.get("list") or q_data
            if isinstance(raw_list, dict):
                raw_list = list(raw_list.values())
            if isinstance(raw_list, list):
                for item in raw_list:
                    if isinstance(item, dict):
                        q_id = str(item.get("id", "")).strip()
                        if not q_id or q_id in seen_ids:
                            continue
                        title = str(item.get("title") or item.get("name") or f"Missão #{q_id}").strip()
                        desc = str(item.get("description") or "").strip()
                        state_str = str(item.get("state", "")).lower()
                        finishable = bool(
                            item.get("finishable")
                            or item.get("completed")
                            or item.get("finished")
                            or item.get("can_be_completed")
                            or item.get("goals_completed") is True
                            or state_str in ("finished", "completed", "claimable")
                        )
                        claim_url = item.get("claim_url") or item.get("url")
                        rewards = item.get("rewards") or item.get("reward") or {}

                        # Suporte a formatos planos e aninhados de recursos
                        res_obj = rewards.get("resources") if isinstance(rewards.get("resources"), dict) else rewards
                        wood = int(res_obj.get("wood", 0) or 0)
                        stone = int(res_obj.get("stone", 0) or 0)
                        iron = int(res_obj.get("iron", 0) or 0)
                        pop = int(rewards.get("pop", 0) or 0)

                        seen_ids.add(q_id)
                        quests.append({
                            "id": q_id,
                            "title": title,
                            "description": desc,
                            "finishable": finishable,
                            "claim_url": claim_url,
                            "rewards": {
                                "wood": wood,
                                "stone": stone,
                                "iron": iron,
                                "pop": pop,
                                "flags": rewards.get("flags", []),
                                "items": rewards.get("items", []),
                                "description": str(rewards.get("description", "")),
                            },
                        })

    # 2. Localização e fatiamento robusto de blocos de missões no HTML
    raw_starts = [
        m
        for m in re.finditer(
            r'<(?:div|tr|li)[^>]*?(?:class=["\'][^"\']*\b(?:quest_item|quest-item|quest_container|quest-container|quest_reward)\b[^"\']*["\']|data-quest-id=["\']\w+["\'])',
            normalized,
            re.IGNORECASE,
        )
    ]
    # Fallback para class com \bquest\b isolado se não encontrar classes específicas
    if not raw_starts:
        raw_starts = [
            m
            for m in re.finditer(
                r'<(?:div|tr|li)[^>]*?class=["\'][^"\']*\bquest\b[^"\']*["\']',
                normalized,
                re.IGNORECASE,
            )
        ]
    block_starts = [m.start() for m in raw_starts]

    claim_btn_regex = re.compile(
        r'<a[^>]*href=["\']([^"\']*[?&]action=(?:claim_reward|claim|reward|claim_quest)[^"\']*)["\'][^>]*>(.*?)</a>',
        re.DOTALL | re.IGNORECASE,
    )

    for i, start_pos in enumerate(block_starts):
        end_pos = block_starts[i + 1] if i + 1 < len(block_starts) else start_pos + 3000
        content = normalized[start_pos:end_pos]

        # Extração de ID
        q_id = None
        id_m = re.search(r'(?:data-quest-id|data-id)=["\'](\w+)["\']', content, re.IGNORECASE)
        if id_m:
            q_id = id_m.group(1)

        claim_match = claim_btn_regex.search(content)
        claim_url = claim_match.group(1) if claim_match else None
        if not q_id and claim_url:
            url_id_m = re.search(r'[?&](?:quest_id|quest|id)=(\w+)', claim_url, re.IGNORECASE)
            if url_id_m:
                q_id = url_id_m.group(1)

        if not q_id:
            # Fallback numérico
            q_id = str(len(quests) + 1)

        if q_id in seen_ids:
            # Se a missão já existe, mas encontramos um claim_url específico no HTML, atualizamos
            for existing_q in quests:
                if existing_q["id"] == q_id:
                    if claim_url and not existing_q["claim_url"]:
                        existing_q["claim_url"] = claim_url
                    if claim_url:
                        existing_q["finishable"] = True
            continue

        title_m = re.search(
            r'<(?:h\d|b|strong|span)[^>]*class=["\']?[^"\']*(?:title|name|quest_name)[^"\']*["\']?[^>]*>(.*?)</(?:h\d|b|strong|span)>',
            content,
            re.IGNORECASE,
        )
        title = title_m.group(1).strip() if title_m else f"Missão #{q_id}"
        title = re.sub(r'<[^>]+>', '', title).strip()

        wood_m = re.search(r'(?:icon header wood|cost_wood|wood)[^>]*>.*?([\d\.]+)', content, re.IGNORECASE)
        stone_m = re.search(r'(?:icon header stone|cost_stone|stone)[^>]*>.*?([\d\.]+)', content, re.IGNORECASE)
        iron_m = re.search(r'(?:icon header iron|cost_iron|iron)[^>]*>.*?([\d\.]+)', content, re.IGNORECASE)
        pop_m = re.search(r'(?:icon header pop|cost_pop|pop|população)[^>]*>.*?([\d\.]+)', content, re.IGNORECASE)

        def clean_val(m):
            if not m:
                return 0
            val_str = m.group(1).replace(".", "").strip()
            return int(val_str) if val_str.isdigit() else 0

        wood = clean_val(wood_m)
        stone = clean_val(stone_m)
        iron = clean_val(iron_m)
        pop = clean_val(pop_m)

        finishable = bool(claim_url) or bool(
            re.search(
                r'class=["\'][^"\']*\b(?:quest_complete|quest_finished|btn-confirm-yes|claim|reward_button|btn-reward)\b|<a[^>]*>(?:Receber|Resgatar|Claim|Reclamar|Recompensa)\b',
                content,
                re.IGNORECASE,
            )
        )

        seen_ids.add(q_id)
        quests.append({
            "id": q_id,
            "title": title,
            "description": "",
            "finishable": finishable,
            "claim_url": claim_url,
            "rewards": {
                "wood": wood,
                "stone": stone,
                "iron": iron,
                "pop": pop,
                "flags": [],
                "items": [],
                "description": "",
            },
        })

    # 3. Varredura global de links/botões de claim isolados no HTML (ex: screen=main ou botões soltos)
    for c_match in claim_btn_regex.finditer(normalized):
        url = c_match.group(1)
        id_m = re.search(r'[?&](?:quest_id|quest|id)=(\w+)', url, re.IGNORECASE)
        q_id = id_m.group(1) if id_m else None
        if q_id and q_id in seen_ids:
            # Atualiza claim_url
            for existing_q in quests:
                if existing_q["id"] == q_id:
                    existing_q["claim_url"] = url
                    existing_q["finishable"] = True
            continue

        if not q_id:
            q_id = str(len(quests) + 1)
        if q_id in seen_ids:
            continue

        seen_ids.add(q_id)
        quests.append({
            "id": q_id,
            "title": f"Recompensa #{q_id}",
            "description": "",
            "finishable": True,
            "claim_url": url,
            "rewards": {
                "wood": 0,
                "stone": 0,
                "iron": 0,
                "pop": 0,
                "flags": [],
                "items": [],
                "description": "",
            },
        })

    # 4. Varredura de chamadas JavaScript Quest.reward(ID) ou Quest.claim(ID)
    js_claim_matches = re.finditer(
        r'Quest\.(?:reward|claim)\((?:["\']?(\w+)["\']?|(\d+))\)',
        normalized,
        re.IGNORECASE,
    )
    for js_m in js_claim_matches:
        q_id = js_m.group(1) or js_m.group(2)
        if q_id:
            q_id = str(q_id)
            if q_id in seen_ids:
                for existing_q in quests:
                    if existing_q["id"] == q_id:
                        existing_q["finishable"] = True
            else:
                seen_ids.add(q_id)
                quests.append({
                    "id": q_id,
                    "title": f"Recompensa #{q_id}",
                    "description": "",
                    "finishable": True,
                    "claim_url": f"/game.php?screen=quest&action=reward&quest_id={q_id}",
                    "rewards": {
                        "wood": 0,
                        "stone": 0,
                        "iron": 0,
                        "pop": 0,
                        "flags": [],
                        "items": [],
                        "description": "",
                    },
                })

    finishable_count = sum(1 for q in quests if q["finishable"])
    return {
        "quests": quests,
        "finishable_count": finishable_count,
    }


def parse_daily_bonus_screen(html: str) -> Dict[str, Any]:
    """
    Extrai o estado do Bónus Diário / Baús de Login (screen=daily_bonus).
    Verifica se há baú gratuito disponível para abertura ou se já foi recolhido hoje.
    """
    normalized = html.replace("&amp;", "&")

    open_match = re.search(
        r'<a[^>]*href=["\']([^"\']*[?&]action=(?:open_chest|open|claim|unlock_chest)[^"\']*)["\'][^>]*>(.*?)</a>',
        normalized,
        re.IGNORECASE,
    )
    open_url = open_match.group(1) if open_match else None

    is_opened_today = bool(re.search(
        r'(?:já\s+recolheste|já\s+aberto|já\s+recolhido|volta\s+amanhã|come\s+back\s+tomorrow|already\s+opened|chest_opened)',
        normalized,
        re.IGNORECASE,
    ))

    can_open = bool(open_url) and not is_opened_today

    chests = []
    chest_matches = re.finditer(
        r'<(?:div|a)[^>]*class=["\'][^"\']*(?:chest|daily_bonus)[^"\']*["\'][^>]*>(.*?)</(?:div|a)>',
        normalized,
        re.DOTALL | re.IGNORECASE,
    )
    for idx, c in enumerate(chest_matches, start=1):
        chests.append({
            "id": idx,
            "raw": c.group(1)[:100],
        })

    return {
        "can_open": can_open,
        "open_url": open_url,
        "is_opened_today": is_opened_today,
        "chests": chests,
    }


def parse_inventory_screen(html: str) -> Dict[str, Any]:
    """
    Extrai a lista de itens presentes no Inventário do jogador (screen=inventory).
    Identifica itens disponíveis, quantidade, descrição e URL de uso manual.
    """
    normalized = html.replace("&amp;", "&")
    items: List[Dict[str, Any]] = []
    seen_ids = set()

    item_starts = [
        m.start()
        for m in re.finditer(
            r'<(?:div|tr|li)[^>]*class=["\'][^"\']*(?:inventory_item|item_container|item)[^"\']*["\']',
            normalized,
            re.IGNORECASE,
        )
    ]

    for i, start_pos in enumerate(item_starts):
        end_pos = item_starts[i + 1] if i + 1 < len(item_starts) else start_pos + 3000
        content = normalized[start_pos:end_pos]

        id_m = re.search(r'(?:data-item-id|data-id)=["\']([^"\']+)["\']', content, re.IGNORECASE)
        use_m = re.search(
            r'<a[^>]*href=["\']([^"\']*[?&]action=(?:use_item|use)[^"\']*)["\'][^>]*>(.*?)</a>',
            content,
            re.IGNORECASE,
        )
        use_url = use_m.group(1) if use_m else None

        item_id = id_m.group(1) if id_m else None
        if not item_id and use_url:
            url_id_m = re.search(r'[?&](?:item_id|item|id)=([^&"\']+)', use_url, re.IGNORECASE)
            if url_id_m:
                item_id = url_id_m.group(1)

        if not item_id or item_id in seen_ids:
            continue

        seen_ids.add(item_id)

        name_m = re.search(
            r'<(?:h\d|b|strong|span)[^>]*class=["\']?[^"\']*(?:item_name|title|name)[^"\']*["\']?[^>]*>(.*?)</(?:h\d|b|strong|span)>',
            content,
            re.IGNORECASE,
        )
        name = name_m.group(1).strip() if name_m else item_id
        name = re.sub(r'<[^>]+>', '', name).strip()

        count_m = re.search(r'(?:count|qtd|quantidade|badge)[^>]*>.*?(\d+)|(\d+)\s*x', content, re.IGNORECASE)
        count = 1
        if count_m:
            c_val = count_m.group(1) or count_m.group(2)
            if c_val and c_val.isdigit():
                count = int(c_val)

        desc_m = re.search(
            r'<(?:p|span|div)[^>]*class=["\']?[^"\']*(?:desc|description)[^"\']*["\']?[^>]*>(.*?)</(?:p|span|div)>',
            content,
            re.IGNORECASE,
        )
        desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip() if desc_m else ""

        can_use = bool(use_url)

        items.append({
            "id": item_id,
            "name": name,
            "count": count,
            "description": desc,
            "can_use": can_use,
            "use_url": use_url,
        })

    return {"items": items}


def parse_map_response(data: Any) -> List[Dict[str, Any]]:
    """
    Analisa a resposta de dados do mapa do Tribal Wars com suporte total para:
    1. Respostas de setores oficiais do Tribal Wars (/map.php?v=2&e=... e TWMap.sectorPrefech no HTML).
    2. Dumps mundiais públicos em formato CSV (/map/village.txt).
    3. Respostas AJAX legadas e estruturas serializadas em dicionários/listas.
    4. Fallback por regex para marcação HTML.
    """
    villages: List[Dict[str, Any]] = []
    seen_ids = set()
    json_obj = None

    def _parse_sector_dict(sec: Dict[str, Any]) -> None:
        """Processa um setor 20x20 oficial do Tribal Wars."""
        d = sec.get("data", sec)
        bx = int(d.get("x", sec.get("x", 0)))
        by = int(d.get("y", sec.get("y", 0)))
        v_list = d.get("villages", [])
        p_dict = d.get("players", {})
        a_dict = d.get("allies", {})

        if isinstance(v_list, list):
            for dx, y_dict in enumerate(v_list):
                if not isinstance(y_dict, dict):
                    continue
                ax = bx + dx
                for dy_str, v_info in y_dict.items():
                    try:
                        ay = by + int(dy_str)
                    except ValueError:
                        continue
                    if not isinstance(v_info, (list, tuple)) or len(v_info) < 2:
                        continue
                    try:
                        vid = int(v_info[0])
                    except (ValueError, TypeError):
                        continue
                    if vid in seen_ids:
                        continue
                    seen_ids.add(vid)

                    raw_name = v_info[2] if len(v_info) > 2 else ""
                    raw_pts = v_info[3] if len(v_info) > 3 else 0
                    raw_pid = v_info[4] if len(v_info) > 4 else 0
                    bonus_info = v_info[6] if len(v_info) > 6 else None
                    bonus_id = int(v_info[8]) if (len(v_info) > 8 and isinstance(v_info[8], int)) else (1 if bonus_info else 0)

                    try:
                        pid = int(raw_pid)
                    except (ValueError, TypeError):
                        pid = 0
                    try:
                        pts = int(raw_pts)
                    except (ValueError, TypeError):
                        pts = 0

                    p_data = p_dict.get(str(pid)) or p_dict.get(pid) or []
                    p_name = str(p_data[0]) if len(p_data) >= 1 else ""
                    t_id = int(p_data[2]) if (len(p_data) >= 3 and str(p_data[2]).isdigit()) else 0

                    a_data = a_dict.get(str(t_id)) or a_dict.get(t_id) or []
                    t_tag = str(a_data[2]) if len(a_data) >= 3 else (str(a_data[0]) if len(a_data) >= 1 else "")

                    vname = str(raw_name) if (raw_name and raw_name != 0 and raw_name != "0") else ("Aldeia bónus" if bonus_id > 0 else "Aldeia de bárbaros")

                    villages.append({
                        "id": vid,
                        "x": ax,
                        "y": ay,
                        "name": vname,
                        "points": pts,
                        "player_id": pid,
                        "player_name": p_name,
                        "tribe_id": t_id,
                        "tribe_tag": t_tag,
                        "bonus_id": bonus_id,
                    })

    if isinstance(data, (dict, list)):
        json_obj = data
    elif isinstance(data, str):
        raw_str = data.strip()
        # 1. Verifica se é dump CSV (/map/village.txt)
        if "\n" in raw_str and not raw_str.startswith("<") and not raw_str.startswith("{") and not raw_str.startswith("["):
            first_line = raw_str.split("\n")[0].strip()
            parts = first_line.split(",")
            if len(parts) >= 6 and parts[0].isdigit() and parts[2].isdigit():
                for line in raw_str.splitlines():
                    p = line.strip().split(",")
                    if len(p) >= 6:
                        try:
                            vid = int(p[0])
                            vname = urllib.parse.unquote_plus(p[1])
                            vx = int(p[2])
                            vy = int(p[3])
                            pid = int(p[4])
                            pts = int(p[5])
                            if vid not in seen_ids:
                                seen_ids.add(vid)
                                villages.append({
                                    "id": vid,
                                    "x": vx,
                                    "y": vy,
                                    "name": vname,
                                    "points": pts,
                                    "player_id": pid,
                                    "player_name": "" if pid == 0 else f"Jogador {pid}",
                                    "tribe_id": 0,
                                    "tribe_tag": "",
                                    "bonus_id": 0,
                                })
                        except (ValueError, IndexError):
                            pass
                return villages

        # 2. Tenta decodificar JSON direto
        if (raw_str.startswith("{") and raw_str.endswith("}")) or (raw_str.startswith("[") and raw_str.endswith("]")):
            try:
                json_obj = json.loads(raw_str)
            except Exception:
                json_obj = None

        # 3. Procura variáveis JS no HTML do jogo
        if json_obj is None:
            js_patterns = [
                r'TWMap\.sectorPrefech\s*=\s*(\[.*?\]);',
                r'TWMap\.sectorData\s*=\s*(\{.*?\});',
                r'TWMap\.initMap\s*\(\s*(\{.*?\})\s*\)',
                r'(?:var|let|const)\s+map_data\s*=\s*(\{.*?\});',
                r'TWMap\.mapData\s*=\s*(\{.*?\});',
            ]
            for pat in js_patterns:
                m = re.search(pat, data, re.DOTALL)
                if m:
                    try:
                        json_obj = json.loads(m.group(1))
                        if json_obj:
                            break
                    except Exception:
                        continue

    # Processamento se o JSON for lista de setores (formato /map.php ou TWMap.sectorPrefech)
    if isinstance(json_obj, list):
        is_sector_list = any(isinstance(item, dict) and ("tiles" in item or "data" in item) for item in json_obj)
        if is_sector_list:
            for item in json_obj:
                if isinstance(item, dict):
                    _parse_sector_dict(item)
            return villages

        # Caso contrário, trata como lista legada de aldeias em formato plano
        for v_item in json_obj:
            if isinstance(v_item, dict):
                v_id = int(v_item.get("id", 0))
                x = int(v_item.get("x", 0))
                y = int(v_item.get("y", 0))
                name = str(v_item.get("name") or f"Aldeia ({x}|{y})")
                points = int(v_item.get("points", 0))
                player_id = int(v_item.get("player_id", v_item.get("player", 0)) or 0)
                player_name = str(v_item.get("player_name", ""))
                tribe_id = int(v_item.get("tribe_id", v_item.get("tribe", 0)) or 0)
                tribe_tag = str(v_item.get("tribe_tag", ""))
                bonus_id = int(v_item.get("bonus_id", v_item.get("bonus", 0)) or 0)

                if v_id and v_id not in seen_ids:
                    seen_ids.add(v_id)
                    villages.append({
                        "id": v_id,
                        "x": x,
                        "y": y,
                        "name": name,
                        "points": points,
                        "player_id": player_id,
                        "player_name": player_name,
                        "tribe_id": tribe_id,
                        "tribe_tag": tribe_tag,
                        "bonus_id": bonus_id,
                    })
        return villages

    # Processamento de JSON quando é dicionário
    if isinstance(json_obj, dict):
        if "data" in json_obj and isinstance(json_obj["data"], dict) and "villages" in json_obj["data"]:
            _parse_sector_dict(json_obj)
            return villages

        raw_v_list = json_obj.get("villages")
        if isinstance(raw_v_list, list) and raw_v_list and isinstance(raw_v_list[0], dict) and "data" not in json_obj:
            # Lista de colunas de setor
            if any(k.isdigit() for k in raw_v_list[0].keys()):
                _parse_sector_dict({"data": json_obj})
                return villages

        # Formato legado {villages: {...}, players: {...}, allies: {...}}
        players_data = json_obj.get("players", {})
        allies_data = json_obj.get("allies", {})

        def get_player_info(p_id: int) -> Tuple[str, int]:
            p_val = players_data.get(str(p_id)) or players_data.get(p_id)
            if not p_val:
                return ("", 0)
            if isinstance(p_val, (list, tuple)) and len(p_val) >= 1:
                p_name = str(p_val[0])
                t_id = int(p_val[2]) if len(p_val) >= 3 and str(p_val[2]).isdigit() else 0
                return (p_name, t_id)
            if isinstance(p_val, dict):
                p_name = str(p_val.get("name", ""))
                t_id = int(p_val.get("tribe_id", 0) or p_val.get("tribe", 0))
                return (p_name, t_id)
            return (str(p_val), 0)

        def get_tribe_tag(t_id: int) -> str:
            t_val = allies_data.get(str(t_id)) or allies_data.get(t_id)
            if not t_val:
                return ""
            if isinstance(t_val, (list, tuple)) and len(t_val) >= 2:
                return str(t_val[1])
            if isinstance(t_val, dict):
                return str(t_val.get("tag", "") or t_val.get("name", ""))
            return str(t_val)

        raw_villages = json_obj.get("villages", {})
        if isinstance(raw_villages, dict):
            for v_id_str, v_info in raw_villages.items():
                try:
                    v_id = int(v_id_str)
                except ValueError:
                    v_id = 0

                if isinstance(v_info, (list, tuple)) and len(v_info) >= 2:
                    x = int(v_info[0])
                    y = int(v_info[1])
                    name = str(v_info[2]) if len(v_info) >= 3 else f"Aldeia ({x}|{y})"
                    points = int(v_info[3]) if len(v_info) >= 4 and str(v_info[3]).isdigit() else 0
                    player_id = int(v_info[4]) if len(v_info) >= 5 and str(v_info[4]).isdigit() else 0
                    tribe_id = int(v_info[5]) if len(v_info) >= 6 and str(v_info[5]).isdigit() else 0
                    bonus_id = int(v_info[6]) if len(v_info) >= 7 and str(v_info[6]).isdigit() else 0

                    p_name, p_tribe = get_player_info(player_id)
                    if not tribe_id and p_tribe:
                        tribe_id = p_tribe
                    tribe_tag = get_tribe_tag(tribe_id)

                    if v_id and v_id not in seen_ids:
                        seen_ids.add(v_id)
                        villages.append({
                            "id": v_id,
                            "x": x,
                            "y": y,
                            "name": name,
                            "points": points,
                            "player_id": player_id,
                            "player_name": p_name,
                            "tribe_id": tribe_id,
                            "tribe_tag": tribe_tag,
                            "bonus_id": bonus_id,
                        })

                elif isinstance(v_info, dict):
                    v_id = int(v_info.get("id", v_id))
                    x = int(v_info.get("x", 0))
                    y = int(v_info.get("y", 0))
                    name = str(v_info.get("name") or f"Aldeia ({x}|{y})")
                    points = int(v_info.get("points", 0))
                    player_id = int(v_info.get("player_id", v_info.get("player", 0)) or 0)
                    tribe_id = int(v_info.get("tribe_id", v_info.get("tribe", 0)) or 0)
                    bonus_id = int(v_info.get("bonus_id", v_info.get("bonus", 0)) or 0)

                    p_name, p_tribe = get_player_info(player_id)
                    if not tribe_id and p_tribe:
                        tribe_id = p_tribe
                    tribe_tag = get_tribe_tag(tribe_id)

                    if v_id and v_id not in seen_ids:
                        seen_ids.add(v_id)
                        villages.append({
                            "id": v_id,
                            "x": x,
                            "y": y,
                            "name": name,
                            "points": points,
                            "player_id": player_id,
                            "player_name": p_name,
                            "tribe_id": tribe_id,
                            "tribe_tag": tribe_tag,
                            "bonus_id": bonus_id,
                        })

        elif isinstance(raw_villages, list):
            for v_item in raw_villages:
                if isinstance(v_item, dict):
                    v_id = int(v_item.get("id", 0))
                    x = int(v_item.get("x", 0))
                    y = int(v_item.get("y", 0))
                    name = str(v_item.get("name") or f"Aldeia ({x}|{y})")
                    points = int(v_item.get("points", 0))
                    player_id = int(v_item.get("player_id", v_item.get("player", 0)) or 0)
                    tribe_id = int(v_item.get("tribe_id", v_item.get("tribe", 0)) or 0)
                    bonus_id = int(v_item.get("bonus_id", v_item.get("bonus", 0)) or 0)

                    p_name, p_tribe = get_player_info(player_id)
                    if not tribe_id and p_tribe:
                        tribe_id = p_tribe
                    tribe_tag = get_tribe_tag(tribe_id)

                    if v_id and v_id not in seen_ids:
                        seen_ids.add(v_id)
                        villages.append({
                            "id": v_id,
                            "x": x,
                            "y": y,
                            "name": name,
                            "points": points,
                            "player_id": player_id,
                            "player_name": p_name,
                            "tribe_id": tribe_id,
                            "tribe_tag": tribe_tag,
                            "bonus_id": bonus_id,
                        })

    # Fallback de extração via regex em tags HTML do mapa
    if not villages and isinstance(data, str):
        village_matches = re.finditer(
            r'<(?:div|a|td)[^>]*?(?:data-village-id|data-id)=["\'](\d+)["\'][^>]*>(.*?)</(?:div|a|td)>',
            data,
            re.DOTALL | re.IGNORECASE,
        )
        for vm in village_matches:
            v_id = int(vm.group(1))
            content = vm.group(2)
            if v_id in seen_ids:
                continue

            coord_m = re.search(r'\((\d{1,3})\|(\d{1,3})\)', content) or re.search(
                r'data-x=["\'](\d+)["\']\s+data-y=["\'](\d+)["\']', content, re.IGNORECASE
            )
            if not coord_m:
                continue

            x = int(coord_m.group(1))
            y = int(coord_m.group(2))

            name_m = re.search(r'class=["\']?[^"\']*(?:village_name|title)[^"\']*["\']?[^>]*>(.*?)</', content, re.IGNORECASE)
            name = name_m.group(1).strip() if name_m else f"Aldeia ({x}|{y})"
            name = re.sub(r'<[^>]+>', '', name).strip()

            is_barb = "bárbar" in content.lower() or "barbarian" in content.lower()
            player_id = 0 if is_barb else 1
            player_name = "" if is_barb else "Desconhecido"

            bonus_id = 1 if "bonus" in content.lower() else 0

            seen_ids.add(v_id)
            villages.append({
                "id": v_id,
                "x": x,
                "y": y,
                "name": name,
                "points": 0,
                "player_id": player_id,
                "player_name": player_name,
                "tribe_id": 0,
                "tribe_tag": "",
                "bonus_id": bonus_id,
            })

    return villages


def parse_market_screen(html: str) -> Dict[str, Any]:
    """
    Extrai informações da Praça do Mercado (screen=market):
    - Mercadores disponíveis e mercadores totais
    - Transportes em trânsito (a enviar ou a receber)
    """
    merchants_available = 0
    merchants_total = 0

    # 1. Extração de mercadores via ID direto ou regex no texto
    avail_m = re.search(
        r'id=["\']market_merchant_available_count["\'][^>]*>(\d+)</span>',
        html,
        re.IGNORECASE,
    )
    total_m = re.search(
        r'id=["\']market_merchant_total_count["\'][^>]*>(\d+)</span>',
        html,
        re.IGNORECASE,
    )

    if avail_m and total_m:
        try:
            merchants_available = int(avail_m.group(1))
            merchants_total = int(total_m.group(1))
        except ValueError:
            pass
    else:
        # Fallback para regex baseado em texto "Mercadores: X/Y" ou "Merchants: X/Y"
        fallback_m = re.search(
            r'(?:Mercadores|Merchants):\s*(?:<[^>]+>\s*)*(\d+)\s*/\s*(\d+)',
            html,
            re.IGNORECASE,
        )
        if fallback_m:
            try:
                merchants_available = int(fallback_m.group(1))
                merchants_total = int(fallback_m.group(2))
            except ValueError:
                pass

    # 2. Extração de transportes em trânsito
    transports: List[Dict[str, Any]] = []

    # Procura por blocos de linha de tabela contendo transportes
    row_matches = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)
    for row in row_matches:
        row_lower = row.lower()
        if "transporte" not in row_lower and "transport" not in row_lower:
            continue

        is_incoming = bool(re.search(r'\b(?:de|from)\b', row_lower))
        is_outgoing = bool(re.search(r'\b(?:para|to)\b', row_lower))
        direction = "incoming" if is_incoming and not is_outgoing else "outgoing"

        # Coordenadas da aldeia (X|Y)
        coord_m = re.search(r'\((\d{1,3})\|(\d{1,3})\)', row)
        if not coord_m:
            continue
        target_x = int(coord_m.group(1))
        target_y = int(coord_m.group(2))

        # Nome da aldeia e ID
        village_id = 0
        id_m = re.search(r'(?:screen=info_village&(?:amp;)?id|target|village_id)[=:](\d+)', row, re.IGNORECASE)
        if not id_m:
            id_m = re.search(r'(?:[?&]id=)(\d+)', row, re.IGNORECASE)
        if id_m:
            village_id = int(id_m.group(1))

        name_m = re.search(r'>([^<]+)\s*\(\d{1,3}\|\d{1,3}\)', row)
        village_name = name_m.group(1).strip() if name_m else f"Aldeia ({target_x}|{target_y})"

        # Quantidades de recursos
        def _extract_res(res_name: str) -> int:
            patterns = [
                rf'{res_name}["\'][^>]*>\s*</span>\s*([\d\.]+)',
                rf'class=["\']?[^"\']*{res_name}[^"\']*["\']?[^>]*>[^<]*</[^>]+>\s*([\d\.]+)',
                rf'{res_name}[:\s]+([\d\.]+)',
            ]
            for p in patterns:
                m = re.search(p, row, re.IGNORECASE)
                if m:
                    try:
                        return int(m.group(1).replace(".", ""))
                    except ValueError:
                        pass
            return 0

        wood = _extract_res("wood")
        stone = _extract_res("stone")
        iron = _extract_res("iron")

        # Tempo de chegada / duração
        arrival_time = ""
        timer_m = re.search(r'(?:<span[^>]*class=["\']timer["\'][^>]*>|chegada|arrival:?\s*)([\d:]+)', row, re.IGNORECASE)
        if timer_m:
            arrival_time = timer_m.group(1).strip()
        else:
            time_m = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)', row)
            if time_m:
                arrival_time = time_m.group(1).strip()

        total_res = wood + stone + iron
        merchants_count = max(1, (total_res + 999) // 1000) if total_res > 0 else 1

        transports.append({
            "direction": direction,
            "village_id": village_id,
            "village_name": village_name,
            "coords": (target_x, target_y),
            "wood": wood,
            "stone": stone,
            "iron": iron,
            "total_resources": total_res,
            "arrival_time": arrival_time,
            "merchants_count": merchants_count,
        })

    return {
        "merchants_available": merchants_available,
        "merchants_total": merchants_total,
        "transports": transports,
    }


def parse_market_offers(html: str) -> List[Dict[str, Any]]:
    """
    Extrai ofertas publicadas no mercado próprio (screen=market&mode=own_offer).
    """
    offers: List[Dict[str, Any]] = []
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)
    for row in rows:
        id_m = re.search(
            r'(?:name=["\']id_(\d+)["\']|id=["\']offer_(\d+)["\']|action=delete_offer&(?:amp;)?id=(\d+))',
            row,
            re.IGNORECASE,
        )
        if not id_m:
            continue
        offer_id = int(id_m.group(1) or id_m.group(2) or id_m.group(3))

        res_icons = re.findall(r'class=["\']?[^"\']*(wood|stone|iron)[^"\']*["\']?', row, re.IGNORECASE)
        numbers = re.findall(r'>\s*([\d\.]+)\s*<', row)
        cleaned_numbers = []
        for n in numbers:
            try:
                cleaned_numbers.append(int(n.replace(".", "")))
            except ValueError:
                pass

        sell_res = res_icons[0].lower() if len(res_icons) > 0 else "wood"
        buy_res = res_icons[1].lower() if len(res_icons) > 1 else "stone"
        sell_amount = cleaned_numbers[0] if len(cleaned_numbers) > 0 else 1000
        buy_amount = cleaned_numbers[1] if len(cleaned_numbers) > 1 else 1000

        ratio = round(buy_amount / sell_amount, 2) if sell_amount > 0 else 1.0

        multi_m = re.search(r'>\s*(\d+)x\s*<', row, re.IGNORECASE)
        available_offers = int(multi_m.group(1)) if multi_m else 1

        offers.append({
            "id": offer_id,
            "sell_res": sell_res,
            "sell_amount": sell_amount,
            "buy_res": buy_res,
            "buy_amount": buy_amount,
            "ratio": ratio,
            "available_offers": available_offers,
        })

    return offers






