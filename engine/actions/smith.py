"""
Tribal Wars Mobile Automation Engine - SmithManager (screen=smith)
Gestão do Ferreiro e Pesquisa Tecnológica Automática de Unidades Militares.
Inicia automaticamente a pesquisa de tropas necessárias para o modelo da aldeia
assim que os pré-requisitos de edifícios e recursos forem alcançados.
"""

import asyncio
from dataclasses import dataclass, field
import json
import logging
import re
from typing import Any, Dict, List, Optional
import urllib.parse

from engine.core.account import TribalAccount
from engine.utils.parsers import ALL_UNITS, parse_timer_to_seconds
from engine.utils.timing import get_click_jitter

logger = logging.getLogger(__name__)


# Mapeamento de nomes de unidades no Ferreiro para chaves canónicas
SMITH_UNIT_ALIASES: Dict[str, str] = {
    "spear": "spear",
    "lanceiro": "spear",
    "sword": "sword",
    "espadachim": "sword",
    "espada": "sword",
    "axe": "axe",
    "bárbaro": "axe",
    "barbaro": "axe",
    "viking": "axe",
    "machado": "axe",
    "archer": "archer",
    "arqueiro": "archer",
    "spy": "spy",
    "batedor": "spy",
    "espião": "spy",
    "espiao": "spy",
    "explorador": "spy",
    "light": "light",
    "cavalaria leve": "light",
    "cav_leve": "light",
    "marcher": "marcher",
    "arqueiro a cavalo": "marcher",
    "heavy": "heavy",
    "cavalaria pesada": "heavy",
    "cav_pesada": "heavy",
    "ram": "ram",
    "aríete": "ram",
    "ariete": "ram",
    "catapult": "catapult",
    "catapulta": "catapult",
}


@dataclass
class ResearchOrder:
    """Representação de uma tecnologia militar em pesquisa no Ferreiro."""
    unit: str
    timer_str: str = ""
    timer_seconds: Optional[int] = None
    finish_time: str = ""
    cancel_url: Optional[str] = None


@dataclass
class SmithUnitInfo:
    """Informações de pesquisa de uma determinada unidade no Ferreiro."""
    unit: str
    level: int = 0
    status: str = "unavailable"  # 'researched', 'researching', 'can_research', 'unavailable'
    wood: int = 0
    stone: int = 0
    iron: int = 0
    research_url: Optional[str] = None
    error_reason: Optional[str] = None

    @property
    def is_researched(self) -> bool:
        return self.status == "researched" or self.level >= 1

    @property
    def is_researching(self) -> bool:
        return self.status == "researching"

    @property
    def can_research(self) -> bool:
        return self.status == "can_research"


@dataclass
class SmithState:
    """Estado consolidado do Ferreiro para uma aldeia."""
    village_id: int
    smith_level: int = 0
    units: Dict[str, SmithUnitInfo] = field(default_factory=dict)
    queue: List[ResearchOrder] = field(default_factory=list)

    @property
    def is_researching_any(self) -> bool:
        return len(self.queue) > 0


