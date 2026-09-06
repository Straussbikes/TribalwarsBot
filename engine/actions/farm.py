"""
Tribal Wars Mobile Automation Engine - FarmManager (screen=am_farm & screen=place)
Automação de Micro-Farming: envio de saques em massa com o Assistente de Farm (Modelos A/B)
e fallback direto via Praça de Reunião com filtros de segurança e temporização humana.
"""

import asyncio
from dataclasses import dataclass, field
import logging
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from engine.actions.map import MapManager, calculate_distance
from engine.actions.place import PlaceManager, UnitsCount
from engine.config.settings import FarmConfig
from engine.core.account import TribalAccount
from engine.core.models import TaskPriority
from engine.core.scheduler import TaskScheduler
from engine.utils.parsers import (
    parse_am_farm_targets,
    parse_am_farm_templates,
)
from engine.utils.timing import get_human_delay

logger = logging.getLogger(__name__)


@dataclass
class FarmTarget:
    """Dados de uma aldeia bárbara elegível para farm."""
    target_id: str
    target_name: str
    target_coords: str
    x: int = 0
    y: int = 0
    distance: float = 0.0
    report_color: str = "none"  # 'green', 'yellow', 'red', 'blue', 'none'
    loot_status: str = "unknown"  # 'full', 'partial', 'empty', 'unknown'
    wall_level: int = 0
    has_attack_in_transit: bool = False
    is_in_am_farm: bool = True
    template_a_id: Optional[str] = None
    template_b_id: Optional[str] = None
    template_a_available: bool = False
    template_b_available: bool = False
    action_url_a: Optional[str] = None
    action_url_b: Optional[str] = None

    def __post_init__(self):
        if (not self.x or not self.y) and self.target_coords and "|" in self.target_coords:
            try:
                parts = self.target_coords.strip("() ").split("|")
                self.x = int(parts[0])
                self.y = int(parts[1])
            except (ValueError, IndexError) as err:
                logger.debug(f"Falha ao decompor coordenadas de farm '{self.target_coords}': {err}")


@dataclass
class FarmAssistantState:
    """Estado consolidado do Assistente de Farm (screen=am_farm)."""
    village_id: int
    targets: List[FarmTarget] = field(default_factory=list)
    template_a_troops: Dict[str, int] = field(default_factory=dict)
    template_b_troops: Dict[str, int] = field(default_factory=dict)
    haul_capacities: Dict[str, int] = field(default_factory=dict)

    @property
    def total_targets_count(self) -> int:
        return len(self.targets)


@dataclass
class RadarFarmPlan:
    """Plano dinâmico de alocação de micro-esquadrões para aldeias bárbaras mapeadas."""
    village_id: int
    total_barbarians_found: int
    eligible_targets: List[Tuple[int, int]] = field(default_factory=list)
    squads_assigned: List[Tuple[Tuple[int, int], UnitsCount]] = field(default_factory=list)
    total_carrying_capacity: int = 0


def allocate_dynamic_squads(
    available_units: UnitsCount,
    squad_template: UnitsCount,
    targets: List[Tuple[int, int]],
    max_squads: Optional[int] = None,
) -> List[Tuple[Tuple[int, int], UnitsCount]]:
    """
    Divide de forma balanceada as tropas disponíveis na aldeia em micro-esquadrões de saque
    de acordo com o modelo de esquadrão fornecido (ex.: 5 lanceiros + 1 explorador ou 2 cavalarias leves).
    Distribui os esquadrões pelos alvos especificados (ordenados por proximidade).
    """
    if not targets:
        return []

    # Determinar unidades mínimas por esquadrão requeridas
    template_dict = {u: cnt for u, cnt in squad_template.to_dict().items() if cnt > 0}
    if not template_dict:
        return []

    avail_dict = available_units.to_dict()

    # Quantos esquadrões completos conseguimos formar com as tropas atualmente disponíveis?
    max_possible_squads = min(
        avail_dict.get(u, 0) // req_cnt
        for u, req_cnt in template_dict.items()
    )

    if max_possible_squads <= 0:
        return []

    num_squads = min(max_possible_squads, len(targets))
    if max_squads is not None and max_squads > 0:
        num_squads = min(num_squads, max_squads)

    allocations: List[Tuple[Tuple[int, int], UnitsCount]] = []
    for i in range(num_squads):
        target = targets[i]
        allocations.append((target, squad_template))

    return allocations


def get_gaussian_delay(min_ms: int = 500, max_ms: int = 1100) -> float:
    """
    Gera um atraso estocástico gaussiano (em segundos) centrado na média do intervalo
    com dispersão normal delimitada estritamente entre min_ms e max_ms para evasão anti-bot e anti-timeout.
    """
    min_s = max(0.05, min_ms / 1000.0)
    max_s = max(min_s, max_ms / 1000.0)
    mean = (min_s + max_s) / 2.0
    stdev = max(0.01, (max_s - min_s) / 6.0)  # ~99.7% das amostras dentro de [min, max]
    sample = random.gauss(mean, stdev)
    return max(min_s, min(max_s, sample))


