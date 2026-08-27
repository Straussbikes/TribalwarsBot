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
