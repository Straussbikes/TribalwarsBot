"""
Tribal Wars Mobile Automation Engine - Parsers de Dados e Evasão
Extração resiliente de 'game_data', tokens CSRF, recursos e deteção de bot protect.
"""

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from engine.core.models import Resources, VillageData, PlayerData

logger = logging.getLogger(__name__)

# Regex robusto para localizar o objeto JavaScript global 'game_data'
GAME_DATA_REGEX = re.compile(
    r"(?:var\s+game_data\s*=|TribalWars\.updateGameData\()\s*(\{.+?\})\s*;",
    re.DOTALL,
)

# Regex de fallback para extração direta de chaves individuais do game_data
CSRF_REGEX = re.compile(r'["\']csrf["\']\s*:\s*["\']([a-f0-9]+)["\']', re.IGNORECASE)
VILLAGE_ID_REGEX = re.compile(r'["\']village["\']\s*:\s*\{[^}]*?["\']id["\']\s*:\s*(\d+)', re.IGNORECASE)
RESOURCE_SPAN_REGEX = {
    "wood": re.compile(r'<span[^>]*id=["\']wood["\'][^>]*>([\d\.]+)</span>', re.IGNORECASE),
    "stone": re.compile(r'<span[^>]*id=["\']stone["\'][^>]*>([\d\.]+)</span>', re.IGNORECASE),
    "iron": re.compile(r'<span[^>]*id=["\']iron["\'][^>]*>([\d\.]+)</span>', re.IGNORECASE),
    "storage": re.compile(r'<span[^>]*id=["\']storage["\'][^>]*>([\d\.]+)</span>', re.IGNORECASE),
    "pop_current": re.compile(r'<span[^>]*id=["\']pop_current_label["\'][^>]*>([\d\.]+)</span>', re.IGNORECASE),
    "pop_max": re.compile(r'<span[^>]*id=["\']pop_max_label["\'][^>]*>([\d\.]+)</span>', re.IGNORECASE),
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
    """
    if not html:
        return None

    match = GAME_DATA_REGEX.search(html)
    if match:
        raw_json = match.group(1)
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError:
            # Em versões mobile antigas, chaves JS podem não conter aspas perfeitas
            try:
                # Tenta reparar JSON com regex básico
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
    r'<tr[^>]*id=["\']main_buildrow_([a-z_]+)["\'][^>]*>(.*?)</tr>',
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


def parse_build_queue(html: str) -> List[Dict[str, Any]]:
    """
    Extrai as ordens ativas na fila de construção do Edifício Principal.
    Retorna uma lista de dicionários com: order_id, building_raw, target_level, timer_str, cancel_url.
    """
    queue: List[Dict[str, Any]] = []
    if not html:
        return queue

    # Normaliza entidades HTML comuns em URLs
    normalized_html = html.replace("&amp;", "&")

    # Busca a tabela ou seção do buildqueue
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
        preceding_text = search_scope[start_pos:link_match.start()]

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

        queue.append({
            "order_id": order_id,
            "building_raw": b_name_raw,
            "target_level": target_lvl,
            "timer_str": timer_str,
            "cancel_url": full_cancel_url,
        })

    return queue


def parse_building_upgrades(html: str) -> Dict[str, Dict[str, Any]]:
    """
    Extrai os custos de melhoria, requisitos e estado de elegibilidade de cada edifício.
    """
    upgrades: Dict[str, Dict[str, Any]] = {}
    if not html:
        return upgrades

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

        # Link de construção
        build_link_match = re.search(
            r'<a[^>]*href=["\']([^"\']*[?&]action=build[^"\']*)["\'][^>]*>',
            content,
            re.IGNORECASE,
        )
        can_build = build_link_match is not None
        build_url = build_link_match.group(1) if build_link_match else None

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