def parse_smith_page(html: str) -> Dict[str, Any]:
    """
    Analisa o ecrã do Ferreiro (screen=smith).
    Extrai o estado de pesquisa de cada tropa (researched, researching, can_research, unavailable),
    custos de pesquisa e ordens ativas na fila.
    """
    result: Dict[str, Any] = {
        "units": {},
        "queue": [],
    }

    if not html:
        return result

    normalized = html.replace("&amp;", "&")

    # 1. Extração da fila de pesquisa ativa (se houver)
    for tr_match in re.finditer(r'<tr[^>]*>(?:(?!</tr>).)*?</tr>', normalized, re.DOTALL | re.IGNORECASE):
        row_content = tr_match.group(0)
        if "action=cancel" not in row_content:
            continue

        unit_found = None
        id_m = re.search(r'[?&]id=([a-z_]+)', row_content, re.IGNORECASE)
        if id_m:
            raw_id = id_m.group(1).lower()
            unit_found = SMITH_UNIT_ALIASES.get(raw_id, raw_id)

        if not unit_found:
            for alias, canonic in SMITH_UNIT_ALIASES.items():
                if re.search(rf'\b{re.escape(alias)}\b', row_content, re.IGNORECASE):
                    unit_found = canonic
                    break

        if unit_found:
            timer_m = re.search(r'<span[^>]*class=["\']timer["\'][^>]*>([\d:]+)</span>', row_content, re.IGNORECASE)
            timer_str = timer_m.group(1) if timer_m else ""
            cancel_m = re.search(r'<a[^>]*href=["\']([^"\']*[?&]action=cancel[^"\']*)["\']', row_content, re.IGNORECASE)
            cancel_url = cancel_m.group(1) if cancel_m else None

            result["queue"].append({
                "unit": unit_found,
                "timer_str": timer_str,
                "timer_seconds": parse_timer_to_seconds(timer_str),
                "cancel_url": cancel_url,
            })

    researching_units = {q["unit"] for q in result["queue"]}

    # 2. Extração do estado de cada unidade militar no Ferreiro
    for canonic_key in ALL_UNITS:
        # Se está na fila de pesquisa ativa
        if canonic_key in researching_units:
            result["units"][canonic_key] = {
                "unit": canonic_key,
                "level": 0,
                "status": "researching",
                "wood": 0,
                "stone": 0,
                "iron": 0,
                "research_url": None,
            }
            continue

        # Procura a linha ou bloco da unidade
        unit_block_regex = re.compile(
            rf'<tr[^>]*?(?:id=["\'](?:unit_smith_|unit_){canonic_key}["\']|data-unit=["\']{canonic_key}["\'])[^>]*>(?:(?!</tr>).)*?</tr>',
            re.DOTALL | re.IGNORECASE,
        )
        block_m = unit_block_regex.search(normalized)
        block_content = block_m.group(0) if block_m else ""

        if not block_content:
            wide_regex = re.compile(
                rf'(?:<tr|<div)[^>]*?(?:id=["\'](?:unit_smith_|unit_){canonic_key}["\']|data-unit=["\']{canonic_key}["\']).*?(?=<(?:tr|div)[^>]*?(?:id=["\'](?:unit_smith_|unit_)|data-unit=)|</table>|</div>\s*</div>|$)',
                re.DOTALL | re.IGNORECASE,
            )
            wide_m = wide_regex.search(normalized)
            if wide_m:
                block_content = wide_m.group(0)

        # Procura link de pesquisa explícito: action=research&id=canonic_key
        research_link_m = re.search(
            rf'<a[^>]*href=["\']([^"\']*[?&]action=research[^"\']*[?&]id={canonic_key}[^"\']*)["\'][^>]*>(.*?)</a>|'
            rf'<a[^>]*href=["\']([^"\']*[?&]id={canonic_key}[^"\']*[?&]action=research[^"\']*)["\'][^>]*>(.*?)</a>',
            normalized,
            re.IGNORECASE,
        )

        research_url = None
        if research_link_m:
            research_url = research_link_m.group(1) or research_link_m.group(3)

        # Determina status da unidade
        status = "unavailable"
        level = 0

        # Verifica se já está pesquisado
        is_researched = False
        if block_content:
            if re.search(r'pesquisado|nível\s+1|level\s+1|icon header checked', block_content, re.IGNORECASE):
                if "não pesquisado" not in block_content.lower() and "requisitos não" not in block_content.lower():
                    is_researched = True
            elif not research_url and "requisito" not in block_content.lower() and "inactive" not in block_content.lower():
                is_researched = True

        if research_url:
            status = "can_research"
            level = 0
        elif is_researched:
            status = "researched"
            level = 1
        elif "em pesquisa" in block_content.lower() or "a pesquisar" in block_content.lower():
            status = "researching"
            level = 0

        # Extração de custos se disponível no bloco
        wood, stone, iron = 0, 0, 0
        if block_content:
            w_m = re.search(r'(?:icon header wood|cost_wood|wood)[^>]*>.*?([\d\.]+)', block_content, re.IGNORECASE)
            s_m = re.search(r'(?:icon header stone|cost_stone|stone)[^>]*>.*?([\d\.]+)', block_content, re.IGNORECASE)
            i_m = re.search(r'(?:icon header iron|cost_iron|iron)[^>]*>.*?([\d\.]+)', block_content, re.IGNORECASE)

            def to_int(m):
                if not m:
                    return 0
                val = m.group(1).replace(".", "").strip()
                return int(val) if val.isdigit() else 0

            wood = to_int(w_m)
            stone = to_int(s_m)
            iron = to_int(i_m)

        result["units"][canonic_key] = {
            "unit": canonic_key,
            "level": level,
            "status": status,
            "wood": wood,
            "stone": stone,
            "iron": iron,
            "research_url": research_url,
        }

    return result


