"""
Tribal Wars Mobile Automation Engine - SmithManager (screen=smith)
Gestão do Ferreiro e Pesquisa Tecnológica Automática de Unidades Militares.
Inicia automaticamente a pesquisa de tropas necessárias para o modelo da aldeia
assim que os pré-requisitos de edifícios e recursos forem alcançados.
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Dict, List, Optional

from engine.core.account import TribalAccount
from engine.utils.parsers import ALL_UNITS, parse_timer_to_seconds

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
    for tr_match in re.finditer(r'<tr[^>]*>(?:(?!</tr>).)*?</tr>|<div[^>]*class=["\'][^"\']*queueItem[^"\']*["\'][^>]*>.*?</div>', normalized, re.DOTALL | re.IGNORECASE):
        row_content = tr_match.group(0)
        if "action=cancel" not in row_content and "action=cancel_research" not in row_content:
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

        # Procura a linha ou bloco da unidade por ID, data-unit, imagem ou aliases em texto
        block_content = ""
        unit_block_regex = re.compile(
            rf'<tr[^>]*?(?:id=["\'](?:unit_smith_|unit_){canonic_key}["\']|data-unit=["\']{canonic_key}["\']|class=["\'][^"\']*\bunit_smith_{canonic_key}\b[^"\']*["\'])[^>]*>(?:(?!</tr>).)*?</tr>',
            re.DOTALL | re.IGNORECASE,
        )
        block_m = unit_block_regex.search(normalized)
        if block_m:
            block_content = block_m.group(0)

        if not block_content:
            # Procura por linhas com a imagem correspondente da unidade (ex: unit_axe.png ou unit_axe)
            img_row_regex = re.compile(
                rf'<tr[^>]*>(?:(?!</tr>).)*?unit_{canonic_key}(?:\.png|\.webp|\.gif|["\'])(?:(?!</tr>).)*?</tr>',
                re.DOTALL | re.IGNORECASE,
            )
            img_m = img_row_regex.search(normalized)
            if img_m:
                block_content = img_m.group(0)

        if not block_content:
            # Procura por aliases conhecidos no texto da linha da tabela
            unit_aliases = [k for k, v in SMITH_UNIT_ALIASES.items() if v == canonic_key]
            for alias in unit_aliases:
                alias_row_regex = re.compile(
                    rf'<tr[^>]*>(?:(?!</tr>).)*?\b{re.escape(alias)}\b(?:(?!</tr>).)*?</tr>',
                    re.DOTALL | re.IGNORECASE,
                )
                alias_m = alias_row_regex.search(normalized)
                if alias_m:
                    block_content = alias_m.group(0)
                    break

        if not block_content:
            wide_regex = re.compile(
                rf'(?:<tr|<div)[^>]*?(?:id=["\'](?:unit_smith_|unit_){canonic_key}["\']|data-unit=["\']{canonic_key}["\']).*?(?=<(?:tr|div)[^>]*?(?:id=["\'](?:unit_smith_|unit_)|data-unit=)|</table>|</div>\s*</div>|$)',
                re.DOTALL | re.IGNORECASE,
            )
            wide_m = wide_regex.search(normalized)
            if wide_m:
                block_content = wide_m.group(0)

        # Procura link de pesquisa explícito: action=research&id=canonic_key ou ajaxaction=research
        research_link_m = re.search(
            rf'<a[^>]*href=["\']([^"\']*[?&](?:action|ajaxaction)=research[^"\']*[?&]id={canonic_key}[^"\']*)["\'][^>]*>(.*?)</a>|'
            rf'<a[^>]*href=["\']([^"\']*[?&]id={canonic_key}[^"\']*[?&](?:action|ajaxaction)=research[^"\']*)["\'][^>]*>(.*?)</a>',
            normalized,
            re.IGNORECASE,
        )

        research_url = None
        if research_link_m:
            research_url = research_link_m.group(1) or research_link_m.group(3)

        # Extração de custos se disponível no bloco ou página
        wood, stone, iron = 0, 0, 0
        def to_int(m):
            if not m:
                return 0
            val = m.group(1).replace(".", "").strip()
            return int(val) if val.isdigit() else 0

        target_text_for_cost = block_content or normalized
        if block_content:
            w_m = re.search(r'(?:icon header wood|cost_wood|wood)[^>]*>.*?([\d\.]+)', block_content, re.IGNORECASE)
            s_m = re.search(r'(?:icon header stone|cost_stone|stone)[^>]*>.*?([\d\.]+)', block_content, re.IGNORECASE)
            i_m = re.search(r'(?:icon header iron|cost_iron|iron)[^>]*>.*?([\d\.]+)', block_content, re.IGNORECASE)
            wood = to_int(w_m)
            stone = to_int(s_m)
            iron = to_int(i_m)

        # Determina status da unidade
        status = "unavailable"
        level = 0

        has_costs = (wood > 0 or stone > 0 or iron > 0)
        lower_block = block_content.lower()

        is_explicit_researched = False
        if block_content:
            has_researched_marker = bool(
                re.search(r'\b(?:pesquisado|pesquisada|desenvolvido|desenvolvida|conclu[ií]d[oa])\b', lower_block)
                or re.search(r'\b(?:n[ií]vel|level)\s*[:\s]*[1-9]\b', lower_block)
                or re.search(r'\b1\s*/\s*1\b|\b10\s*/\s*10\b', lower_block)
                or re.search(r'icon\s+header\s+checked|unit_researched|\bresearched\b', lower_block)
            )
            has_unmet_marker = bool(
                "não pesquisado" in lower_block
                or "não pesquisada" in lower_block
                or "requisitos não" in lower_block
                or "não atingidos" in lower_block
                or "não cumpridos" in lower_block
            )
            has_research_action = bool(
                research_url
                or "action=research" in lower_block
                or "ajaxaction=research" in lower_block
                or "name=\"research\"" in lower_block
                or re.search(r'<button[^>]*class=["\'][^"\']*(?:btn[-_]build|btn[-_]research)[^"\']*["\']', lower_block)
            )

            if has_researched_marker and not has_unmet_marker and not has_research_action:
                is_explicit_researched = True

        if is_explicit_researched:
            status = "researched"
            level = 1
            wood, stone, iron = 0, 0, 0
        elif research_url or (block_content and has_research_action):
            status = "can_research"
            level = 0
        elif "em pesquisa" in lower_block or "a pesquisar" in lower_block or re.search(r'<span[^>]*class=["\']timer["\']', lower_block):
            status = "researching"
            level = 0
        elif "requisito" in lower_block or "requisitos não" in lower_block or "não atingidos" in lower_block or "não cumpridos" in lower_block:
            status = "unavailable"
            level = 0
        elif has_costs and ("recursos insuficientes" in lower_block or re.search(r'\bpesquisar\b', lower_block)):
            status = "can_research"
            level = 0
        elif not block_content:
            status = "unavailable"
            level = 0
        else:
            # Se a linha existe e não há botão de pesquisa nem requisitos pendentes, a tecnologia já está pesquisada
            status = "researched"
            level = 1
            wood, stone, iron = 0, 0, 0

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


# Tabela de pré-requisitos mínimos de edifícios para pesquisa no Ferreiro
UNIT_RESEARCH_BUILDING_REQUIREMENTS: Dict[str, Dict[str, int]] = {
    "spear": {"barracks": 1},
    "sword": {"barracks": 1, "smith": 1},
    "axe": {"barracks": 2, "smith": 2},
    "archer": {"barracks": 5, "smith": 5},
    "spy": {"stable": 1},
    "light": {"stable": 3, "smith": 5},
    "marcher": {"stable": 5, "smith": 5},
    "heavy": {"stable": 10, "smith": 15},
    "ram": {"garage": 1, "smith": 10},
    "catapult": {"garage": 2, "smith": 12},
}


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
        Emite INFO log imediato quando a pesquisa é colocada na fila.
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

            resp_html = await account.get_screen(
                screen="smith",
                village_id=v_id,
                extra_params=extra_params,
                apply_jitter=True,
            )

            # Inspeciona se houve erro reportado pelo jogo
            if isinstance(resp_html, str):
                error_m = re.search(
                    r'<div[^>]*class=["\'][^"\']*(?:error_box|info_box\s+error|error_message)[^"\']*["\'][^>]*>(.*?)</div>|<span[^>]*class=["\']error["\'][^>]*>(.*?)</span>',
                    resp_html,
                    re.DOTALL | re.IGNORECASE,
                )
                if error_m:
                    raw_err = error_m.group(1) or error_m.group(2) or ""
                    clean_err = re.sub(r'<[^>]+>', ' ', raw_err).strip()
                    if clean_err:
                        logger.warning(f"[{account.world}] ⚠️ Aviso do jogo ao pesquisar '{canonic_unit}': {clean_err}")
                        return False

            unit_label = "Vikings (Machados/Axe)" if canonic_unit == "axe" else ("Cavalaria Leve (CL/Light)" if canonic_unit == "light" else canonic_unit.capitalize())
            logger.info(f"[{account.world}] ⚡ [PESQUISA INICIADA] Pesquisa de {unit_label} iniciada com sucesso no Ferreiro da aldeia {v_id}!")
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
        Prioriza com prioridade máxima Vikings ('axe') e Cavalaria Leve ('light').
        """
        v_id = village_id or account.current_village_id or 0
        researched_list: List[str] = []

        curr_blds = {}
        if v_id in account.villages and account.villages[v_id].buildings:
            curr_blds = account.villages[v_id].buildings

        if curr_blds and curr_blds.get("smith", 0) < 1:
            logger.debug(f"[{account.world}] Ferreiro não construído na aldeia {v_id} (nível 0). Pesquisa suspensa.")
            return researched_list

        try:
            state = await self.get_smith_state(account, village_id=v_id)
        except Exception as e:
            logger.warning(f"Não foi possível ler o Ferreiro para auto-pesquisa: {e}")
            return researched_list

        # Se já há pesquisas na fila (o Ferreiro só permite 1 pesquisa simultânea)
        if state.is_researching_any:
            active_unit = state.queue[0].unit
            timer_info = f" ({state.queue[0].timer_str})" if state.queue[0].timer_str else ""
            logger.debug(f"[{account.world}] Ferreiro ocupado com pesquisa em andamento: {active_unit}{timer_info}.")
            return researched_list

        # Unidades a verificar ordenadas por prioridade máxima (Vikings e CL primeiro)
        priority_needed = []
        needed_clean = [SMITH_UNIT_ALIASES.get(str(x).lower().strip(), str(x).lower().strip()) for x in (needed_units or [])]
        for top_u in ("axe", "light"):
            if top_u in needed_clean:
                priority_needed.append(top_u)

        remaining = [u for u in (needed_clean or ["spear", "sword", "axe", "spy", "light", "ram"]) if u not in priority_needed]
        check_list = priority_needed + remaining

        # Obtém recursos atuais da aldeia
        village_res = None
        if v_id in account.villages and account.villages[v_id].resources:
            village_res = account.villages[v_id].resources

        for u in check_list:
            # Se a aldeia já possui tropas desta unidade treinadas, a pesquisa já foi concluída
            if v_id in account.villages:
                v_troops = getattr(account.villages[v_id], "troops", None)
                unit_qty = 0
                if isinstance(v_troops, dict):
                    val = v_troops.get(u, 0)
                    if isinstance(val, (int, float)):
                        unit_qty = val
                elif hasattr(v_troops, u):
                    val = getattr(v_troops, u, 0)
                    if isinstance(val, (int, float)):
                        unit_qty = val
                if isinstance(unit_qty, (int, float)) and unit_qty > 0:
                    continue

            u_info = state.units.get(u)
            if not u_info:
                continue

            if u_info.is_researched or u_info.is_researching:
                continue

            # Valida pré-requisitos de edifícios se conhecidos
            reqs = UNIT_RESEARCH_BUILDING_REQUIREMENTS.get(u, {})
            if curr_blds and reqs:
                unmet = [
                    f"{b_req} nv{lvl_req} (atual: {curr_blds.get(b_req, 0)})"
                    for b_req, lvl_req in reqs.items()
                    if curr_blds.get(b_req, 0) < lvl_req
                ]
                if unmet:
                    if u == "axe":
                        logger.info(
                            f"[{account.world}] ⏳ [RUSH VIKINGS] Pesquisa de Vikings ('axe') aguarda edifícios na aldeia {v_id}: "
                            f"{', '.join(unmet)}."
                        )
                    elif u == "light":
                        logger.info(
                            f"[{account.world}] ⏳ [RUSH CL] Pesquisa de Cavalaria Leve ('light') aguarda edifícios na aldeia {v_id}: "
                            f"{', '.join(unmet)}."
                        )
                    continue

            # Custos canónicos de pesquisa se a página não reportar
            default_research_costs = {
                "axe": {"wood": 700, "stone": 840, "iron": 820},
                "spy": {"wood": 560, "stone": 480, "iron": 480},
                "light": {"wood": 2200, "stone": 2400, "iron": 2000},
                "heavy": {"wood": 4000, "stone": 4200, "iron": 3800},
                "ram": {"wood": 1400, "stone": 1600, "iron": 1200},
                "catapult": {"wood": 1600, "stone": 2000, "iron": 1200},
            }
            req_wood = u_info.wood or default_research_costs.get(u, {}).get("wood", 0)
            req_stone = u_info.stone or default_research_costs.get(u, {}).get("stone", 0)
            req_iron = u_info.iron or default_research_costs.get(u, {}).get("iron", 0)

            # Verifica se os recursos da aldeia cobrem o custo de pesquisa
            has_resources = True
            if village_res and req_wood > 0 and isinstance(getattr(village_res, "wood", None), (int, float)):
                v_wood = getattr(village_res, "wood", 0)
                v_stone = getattr(village_res, "stone", 0)
                v_iron = getattr(village_res, "iron", 0)
                if isinstance(v_stone, (int, float)) and isinstance(v_iron, (int, float)):
                    if v_wood < req_wood or v_stone < req_stone or v_iron < req_iron:
                        has_resources = False
                        missing = []
                        if v_wood < req_wood:
                            missing.append(f"{req_wood - v_wood} Madeira")
                        if v_stone < req_stone:
                            missing.append(f"{req_stone - v_stone} Argila")
                        if v_iron < req_iron:
                            missing.append(f"{req_iron - v_iron} Ferro")
                        logger.info(
                            f"[{account.world}] ⏳ Pesquisa de '{u.capitalize()}' aguarda recursos "
                            f"(Em falta: {', '.join(missing)} | Necessário: {req_wood}M, {req_stone}A, {req_iron}F | Aldeia: {v_wood}M, {v_stone}A, {v_iron}F)."
                        )

            if u_info.can_research or (has_resources and u_info.status != "unavailable"):
                if u == "axe":
                    logger.info(f"[{account.world}] ⚡ [RUSH VIKINGS] Pré-requisitos cumpridos! A disparar pesquisa de Vikings ('axe') no Ferreiro...")
                elif u == "light":
                    logger.info(f"[{account.world}] ⚡ [RUSH CL] Pré-requisitos cumpridos! A disparar pesquisa de Cavalaria Leve ('light') no Ferreiro...")
                else:
                    logger.info(f"[{account.world}] 🔬 Pré-requisitos cumpridos! A disparar pesquisa de '{u.capitalize()}' no Ferreiro...")

                success = await self.research_unit(account, u, village_id=v_id)
                if success:
                    researched_list.append(u)
                    # Ferreiro ocupado, aguarda conclusão antes de pesquisar o próximo
                    break

        return researched_list