def select_optimal_farm_template(
    target: FarmTarget,
    preferred_template: str = "A",
    haul_capacities: Optional[Dict[str, int]] = None,
    distance_threshold_for_upgrade: float = 5.0,
    allow_fallback: bool = True,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Algoritmo de Seleção Inteligente de Modelo de Saque (A vs B):
    1. Se o último saque foi 100% cheio ('full'), e o Modelo B possui maior capacidade de carga,
       promove para o Modelo B para maximizar recursos saqueados por viagem.
    2. Se o último saque foi parcial/vazio ('partial'/'empty'), prefere o modelo com menor alocação (normalmente A).
    3. Para aldeias a maior distância com histórico positivo, favorece o modelo de maior capacidade/velocidade.
    4. Auto-fallback resiliente: se o modelo ideal estiver indisponível (botão disabled ou sem tropas),
       recorre opcionalmente ao modelo alternativo se este estiver disponível.
    Retorna (template_letter, template_id) ou (None, None) se nenhum modelo estiver disponível.
    """
    pref = preferred_template.upper().strip()
    haul = haul_capacities or {"a": 0, "b": 0}
    cap_a = haul.get("a", 0)
    cap_b = haul.get("b", 0)

    chosen = pref

    # Heurística 1: Saque cheio anterior -> Promove para o modelo de maior capacidade
    if target.loot_status == "full":
        if cap_b > cap_a and target.template_b_available and target.template_b_id:
            chosen = "B"
        elif cap_a >= cap_b and target.template_a_available and target.template_a_id:
            chosen = "A"

    # Heurística 2: Saque parcial/vazio anterior -> Prefere modelo mais económico
    elif target.loot_status in ("partial", "empty"):
        if cap_a < cap_b and cap_a > 0 and target.template_a_available and target.template_a_id:
            chosen = "A"

    # Heurística 3: Distância elevada com histórico positivo
    elif target.distance > distance_threshold_for_upgrade and target.report_color in ("green", "blue"):
        if cap_b > cap_a and target.template_b_available and target.template_b_id:
            chosen = "B"

    # Validação de disponibilidade do modelo escolhido
    t_id = target.template_a_id if chosen == "A" else target.template_b_id
    t_avail = target.template_a_available if chosen == "A" else target.template_b_available

    if t_avail and t_id:
        return chosen, t_id

    # Fallback automático para o modelo alternativo se permitido
    if allow_fallback:
        alt_letter = "B" if chosen == "A" else "A"
        alt_id = target.template_b_id if chosen == "A" else target.template_a_id
        alt_avail = target.template_b_available if chosen == "A" else target.template_a_available
        if alt_avail and alt_id:
            return alt_letter, alt_id

    return None, None


class FarmManager:
    """
    Controlador de automação de Micro-Farming.
    Fornece rotinas de saque em massa via Assistente de Farm ou Praça de Reunião.
    """

    def __init__(
        self,
        place_manager: Optional[PlaceManager] = None,
        map_manager: Optional[Any] = None,
        broadcast_callback: Optional[Any] = None,
        config: Optional[Any] = None,
    ):
        self.place_manager = place_manager or PlaceManager()
        self.map_manager = map_manager
        self.broadcast_callback = broadcast_callback
        self.config = config
        self._recent_farm_targets: Set[str] = set()
        self._target_last_farmed: Dict[str, float] = {}

    async def get_am_farm_state(
        self,
        account: TribalAccount,
        village_id: Optional[int] = None,
        config: Optional[Any] = None,
    ) -> FarmAssistantState:
        """
        Carrega o ecrã 'screen=am_farm' e extrai a lista de aldeias bárbaras e modelos A/B.
        """
        html = await account.get_screen("am_farm", village_id=village_id)
        v_id = village_id or account.current_village_id or 0

        raw_targets = parse_am_farm_targets(html)
        raw_templates = parse_am_farm_templates(html)

        targets: List[FarmTarget] = [
            FarmTarget(
                target_id=str(t["target_id"]),
                target_name=str(t["target_name"]),
                target_coords=str(t["target_coords"]),
                distance=float(t["distance"]),
                report_color=str(t["report_color"]),
                loot_status=str(t.get("loot_status", "unknown")),
                wall_level=int(t["wall_level"]),
                has_attack_in_transit=bool(t.get("has_attack_in_transit", False)),
                template_a_id=t["template_a_id"],
                template_b_id=t["template_b_id"],
                template_a_available=bool(t["template_a_available"]),
                template_b_available=bool(t["template_b_available"]),
                action_url_a=t.get("action_url_a"),
                action_url_b=t.get("action_url_b"),
            )
            for t in raw_targets
        ]

        logger.info(
            f"[{account.world}] Assistente de Farm carregado: {len(targets)} alvos detetados na aldeia {v_id}."
        )
        tmpl_a = raw_templates.get("a", {}).copy()
        tmpl_b = raw_templates.get("b", {}).copy()
        haul_caps = raw_templates.get("haul_capacity", {"a": 0, "b": 0}).copy()

        # Fallback para modelos configurados na app caso a resposta HTML do jogo não forneça valores
        cfg_farm = getattr(config, "farm", None) or getattr(getattr(self, "config", None), "farm", None)
        if not cfg_farm and hasattr(config, "template_a_troops"):
            cfg_farm = config
        if cfg_farm:
            from engine.utils.parsers import UNIT_HAUL_CAPACITY
            if sum(tmpl_a.values()) == 0 and getattr(cfg_farm, "template_a_troops", None) and sum(cfg_farm.template_a_troops.values()) > 0:
                tmpl_a = cfg_farm.template_a_troops.copy()
                haul_caps["a"] = sum(qty * UNIT_HAUL_CAPACITY.get(u, 0) for u, qty in tmpl_a.items())
            if sum(tmpl_b.values()) == 0 and getattr(cfg_farm, "template_b_troops", None) and sum(cfg_farm.template_b_troops.values()) > 0:
                tmpl_b = cfg_farm.template_b_troops.copy()
                haul_caps["b"] = sum(qty * UNIT_HAUL_CAPACITY.get(u, 0) for u, qty in tmpl_b.items())

        return FarmAssistantState(
            village_id=v_id,
            targets=targets,
            template_a_troops=tmpl_a,
            template_b_troops=tmpl_b,
            haul_capacities=haul_caps,
        )

    async def save_am_farm_template(
        self,
        account: TribalAccount,
        template: str,
        units: Dict[str, int],
        village_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Atualiza e persiste a configuração do Modelo A ou Modelo B diretamente nos servidores do jogo.
        Emprega o formulário nativo edit_all com suporte de fallback a change_template.
        """
        tmpl = template.lower().strip()
        if tmpl not in ("a", "b"):
            raise ValueError("O template deve ser 'a' ou 'b'.")

        v_id = village_id or account.current_village_id or 0
        from engine.utils.parsers import ALL_UNITS, parse_am_farm_templates

        # 1. Carrega o estado atual da página do farm assistant para preservar o outro template e IDs
        try:
            current_html = await account.get_screen("am_farm", village_id=v_id, apply_jitter=False)
            parsed_current = parse_am_farm_templates(current_html)
        except Exception as e_get:
            logger.debug(f"Não foi possível obter tela atual do am_farm antes de salvar template: {e_get}")
            parsed_current = {"template_ids": {}, "template_news": {}, "a": {}, "b": {}}

        # 2. Constrói o payload para action=edit_all
        data: Dict[str, str] = {}
        for tmpl_key in ("a", "b"):
            t_id = parsed_current.get("template_ids", {}).get(tmpl_key)
            t_new = parsed_current.get("template_news", {}).get(tmpl_key, "0")
            if not t_id:
                t_id = "1" if tmpl_key == "b" else "0"

            data[f"template[{t_id}][id]"] = str(t_id)
            data[f"template[{t_id}][new]"] = str(t_new)

            u_dict = units if tmpl_key == tmpl else parsed_current.get(tmpl_key, {})
            for u in ALL_UNITS:
                qty = max(0, int(u_dict.get(u, 0)))
                data[f"{u}[{t_id}]"] = str(qty)
                # Formato legado para máxima compatibilidade
                data[f"{tmpl_key}[{u}]"] = str(qty)

        if account.csrf_token:
            data["h"] = account.csrf_token

        # 3. Submissão prioritária via edit_all
        try:
            html = await account.post_action(
                screen="am_farm",
                action="edit_all",
                data=data,
                village_id=v_id,
                apply_jitter=True,
            )
        except Exception as e_post:
            logger.warning(f"[{account.world}] post_action edit_all falhou: {e_post}. A tentar change_template...")
            html = await account.post_action(
                screen="am_farm",
                action="change_template",
                data=data,
                village_id=v_id,
                apply_jitter=True,
            )

        parsed_templates = parse_am_farm_templates(html)
        updated_template = parsed_templates.get(tmpl, {})
        capacity = parsed_templates.get("haul_capacity", {}).get(tmpl, 0)

        # Se por algum motivo o parsing retornou vazio mas a submissão foi aceite, usa os valores enviados
        if sum(updated_template.values()) == 0 and sum(units.values()) > 0:
            updated_template = {u: max(0, int(units.get(u, 0))) for u in ALL_UNITS}
            from engine.utils.parsers import UNIT_HAUL_CAPACITY
            capacity = sum(qty * UNIT_HAUL_CAPACITY.get(u, 0) for u, qty in updated_template.items())
            parsed_templates[tmpl] = updated_template
            parsed_templates["haul_capacity"][tmpl] = capacity

        # Persiste localmente no FarmConfig do bot para imunidade a templates não retornados pela página
        cfg_farm = getattr(getattr(self, "config", None), "farm", None)
        if cfg_farm:
            if tmpl == "a":
                cfg_farm.template_a_troops = updated_template.copy()
            else:
                cfg_farm.template_b_troops = updated_template.copy()

        logger.info(
            f"[{account.world}] Modelo {tmpl.upper()} de Saque atualizado no jogo com sucesso: {updated_template} (Capacidade: {capacity})."
        )
        return {
            "status": "success",
            "template": tmpl.upper(),
            "units": updated_template,
            "haul_capacity": capacity,
            "templates": parsed_templates,
        }

    async def send_am_farm_attack(
        self,
        account: TribalAccount,
        target_id: str,
        template_id: str,
        village_id: Optional[int] = None,
    ) -> bool:
        """
        Envia um comando de farm rápido via Assistente de Farm.
        Prioriza o POST nativo ajaxaction=farm do Tribal Wars e efetua fallback para GET.
        """
        v_id = village_id or account.current_village_id or 0
        try:
            # 1. Envio nativo oficial via POST ajaxaction=farm quando suportado
            if hasattr(account, "post_action"):
                try:
                    post_payload = {
                        "target": str(target_id),
                        "template_id": str(template_id),
                        "source": str(v_id),
                        "h": account.csrf_token or "",
                    }
                    resp = await account.post_action(
                        screen="am_farm",
                        action=None,
                        data=post_payload,
                        extra_params={"mode": "farm", "ajaxaction": "farm", "json": "1"},
                        village_id=v_id,
                        apply_jitter=True,
                    )
                    if resp and ('"success"' in resp or '"current_units"' in resp or 'Vikings' in resp or 'Cavalaria' in resp):
                        return True
                except Exception as e_post:
                    logger.debug(f"post_action ajaxaction=farm falhou ({e_post}), a tentar GET...")

            # 2. Fallback via GET action=farm
            extra_params = {
                "action": "farm",
                "target": str(target_id),
                "template_id": str(template_id),
                "h": account.csrf_token or "",
            }
            await account.get_screen(
                screen="am_farm",
                village_id=v_id,
                extra_params=extra_params,
                apply_jitter=True,
            )
            return True
        except Exception as e:
            logger.warning(f"[{account.world}] Falha ao enviar farm para alvo {target_id}: {e}")
            return False

    async def run_am_farm_wave(
        self,
        account: TribalAccount,
        template: str = "A",
        max_distance: float = 15.0,
        skip_losses: bool = True,
        skip_wall: bool = True,
        max_attacks: int = 30,
        village_id: Optional[int] = None,
        allow_fallback: bool = False,
        min_delay_ms: int = 500,
        max_delay_ms: int = 1100,
    ) -> int:
        """
        Executa uma onda de saques pelo Assistente de Farm:
        1. Inspeciona a lista de bárbaras.
        2. Aplica filtros de distância, cor de relatório e nível de muralha.
        3. Dispara os ataques em série com jitter humano entre cada clique.
        Retorna a quantidade de saques enviados com sucesso.
        """
        tmpl_key = template.upper().strip()
        state = await self.get_am_farm_state(account, village_id=village_id)
        if not state.targets:
            logger.info(f"[{account.world}] Nenhuma aldeia bárbara listada no Assistente de Farm.")
            return 0

        sent_count = 0
        logger.info(
            f"[{account.world}] A iniciar onda de Farm (Modelo {tmpl_key}) para até {max_attacks} alvos..."
        )

        cycle_sent: Set[str] = set()
        now_ts = time.time()
        farm_cfg = getattr(self.config, "farm", None)
        cooldown_secs = getattr(farm_cfg, "target_cooldown_minutes", 10.0) * 60.0
        avoid_concurrent = getattr(farm_cfg, "avoid_concurrent_attacks", True)

        for target in state.targets:
            if sent_count >= max_attacks:
                break

            coords = target.target_coords or f"{target.x}|{target.y}"
            if coords in cycle_sent:
                continue

            # 1. Filtro de distância máxima
            if target.distance > max_distance:
                continue

            # 2. Prevenção de colisões / validação de cooldown
            last_farmed = self._target_last_farmed.get(coords, 0.0)
            time_since = now_ts - last_farmed
            if last_farmed > 0 and time_since < cooldown_secs:
                continue

            if avoid_concurrent and (target.has_attack_in_transit or coords in self._recent_farm_targets):
                continue

            # 3. Filtro de segurança: ignorar aldeias com perdas
            if skip_losses and target.report_color in ("yellow", "red"):
                logger.debug(
                    f"Alvo {target.target_coords} ignorado (relatório {target.report_color})."
                )
                continue

            # 4. Filtro de segurança: ignorar aldeias com muralha detectada
            if skip_wall and target.wall_level > 0:
                logger.debug(
                    f"Alvo {target.target_coords} ignorado (muralha nível {target.wall_level})."
                )
                continue

            # 5. Seleção Inteligente de Modelo (A vs B)
            chosen_letter, t_id = select_optimal_farm_template(
                target=target,
                preferred_template=tmpl_key,
                haul_capacities=state.haul_capacities,
                allow_fallback=allow_fallback,
            )

            if not t_id:
                # Nenhum modelo com tropas disponíveis para este alvo
                continue

            # Envia o saque com micro-jitter
            success = await self.send_am_farm_attack(
                account=account,
                target_id=target.target_id,
                template_id=t_id,
                village_id=village_id,
            )
            if success:
                sent_count += 1
                if coords:
                    cycle_sent.add(coords)
                    self._recent_farm_targets.add(coords)
                    self._target_last_farmed[coords] = time.time()
                target.has_attack_in_transit = True

                logger.info(
                    f"[{account.world}] 🌾 [SAQUE DESPACHADO] Modelo {chosen_letter.upper()} enviado com sucesso para "
                    f"{target.target_name} ({target.target_coords}) [Dist: {target.distance:.1f}c | Muralha: {target.wall_level if target.wall_level is not None else '?'}]"
                )

                try:
                    tracker = getattr(account, "stats_tracker", None) or (account.get_stats_tracker() if hasattr(account, "get_stats_tracker") else None)
                    if tracker:
                        tracker.record_command(command_type="farm", target_coords=target.target_coords, success=True)
                        tracker.record_farm_loot(
                            wood=100, stone=100, iron=100,
                            village_id=village_id or account.current_village_id or 0,
                            target_x=target.x, target_y=target.y,
                            village_name=target.target_name,
                        )
                except Exception as e_st:
                    logger.debug(f"Aviso ao registar telemetria de farm: {e_st}")

                logger.info(
                    f"[{account.world}] Saque #{sent_count} (Modelo {chosen_letter}) enviado -> {target.target_name} "
                    f"({target.target_coords}) [Dist: {target.distance:.1f} campos]"
                )
                # Jitter humano gaussiano realista entre cliques sucessivos de farm (aliviado anti-timeout)
                await asyncio.sleep(get_gaussian_delay(min_delay_ms, max_delay_ms))

        logger.info(
            f"[{account.world}] Onda de Farm concluída: {sent_count} saques enviados."
        )
        return sent_count

    async def discover_all_radius_barbarians(
        self,
        account: TribalAccount,
        max_distance: float = 25.0,
        village_id: Optional[int] = None,
        custom_targets: Optional[List[Any]] = None,
        config: Optional[Any] = None,
    ) -> List[FarmTarget]:
        """
        Descobre e unifica TODAS as aldeias bárbaras/abandonadas num raio de X campos em redor da aldeia ativa.
        Combina:
        1. Alvos mapeados no Assistente de Saque (screen=am_farm).
        2. Aldeias bárbaras identificadas pelo mapa tático (screen=map / cache local).
        3. Coordenadas personalizadas configuradas pelo utilizador (custom_targets).
        Retorna a lista unificada e sem duplicados, ordenada por distância euclidiana ascendente.
        """
        v_id = village_id or account.current_village_id or 0
        v_data = account.villages.get(v_id) if account.villages else None
        origin_x = v_data.x if v_data else 500
        origin_y = v_data.y if v_data else 500

        # 1. Carrega o estado atual do Assistente de Saque
        am_state = await self.get_am_farm_state(account, village_id=v_id, config=config)
        targets_by_coords: Dict[str, FarmTarget] = {}
        for t in am_state.targets:
            t.is_in_am_farm = True
            if (not t.distance or t.distance == 0.0) and t.x and t.y:
                t.distance = calculate_distance(origin_x, origin_y, t.x, t.y)
            if t.target_coords:
                targets_by_coords[t.target_coords] = t

        # 2. Descobre bárbaras no mapa através do MapManager
        if not self.map_manager:
            self.map_manager = MapManager()

        try:
            map_data = await self.map_manager.get_tactical_map(
                account=account,
                center_x=origin_x,
                center_y=origin_y,
                radius=max_distance,
                use_cache=True,
            )
            for mv in map_data.villages:
                if mv.is_barbarian:
                    coords = mv.coordinates
                    dist = calculate_distance(origin_x, origin_y, mv.x, mv.y)
                    if dist <= max_distance:
                        if coords not in targets_by_coords:
                            targets_by_coords[coords] = FarmTarget(
                                target_id=str(mv.id),
                                target_name=mv.name or "Aldeia Bárbara",
                                target_coords=coords,
                                x=mv.x,
                                y=mv.y,
                                distance=dist,
                                report_color="none",
                                loot_status="unknown",
                                wall_level=mv.wall,
                                has_attack_in_transit=False,
                                is_in_am_farm=False,
                            )
        except Exception as e_map:
            logger.warning(f"[{account.world}] Aviso ao consultar mapa para varredura de bárbaras: {e_map}")

        # 3. Adiciona alvos personalizados
        if custom_targets:
            for ct in custom_targets:
                coord_str = ""
                cx, cy = 0, 0
                if isinstance(ct, (tuple, list)) and len(ct) == 2:
                    cx, cy = int(ct[0]), int(ct[1])
                    coord_str = f"{cx}|{cy}"
                elif isinstance(ct, str) and "|" in ct:
                    coord_str = ct.strip()
                    try:
                        parts = coord_str.split("|")
                        cx, cy = int(parts[0]), int(parts[1])
                    except ValueError:
                        continue

                if coord_str and coord_str not in targets_by_coords:
                    dist = calculate_distance(origin_x, origin_y, cx, cy)
                    if dist <= max_distance:
                        targets_by_coords[coord_str] = FarmTarget(
                            target_id="0",
                            target_name="Alvo Personalizado",
                            target_coords=coord_str,
                            x=cx,
                            y=cy,
                            distance=dist,
                            is_in_am_farm=False,
                        )

        # 4. Filtra estritamente pelo raio máximo de campos e ordena por distância ascendente
        all_targets = [
            t for t in targets_by_coords.values()
            if t.distance <= max_distance
        ]
        all_targets.sort(key=lambda item: item.distance)

        logger.info(
            f"[{account.world}] Varredura de Bárbaras em Raio ({max_distance} campos): "
            f"{len(all_targets)} alvos mapeados ({sum(1 for t in all_targets if t.is_in_am_farm)} no AM Farm, "
            f"{sum(1 for t in all_targets if not t.is_in_am_farm)} descobertos fora do AM Farm)."
        )
        return all_targets

    async def bootstrap_unlisted_barbarian(
        self,
        account: TribalAccount,
        target: FarmTarget,
        template_troops: Optional[UnitsCount] = None,
        village_id: Optional[int] = None,
    ) -> bool:
        """
        Dispara um primeiro ataque de reconhecimento/saque via Praça de Reunião
        para uma aldeia bárbara no raio que ainda não consta no Assistente de Saque.
        Após o impacto, o jogo indexa automaticamente a bárbara no Assistente de Saque.
        """
        if target.is_in_am_farm:
            return True

        if not target.x or not target.y:
            if target.target_coords and "|" in target.target_coords:
                parts = target.target_coords.split("|")
                try:
                    target.x, target.y = int(parts[0]), int(parts[1])
                except ValueError:
                    return False
            else:
                return False

        v_id = village_id or account.current_village_id or 0
        if template_troops is not None and template_troops.total > 0:
            squad = template_troops
        else:
            squad = None
            try:
                am_state = await self.get_am_farm_state(account, village_id=v_id)
                tmpl_dict = am_state.template_a_troops if am_state.template_a_troops and sum(am_state.template_a_troops.values()) > 0 else am_state.template_b_troops
                if tmpl_dict and sum(tmpl_dict.values()) > 0:
                    squad = UnitsCount.from_dict(tmpl_dict)
            except Exception as e:
                logger.debug(f"Aviso ao ler templates AM para bootstrap: {e}")

        if not squad or squad.total == 0:
            logger.warning(
                f"[{account.world}] Bootstrap cancelado: nenhum modelo de tropas configurado para {target.target_name} ({target.target_coords})."
            )
            return False

        logger.info(
            f"[{account.world}] 🚀 [BOOTSTRAP FARM] A enviar ataque inicial via Praça para bárbara "
            f"{target.target_name} ({target.target_coords}) [Modelo: {squad.to_summary_str()}]..."
        )
        success = await self.place_manager.send_command(
            account=account,
            target_coords=(target.x, target.y),
            units=squad,
            is_attack=True,
            village_id=village_id,
            allow_partial=False,
        )
        if success:
            target.has_attack_in_transit = True
            try:
                tracker = getattr(account, "stats_tracker", None) or (account.get_stats_tracker() if hasattr(account, "get_stats_tracker") else None)
                if tracker:
                    tracker.record_command(command_type="farm", target_coords=target.target_coords, success=True)
                    squad_cap = squad.carrying_capacity() if squad else 240
                    cap_per_res = max(30, squad_cap // 3)
                    tracker.record_farm_loot(
                        wood=cap_per_res, stone=cap_per_res, iron=cap_per_res,
                        village_id=village_id or account.current_village_id or 0,
                        target_x=target.x, target_y=target.y,
                        village_name=target.target_name,
                    )
            except Exception as e:
                logger.debug(f"Aviso ao registar métricas de farm no tracker: {e}")
        return success

    async def run_comprehensive_radius_farm_cycle(
        self,
        account: TribalAccount,
        config: Optional[FarmConfig] = None,
        village_id: Optional[int] = None,
        max_attacks: int = 50,
    ) -> Dict[str, Any]:
        """
        Executa um ciclo completo de varredura e ataque de todas as bárbaras no raio de X campos:
        1. Descobre 100% das bárbaras no raio configurado (AM Farm + Mapa + Custom).
        2. Ataca via Assistente de Saque as bárbaras já catalogadas.
        3. Dispara bootstrap via Praça para as novas bárbaras não catalogadas.
        4. Respeita prevenção de ataques sobrepostos, filtros de perdas e micro-jitters estocásticos.
        """
        if hasattr(config, "farm"):
            cfg = config.farm
        elif config is not None:
            cfg = config
        else:
            cfg = FarmConfig()
        v_id = village_id or account.current_village_id or 0

        # Obter todas as bárbaras no raio configurado
        all_targets = await self.discover_all_radius_barbarians(
            account=account,
            max_distance=cfg.max_distance,
            village_id=v_id,
            custom_targets=cfg.custom_targets,
        )

        results = {
            "total_barbarians_in_radius": len(all_targets),
            "am_farm_attacks_sent": 0,
            "bootstrap_attacks_sent": 0,
            "skipped_in_transit": 0,
            "skipped_losses": 0,
            "skipped_wall": 0,
            "errors": 0,
            "targets_with_resources": 0,
            "new_barbarians": 0,
        }

        if not all_targets:
            logger.info(f"[{account.world}] Nenhuma aldeia bárbara detetada no raio de {cfg.max_distance} campos.")
            return results

        # 2. Algoritmo de Priorização Inteligente:
        # Prioriza bárbaras com recursos confirmados ('full' -> 100), parciais ('partial' -> 80),
        # novas bárbaras não listadas ('none' -> 70), desconhecidas ('unknown' -> 50) e vazias em cooldown ('empty' -> 30/10).
        # Critério secundário: proximidade da aldeia (distância ascendente).
        now_ts = time.time()
        for t in all_targets:
            if t.loot_status in ("full", "partial"):
                results["targets_with_resources"] += 1
            elif not t.is_in_am_farm or t.report_color == "none":
                results["new_barbarians"] += 1

        def get_farm_target_priority(t: FarmTarget) -> Tuple[int, float]:
            if t.loot_status == "full":
                prio = 100
            elif t.loot_status == "partial":
                prio = 80
            elif not t.is_in_am_farm or t.report_color == "none":
                prio = 70
            elif t.loot_status == "unknown":
                prio = 50
            elif t.loot_status == "empty":
                last_time = self._target_last_farmed.get(t.target_coords, 0.0)
                prio = 30 if (now_ts - last_time >= 600.0) else 10
            else:
                prio = 40
            return (-prio, t.distance)

        all_targets.sort(key=get_farm_target_priority)

        # Carregar templates A e B do AM Farm
        am_state = await self.get_am_farm_state(account, village_id=v_id)
        tmpl_a_troops = am_state.template_a_troops
        tmpl_b_troops = am_state.template_b_troops
        default_tmpl = cfg.default_template.upper()

        # Determina o modelo ativo de tropas configurado pelo utilizador
        active_tmpl_dict = tmpl_a_troops if default_tmpl == "A" else tmpl_b_troops
        if not active_tmpl_dict or sum(active_tmpl_dict.values()) == 0:
            active_tmpl_dict = tmpl_b_troops if default_tmpl == "A" else tmpl_a_troops

        # Se nenhum modelo estiver configurado com tropas (> 0), suspende a ronda de ataques
        if not active_tmpl_dict or sum(active_tmpl_dict.values()) == 0:
            logger.warning(
                f"[{account.world}] ⚠️ Nenhum modelo de saque (A ou B) configurado com tropas. "
                f"Defina as tropas do Modelo no botão 'Editar' do Assistente de Saque antes de iniciar o farm."
            )
            return results

        bootstrap_squad = UnitsCount.from_dict(active_tmpl_dict)

        total_sent = 0
        consecutive_no_troops = 0
        cycle_farmed_coords: Set[str] = set()
        cooldown_secs = getattr(cfg, "target_cooldown_minutes", 10.0) * 60.0

        for target in all_targets:
            if total_sent >= max_attacks:
                break

            coords = target.target_coords or f"{target.x}|{target.y}"
            if coords in cycle_farmed_coords:
                continue

            last_farmed_time = self._target_last_farmed.get(coords, 0.0)
            time_since_last = now_ts - last_farmed_time

            # 1. Prevenção de colisões / ataques em trânsito ou validação de cooldown
            if last_farmed_time > 0 and time_since_last < cooldown_secs:
                results["skipped_in_transit"] += 1
                continue

            if cfg.avoid_concurrent_attacks and (target.has_attack_in_transit or coords in self._recent_farm_targets):
                results["skipped_in_transit"] += 1
                continue

            # 2. Se a aldeia já está no AM Farm, envia pelo assistente rápido
            if target.is_in_am_farm:
                # Filtro de perdas anteriores
                if cfg.stop_on_losses and target.report_color in ("yellow", "red"):
                    results["skipped_losses"] += 1
                    continue

                if cfg.skip_wall and target.wall_level > 0:
                    results["skipped_wall"] += 1
                    continue

                # Seleção Inteligente de Modelo (A vs B)
                chosen_letter, t_id = select_optimal_farm_template(
                    target=target,
                    preferred_template=default_tmpl,
                    haul_capacities=am_state.haul_capacities,
                )

                if not t_id:
                    consecutive_no_troops += 1
                    if consecutive_no_troops >= 4:
                        logger.info(
                            f"[{account.world}] ⏸️ Tropas disponíveis na aldeia {v_id} esgotadas para modelos A/B. Ciclo pausado até ao regresso de tropas."
                        )
                        break
                    continue

                consecutive_no_troops = 0
                success = await self.send_am_farm_attack(
                    account=account,
                    target_id=target.target_id,
                    template_id=t_id,
                    village_id=v_id,
                )
                if success:
                    results["am_farm_attacks_sent"] += 1
                    total_sent += 1
                    if coords:
                        cycle_farmed_coords.add(coords)
                        self._recent_farm_targets.add(coords)
                        self._target_last_farmed[coords] = time.time()
                    target.has_attack_in_transit = True

                    try:
                        tracker = getattr(account, "stats_tracker", None) or (account.get_stats_tracker() if hasattr(account, "get_stats_tracker") else None)
                        if tracker:
                            tracker.record_command(command_type="farm", target_coords=target.target_coords, success=True)
                            haul_cap = 300
                            if am_state and am_state.haul_capacities:
                                haul_cap = am_state.haul_capacities.get(chosen_letter.lower(), 300) or 300
                            ratio = 1.0 if target.loot_status == "full" else (0.5 if target.loot_status == "partial" else 0.75)
                            cap_per_res = max(30, int((haul_cap * ratio) // 3))
                            tracker.record_farm_loot(
                                wood=cap_per_res, stone=cap_per_res, iron=cap_per_res,
                                village_id=v_id,
                                target_x=target.x, target_y=target.y,
                                village_name=target.target_name,
                            )
                    except Exception as e_st:
                        logger.debug(f"Aviso ao registar telemetria de farm no ciclo de raio: {e_st}")

                    logger.info(
                        f"[{account.world}] 🌾 [SAQUE DESPACHADO] Modelo {chosen_letter.upper()} enviado com sucesso para "
                        f"{target.target_name} ({target.target_coords}) [Loot: {target.loot_status.upper()} | Dist: {target.distance:.1f}c | Muralha: {target.wall_level if target.wall_level is not None else '?'}]"
                    )

                    # Jitter estocástico gaussiano configurável
                    await asyncio.sleep(get_gaussian_delay(cfg.min_delay_per_attack_ms, cfg.max_delay_per_attack_ms))
                else:
                    results["errors"] += 1

            elif cfg.bootstrap_unlisted_barbarians:
                # 3. Bootstrap via Praça de Reunião para bárbaras não listadas no AM Farm
                # Utiliza estritamente o modelo de tropas configurado pelo utilizador
                success = await self.bootstrap_unlisted_barbarian(
                    account=account,
                    target=target,
                    template_troops=bootstrap_squad,
                    village_id=v_id,
                )
                if success:
                    results["bootstrap_attacks_sent"] += 1
                    total_sent += 1
                    if coords:
                        cycle_farmed_coords.add(coords)
                        self._recent_farm_targets.add(coords)
                        self._target_last_farmed[coords] = time.time()
                    delay = get_human_delay(1.5, 0.4, 0.8, 2.5)
                    await asyncio.sleep(delay)
                else:
                    results["errors"] += 1
                    try:
                        p_state = await self.place_manager.get_state(account, village_id=v_id)
                        if not p_state.units.has_units(bootstrap_squad):
                            logger.info(
                                f"[{account.world}] ⏸️ Tropas na aldeia {v_id} insuficientes para cobrir mais esquadrões do Modelo {default_tmpl} ({bootstrap_squad.to_summary_str()}). Ronda suspensa até ao regresso/recrutamento de tropas."
                            )
                            break
                    except Exception as e:
                        logger.debug(f"Aviso ao consultar tropas na Praça: {e}")

        total_attacks = results["am_farm_attacks_sent"] + results["bootstrap_attacks_sent"]
        results["total_attacks"] = total_attacks
        results["world"] = account.world
        results["village_id"] = v_id

        # Limpa da memória alvos cujo cooldown já expirou para permitir reenvio
        cutoff = now_ts - max(cooldown_secs, 3600.0)
        self._target_last_farmed = {k: v for k, v in self._target_last_farmed.items() if v > cutoff}
        self._recent_farm_targets = set(self._target_last_farmed.keys())
        if total_attacks > 0:
            results["message"] = (
                f"🌾 Auto-Farm: {total_attacks} saques despachados "
                f"({results['am_farm_attacks_sent']} AM Farm com recursos, "
                f"{results['bootstrap_attacks_sent']} novas bárbaras no raio)."
            )
        else:
            results["message"] = (
                f"🌾 Auto-Farm: Varredura concluída ({results['total_barbarians_in_radius']} bárbaras mapeadas no raio). "
                f"Todos os alvos prioritários já possuem ataques a caminho."
            )

        # Dispara broadcast de telemetria e notificações para o frontend
        broadcast_fn = getattr(account, "_broadcast_sync", None) or self.broadcast_callback
        if broadcast_fn:
            try:
                broadcast_fn("FARM_CYCLE_DONE", results)
            except Exception as e_bc:
                logger.debug(f"Aviso ao emitir broadcast FARM_CYCLE_DONE: {e_bc}")

        logger.info(f"[{account.world}] {results['message']}")
        return results

    async def run_place_farm_wave(
        self,
        account: TribalAccount,
        targets: List[Tuple[int, int]],
        troops: UnitsCount,
        max_attacks: int = 30,
        village_id: Optional[int] = None,
    ) -> int:
        """
        Modo de Fallback: executa uma onda de saques diretamente pela Praça de Reunião
        para uma lista de coordenadas de aldeias bárbaras.
        """
        if not targets:
            logger.info("Nenhum alvo de farm configurado na lista de coordenadas.")
            return 0

        sent_count = 0
        logger.info(
            f"[{account.world}] A iniciar onda de Farm via Praça para {len(targets)} alvos..."
        )

        for coords in targets:
            if sent_count >= max_attacks:
                break

            # Envia o comando em 2 etapas
            success = await self.place_manager.send_command(
                account=account,
                target_coords=coords,
                units=troops,
                is_attack=True,
                village_id=village_id,
                allow_partial=False,
            )

            if success:
                sent_count += 1
                try:
                    tracker = getattr(account, "stats_tracker", None) or (account.get_stats_tracker() if hasattr(account, "get_stats_tracker") else None)
                    if tracker:
                        tracker.record_command(command_type="farm", target_coords=f"{coords[0]}|{coords[1]}", success=True)
                        cap = troops.carrying_capacity() // 3
                        tracker.record_farm_loot(
                            wood=max(50, cap), stone=max(50, cap), iron=max(50, cap),
                            village_id=village_id or account.current_village_id or 0,
                            target_x=coords[0], target_y=coords[1],
                            village_name="Aldeia Bárbara",
                        )
                except Exception as e_st:
                    logger.debug(f"Aviso ao registar telemetria de farm via Praça: {e_st}")

                logger.info(f"[{account.world}] Saque #{sent_count} via Praça enviado -> ({coords[0]}|{coords[1]})")
                # Intervalo realista entre saques via praça (1.5s a 3.5s)
                delay = get_human_delay(2.5, 0.5, 1.5, 4.0)
                await asyncio.sleep(delay)
            else:
                # Tropas insuficientes para continuar a onda
                logger.info(f"[{account.world}] Tropas esgotadas para farming via Praça. Onda interrompida.")
                break

        return sent_count

    async def get_radar_farm_plan(
        self,
        account: TribalAccount,
        radius: float = 15.0,
        squad_template: Optional[UnitsCount] = None,
        max_attacks: int = 30,
        skip_active_targets: bool = True,
        village_id: Optional[int] = None,
        use_cache: bool = True,
    ) -> RadarFarmPlan:
        """
        Calcula o plano de alocação de micro-esquadrões para as bárbaras mais próximas,
        sem enviar comandos de ataque.
        """
        v_id = village_id or account.current_village_id
        curr_v = account.villages.get(v_id) if account.villages else None
        cx = curr_v.x if curr_v else 500
        cy = curr_v.y if curr_v else 500

        if not self.map_manager:
            from engine.actions.map import MapManager
            self.map_manager = MapManager()

        # 1. Scanner de aldeias bárbaras ordenadas por proximidade
        barbarians = await self.map_manager.scan_nearby_barbarians(
            account=account,
            center_x=cx,
            center_y=cy,
            radius=radius,
            village_id=v_id,
            use_cache=use_cache,
        )

        # 2. Leitura do estado da Praça de Reunião
        place_state = await self.place_manager.get_state(account, village_id=v_id)

        # 3. Extrair coordenadas com ataques atualmente a caminho para evitar repetições
        active_target_coords = set()
        if skip_active_targets:
            for cmd in place_state.commands:
                if cmd.movement_type in ("attack", "command"):
                    clean_coords = cmd.target_coords.strip("() ")
                    if clean_coords:
                        active_target_coords.add(clean_coords)

        # 4. Filtrar bárbaras elegíveis (não atacadas atualmente se skip_active_targets)
        eligible_targets: List[Tuple[int, int]] = []
        for b in barbarians:
            b_coord_str = f"{b.x}|{b.y}"
            if skip_active_targets and b_coord_str in active_target_coords:
                continue
            eligible_targets.append(b.coords_tuple)

        # Se todas as bárbaras já tiverem ataques e ainda houver bárbaras, usa todas
        if not eligible_targets and barbarians:
            eligible_targets = [b.coords_tuple for b in barbarians]

        # 5. Alocação de esquadrões baseada estritamente no modelo
        if squad_template and squad_template.total > 0:
            squad = squad_template
        else:
            am_state = await self.get_am_farm_state(account, village_id=v_id)
            tmpl_dict = am_state.template_a_troops if am_state.template_a_troops and sum(am_state.template_a_troops.values()) > 0 else am_state.template_b_troops
            squad = UnitsCount.from_dict(tmpl_dict) if tmpl_dict else UnitsCount()

        squads_assigned = allocate_dynamic_squads(
            available_units=place_state.units,
            squad_template=squad,
            targets=eligible_targets,
            max_squads=max_attacks,
        )

        total_cap = sum(sq.carrying_capacity() for _, sq in squads_assigned)

        return RadarFarmPlan(
            village_id=v_id or 0,
            total_barbarians_found=len(barbarians),
            eligible_targets=eligible_targets,
            squads_assigned=squads_assigned,
            total_carrying_capacity=total_cap,
        )

    async def run_radar_farm_cycle(
        self,
        account: TribalAccount,
        radius: float = 15.0,
        squad_template: Optional[UnitsCount] = None,
        max_attacks: int = 30,
        skip_active_targets: bool = True,
        village_id: Optional[int] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Executa um ciclo completo de Radar de Bárbaras com alocação dinâmica de tropas:
        Calcula o plano de alocação e despacha os ataques sequencialmente.
        """
        plan = await self.get_radar_farm_plan(
            account=account,
            radius=radius,
            squad_template=squad_template,
            max_attacks=max_attacks,
            skip_active_targets=skip_active_targets,
            village_id=village_id,
            use_cache=use_cache,
        )

        if not plan.squads_assigned:
            logger.info(
                f"[{account.world}] Radar de Bárbaras (Aldeia {plan.village_id}): "
                f"{plan.total_barbarians_found} bárbaras mapeadas, mas sem tropas suficientes para novos esquadrões."
            )
            return {
                "sent_attacks": 0,
                "total_targets": len(plan.eligible_targets),
                "total_barbarians_found": plan.total_barbarians_found,
                "total_carrying_capacity": 0,
            }

        sent_count = 0
        total_loot_capacity = 0
        logger.info(
            f"[{account.world}] 🚀 A despachar {len(plan.squads_assigned)} micro-ataques pelo Radar de Bárbaras..."
        )

        for target_coords, squad in plan.squads_assigned:
            success = await self.place_manager.send_command(
                account=account,
                target_coords=target_coords,
                units=squad,
                is_attack=True,
                village_id=plan.village_id,
                allow_partial=False,
            )
            if success:
                sent_count += 1
                total_loot_capacity += squad.carrying_capacity()
                try:
                    tracker = getattr(account, "stats_tracker", None) or (account.get_stats_tracker() if hasattr(account, "get_stats_tracker") else None)
                    if tracker:
                        tracker.record_command(command_type="farm", target_coords=f"{target_coords[0]}|{target_coords[1]}", success=True)
                        cap = squad.carrying_capacity() // 3
                        tracker.record_farm_loot(
                            wood=max(50, cap), stone=max(50, cap), iron=max(50, cap),
                            village_id=plan.village_id or account.current_village_id or 0,
                            target_x=target_coords[0], target_y=target_coords[1],
                            village_name="Aldeia Bárbara",
                        )
                except Exception as e_st:
                    logger.debug(f"Aviso ao registar telemetria de Radar: {e_st}")

                logger.info(
                    f"[{account.world}] Saque #{sent_count} via Radar -> ({target_coords[0]}|{target_coords[1]}) "
                    f"[{squad.to_summary_str()} | Cap: {squad.carrying_capacity()}]"
                )
                delay = get_human_delay(2.2, 0.4, 1.2, 3.5)
                await asyncio.sleep(delay)
            else:
                logger.warning(
                    f"[{account.world}] Interrupção no despacho de farm via Radar para ({target_coords[0]}|{target_coords[1]})."
                )
                break

        logger.info(
            f"[{account.world}] ✅ Ciclo de Radar de Bárbaras concluído: "
            f"{sent_count} ataques despachados (Capacidade de saque total: {total_loot_capacity})."
        )
        return {
            "sent_attacks": sent_count,
            "total_targets": len(plan.eligible_targets),
            "total_barbarians_found": plan.total_barbarians_found,
            "total_carrying_capacity": total_loot_capacity,
        }

    def schedule_continuous_radar_farm(
        self,
        scheduler: TaskScheduler,
        account: TribalAccount,
        radius: float = 15.0,
        squad_template: Optional[UnitsCount] = None,
        interval_minutes: float = 5.0,
        max_attacks: int = 30,
        skip_active_targets: bool = True,
        village_id: Optional[int] = None,
    ) -> None:
        """
        Agenda no TaskScheduler o loop contínuo e recorrente de Radar Farming.
        Mantém as micro-tropas sempre em rotação permanente de saques.
        """
        interval_seconds = max(60.0, interval_minutes * 60.0)
        squad = squad_template or UnitsCount(spear=5, spy=1)

        async def continuous_radar_task():
            try:
                await self.run_radar_farm_cycle(
                    account=account,
                    radius=radius,
                    squad_template=squad,
                    max_attacks=max_attacks,
                    skip_active_targets=skip_active_targets,
                    village_id=village_id,
                )
            except Exception as e:
                logger.warning(f"Erro no ciclo contínuo de Radar Farming: {e}")
            finally:
                if scheduler.is_running and not scheduler.is_paused:
                    scheduler.schedule_human_like(
                        name=f"ContinuousRadarFarm-Village-{village_id or 'active'}",
                        priority=TaskPriority.FARM,
                        action=continuous_radar_task,
                        base_seconds=interval_seconds,
                        std_dev=interval_seconds * 0.15,
                        min_seconds=max(30.0, interval_seconds * 0.5),
                        max_seconds=interval_seconds * 1.5,
                    )

        scheduler.schedule(
            name=f"ContinuousRadarFarm-Village-{village_id or 'active'}",
            priority=TaskPriority.FARM,
            action=continuous_radar_task,
            delay_seconds=10.0,
        )
        logger.info(
            f"Radar de Bárbaras contínuo agendado a cada ~{interval_minutes:.1f} minutos (Raio: {radius:.1f} campos)."
        )

    def schedule_auto_farm(
        self,
        scheduler: TaskScheduler,
        account: TribalAccount,
        farm_config: Any,
        village_id: Optional[int] = None,
        bot_config: Optional[Any] = None,
    ) -> None:
        """
        Agenda no TaskScheduler a execução periódica contínua de ondas de Micro-Farming
        na fila de prioridade TaskPriority.FARM = 20.
        Suporta 'am_farm', 'place' e 'radar'.
        Implementa auto-pausa instantânea em caso de alerta anti-bot / pausa de conta.
        """
        min_int = getattr(farm_config, "min_interval_seconds", None)
        max_int = getattr(farm_config, "max_interval_seconds", None)
        if min_int is not None and max_int is not None and min_int > 0:
            base_interval_seconds = (min_int + max_int) / 2.0
            min_sec = float(min_int)
            max_sec = float(max_int)
        else:
            interval_minutes = getattr(farm_config, "interval_minutes", 10.0)
            base_interval_seconds = interval_minutes * 60.0
            min_sec = max(30.0, base_interval_seconds * 0.5)
            max_sec = base_interval_seconds * 1.5

        mode = getattr(farm_config, "mode", "am_farm").lower().strip()

        async def auto_farm_task():
            # Verificação de segurança: se a conta estiver pausada ou interceptada por captcha
            if getattr(account, "is_paused", False) or getattr(account, "captcha_detected", False):
                logger.info(f"[{account.world}] ⏸️ Auto-Farm pausado (alerta anti-bot ou bot pausado pelo utilizador).")
                return

            try:
                if mode == "radar":
                    raw_troops = getattr(farm_config, "custom_troops", {})
                    troops = UnitsCount.from_dict(raw_troops) if isinstance(raw_troops, dict) else UnitsCount(spear=5, spy=1)
                    scan_radius = getattr(farm_config, "map_scan_radius", 15.0)
                    skip_active = getattr(farm_config, "skip_active_targets", True)
                    await self.run_radar_farm_cycle(
                        account=account,
                        radius=scan_radius,
                        squad_template=troops,
                        skip_active_targets=skip_active,
                        village_id=village_id,
                    )
                elif mode == "place":
                    targets = getattr(farm_config, "custom_targets", [])
                    raw_troops = getattr(farm_config, "custom_troops", {})
                    troops = UnitsCount.from_dict(raw_troops) if isinstance(raw_troops, dict) else UnitsCount(spear=5, spy=1)

                    if not targets and getattr(farm_config, "use_map_scanner", True):
                        if not self.map_manager:
                            from engine.actions.map import MapManager
                            self.map_manager = MapManager()

                        scan_radius = getattr(farm_config, "map_scan_radius", 15.0)
                        await self.map_manager.run_map_farm_wave(
                            account=account,
                            farm_manager=self,
                            troops=troops,
                            radius=scan_radius,
                            village_id=village_id,
                        )
                    else:
                        await self.run_place_farm_wave(
                            account=account,
                            targets=targets,
                            troops=troops,
                            village_id=village_id,
                        )
                else:
                    # Modo AM Farm / Varredura Abrangente de Raio
                    if getattr(farm_config, "scan_all_radius_barbarians", True):
                        await self.run_comprehensive_radius_farm_cycle(
                            account=account,
                            config=farm_config,
                            village_id=village_id,
                        )
                    else:
                        template = getattr(farm_config, "template", "A")
                        max_dist = getattr(farm_config, "max_distance", 15.0)
                        skip_losses = getattr(farm_config, "skip_losses", True)
                        skip_wall = getattr(farm_config, "skip_wall", True)
                        await self.run_am_farm_wave(
                            account=account,
                            template=template,
                            max_distance=max_dist,
                            skip_losses=skip_losses,
                            skip_wall=skip_wall,
                            village_id=village_id,
                        )
            except Exception as e:
                logger.warning(f"Erro na execução da onda de farm: {e}")
            finally:
                try:
                    tracker = getattr(account, "stats_tracker", None)
                    broadcast_fn = getattr(account, "_broadcast_sync", None)
                    if broadcast_fn and tracker:
                        broadcast_fn("STATS_UPDATED", tracker.get_summary())
                except Exception as e:
                    logger.debug(f"Aviso ao atualizar estatísticas pós-farm: {e}")

                # Reagenda para o próximo ciclo de farm com delay estocástico gaussiano dinâmico
                if scheduler.is_running and not scheduler.is_paused:
                    cur_min_int = getattr(farm_config, "min_interval_seconds", None)
                    cur_max_int = getattr(farm_config, "max_interval_seconds", None)
                    if cur_min_int is not None and cur_max_int is not None and cur_min_int > 0:
                        cur_base = (cur_min_int + cur_max_int) / 2.0
                        cur_min = float(cur_min_int)
                        cur_max = float(cur_max_int)
                    else:
                        cur_inv_m = getattr(farm_config, "interval_minutes", 10.0)
                        cur_base = cur_inv_m * 60.0
                        cur_min = max(30.0, cur_base * 0.5)
                        cur_max = cur_base * 1.5

                    scheduler.schedule_human_like(
                        name=f"AutoFarm-Village-{village_id or 'active'}",
                        priority=TaskPriority.FARM,
                        action=auto_farm_task,
                        base_seconds=cur_base,
                        std_dev=max(10.0, (cur_max - cur_min) / 6.0),
                        min_seconds=cur_min,
                        max_seconds=cur_max,
                    )

        # Agenda a primeira onda de farm após um delay inicial humano (ex.: 15 segundos)
        scheduler.schedule(
            name=f"AutoFarm-Village-{village_id or 'active'}",
            priority=TaskPriority.FARM,
            action=auto_farm_task,
            delay_seconds=15.0,
        )
        logger.info(
            f"[{account.world}] Micro-Farming agendado (Prioridade: {TaskPriority.FARM.name}, Modo: {mode.upper()}, "
            f"Intervalo: ~{base_interval_seconds/60:.1f}min)."
        )