class SmithManager:
    """
    Controlador de automação para o Ferreiro (screen=smith).
    Verifica tecnologias militares e pesquisa automaticamente tropas necessárias.
    """

    async def get_smith_state(
        self, account: TribalAccount, village_id: Optional[int] = None
    ) -> SmithState:
        """
        Consulta o ecrã 'screen=smith' e extrai o estado detalhado de pesquisas.
        """
        v_id = village_id or account.current_village_id or 0
        html = await account.get_screen("smith", village_id=v_id)
        raw_data = parse_smith_page(html)

        units: Dict[str, SmithUnitInfo] = {}
        for u_key, u_info in raw_data.get("units", {}).items():
            units[u_key] = SmithUnitInfo(
                unit=u_key,
                level=int(u_info.get("level", 0)),
                status=str(u_info.get("status", "unavailable")),
                wood=int(u_info.get("wood", 0)),
                stone=int(u_info.get("stone", 0)),
                iron=int(u_info.get("iron", 0)),
                research_url=u_info.get("research_url"),
            )

        queue: List[ResearchOrder] = [
            ResearchOrder(
                unit=q["unit"],
                timer_str=q.get("timer_str", ""),
                timer_seconds=q.get("timer_seconds"),
                cancel_url=q.get("cancel_url"),
            )
            for q in raw_data.get("queue", [])
        ]

        smith_lvl = 0
        if v_id in account.villages and account.villages[v_id].buildings:
            smith_lvl = account.villages[v_id].buildings.get("smith", 0)

        state = SmithState(
            village_id=v_id,
            smith_level=smith_lvl,
            units=units,
            queue=queue,
        )

        logger.info(
            f"[{account.world}] Ferreiro carregado (Aldeia {v_id}): {len(queue)} pesquisas ativas na fila."
        )
        return state

    async def research_unit(
        self,
        account: TribalAccount,
        unit: str,
        village_id: Optional[int] = None,
    ) -> bool:
        """
        Submete uma ordem de pesquisa para a unidade pretendida no Ferreiro.
        """
        v_id = village_id or account.current_village_id or 0
        canonic_unit = SMITH_UNIT_ALIASES.get(unit.lower(), unit.lower())

        logger.info(f"[{account.world}] 🔬 A iniciar pesquisa de '{canonic_unit.capitalize()}' no Ferreiro...")

        try:
            extra_params = {
                "action": "research",
                "id": canonic_unit,
                "h": account.csrf_token or "",
            }

            await account.get_screen(
                screen="smith",
                village_id=v_id,
                extra_params=extra_params,
                apply_jitter=True,
            )
            logger.info(f"[{account.world}] ✅ Pesquisa de '{canonic_unit.capitalize()}' iniciada com sucesso!")
            return True
        except Exception as e:
            logger.error(f"[{account.world}] Falha ao pesquisar '{canonic_unit}': {e}")
            return False

    async def auto_research_needed_units(
        self,
        account: TribalAccount,
        village_id: Optional[int] = None,
        needed_units: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Verifica se há unidades necessárias não pesquisadas e inicia a sua pesquisa
        caso o Ferreiro e os edifícios pré-requisitos já estejam no nível requerido.
        """
        v_id = village_id or account.current_village_id or 0
        researched_list: List[str] = []

        # Se os edifícios da aldeia são conhecidos e o Ferreiro ainda não existe (nível 0)
        curr_blds = {}
        if v_id in account.villages and account.villages[v_id].buildings:
            curr_blds = account.villages[v_id].buildings

        if curr_blds and curr_blds.get("smith", 0) < 1:
            logger.debug(f"[{account.world}] Ferreiro não construído na aldeia {v_id}. Pesquisa suspensa.")
            return researched_list

        try:
            state = await self.get_smith_state(account, village_id=v_id)
        except Exception as e:
            logger.warning(f"Não foi possível ler o Ferreiro para auto-pesquisa: {e}")
            return researched_list

        # Se já há pesquisas na fila (normalmente o Ferreiro só permite 1 pesquisa simultânea)
        if state.is_researching_any:
            logger.debug(f"[{account.world}] Ferreiro ocupado com pesquisa em andamento ({state.queue[0].unit}).")
            return researched_list

        # Unidades a verificar
        check_list = needed_units or ["spear", "sword", "axe", "spy", "light", "ram"]

        for u in check_list:
            u_info = state.units.get(u)
            if not u_info:
                continue

            if u_info.can_research:
                # Dispara a pesquisa
                success = await self.research_unit(account, u, village_id=v_id)
                if success:
                    researched_list.append(u)
                    # Ferreiro ocupado, aguarda conclusão antes de pesquisar o próximo
                    break

        return researched_list
