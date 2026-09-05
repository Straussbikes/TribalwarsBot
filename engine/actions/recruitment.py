"""
Tribal Wars Mobile Automation Engine - RecruitmentManager (screen=barracks, stable, garage)
Gestão de Recrutamento Militar: Quartel, Estábulo e Oficina com controlo de metas de exército,
produção contínua em pequenos lotes e validação de população livre da Fazenda.
"""

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional

from engine.actions.place import PlaceManager
from engine.core.account import TribalAccount
from engine.core.models import TaskPriority
from engine.core.scheduler import TaskScheduler
from engine.utils.parsers import parse_recruitment_page

logger = logging.getLogger(__name__)

# Mapeamento canónico de cada unidade para o respetivo edifício militar
UNIT_TO_BUILDING: Dict[str, str] = {
    "spear": "barracks",
    "sword": "barracks",
    "axe": "barracks",
    "archer": "barracks",
    "spy": "stable",
    "light": "stable",
    "marcher": "stable",
    "heavy": "stable",
    "ram": "garage",
    "catapult": "garage",
}

BUILDING_UNITS: Dict[str, List[str]] = {
    "barracks": ["spear", "sword", "axe", "archer"],
    "stable": ["spy", "light", "marcher", "heavy"],
    "garage": ["ram", "catapult"],
}

# Tabela de pré-requisitos mínimos de edifícios para desbloqueio/pesquisa de cada unidade
UNIT_BUILDING_REQUIREMENTS: Dict[str, Dict[str, int]] = {
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


UNIT_POP_COST: Dict[str, int] = {
    "spear": 1,
    "sword": 1,
    "axe": 1,
    "archer": 1,
    "spy": 2,
    "light": 4,
    "marcher": 5,
    "heavy": 6,
    "ram": 5,
    "catapult": 8,
}

# Custos canónicos de recursos por unidade (Madeira, Argila, Ferro)
UNIT_RESOURCE_COSTS: Dict[str, Dict[str, int]] = {
    "spear": {"wood": 50, "stone": 30, "iron": 10},       # Total: 90
    "spy": {"wood": 50, "stone": 50, "iron": 20},         # Total: 120
    "sword": {"wood": 30, "stone": 30, "iron": 70},       # Total: 130
    "axe": {"wood": 60, "stone": 30, "iron": 40},         # Total: 130
    "archer": {"wood": 100, "stone": 30, "iron": 60},     # Total: 190
    "light": {"wood": 125, "stone": 100, "iron": 250},    # Total: 475
    "marcher": {"wood": 250, "stone": 100, "iron": 150},  # Total: 500
    "ram": {"wood": 300, "stone": 200, "iron": 200},      # Total: 700
    "catapult": {"wood": 320, "stone": 400, "iron": 100}, # Total: 820
    "heavy": {"wood": 200, "stone": 150, "iron": 600},    # Total: 950
}

UNIT_TOTAL_COST: Dict[str, int] = {
    u: sum(costs.values()) for u, costs in UNIT_RESOURCE_COSTS.items()
}


@dataclass
class TrainingOrder:
    """Representação de uma ordem ativa na fila de recrutamento."""
    unit: str
    count: int
    timer_str: str = ""
    finish_time: str = ""
    cancel_url: Optional[str] = None


@dataclass
class RecruitmentState:
    """Estado consolidado de um edifício militar."""
    building: str
    available_units: Dict[str, int] = field(default_factory=dict)
    queue: List[TrainingOrder] = field(default_factory=list)
    total_in_queue: Dict[str, int] = field(default_factory=dict)
    own_units: Dict[str, int] = field(default_factory=dict)
    in_village_units: Dict[str, int] = field(default_factory=dict)

    @property
    def is_training(self) -> bool:
        return len(self.queue) > 0


class RecruitmentManager:
    """
    Controlador de automação de Recrutamento Militar.
    Permite ler filas de treino, verificar custos e capacidade máxima,
    e submeter ordens de recrutamento em lotes inteligentes.
    """

    def __init__(
        self,
        place_manager: Optional[PlaceManager] = None,
        smith_manager: Optional[Any] = None,
    ):
        self.place_manager = place_manager or PlaceManager()
        if smith_manager is not None:
            self.smith_manager = smith_manager
        else:
            from engine.actions.smith import SmithManager
            self.smith_manager = SmithManager()

    async def get_building_state(
        self, account: TribalAccount, building: str, village_id: Optional[int] = None
    ) -> RecruitmentState:
        """
        Consulta o ecrã do edifício militar ('barracks', 'stable' ou 'garage')
        e extrai as tropas disponíveis, contagem própria/total e ordens ativas na fila.
        """
        html = await account.get_screen(building, village_id=village_id, extra_params={"page": None})
        raw_data = parse_recruitment_page(html)

        orders: List[TrainingOrder] = [
            TrainingOrder(
                unit=str(q["unit"]),
                count=int(q["count"]),
                timer_str=str(q.get("timer_str", "")),
                finish_time=str(q.get("finish_time", "")),
                cancel_url=q.get("cancel_url"),
            )
            for q in raw_data.get("queue", [])
        ]

        own_units = raw_data.get("own_units", {})
        in_village_units = raw_data.get("in_village_units", {})

        state = RecruitmentState(
            building=building,
            available_units=raw_data.get("available_units", {}),
            queue=orders,
            total_in_queue=raw_data.get("total_in_queue", {}),
            own_units=own_units,
            in_village_units=in_village_units,
        )

        v_id = village_id or account.current_village_id
        if v_id:
            target_v = account.villages.get(v_id) or account.current_village
            if target_v:
                if own_units:
                    if not target_v.own_troops:
                        target_v.own_troops = {}
                    target_v.own_troops.update(own_units)
                if in_village_units:
                    if not target_v.troops_in_village:
                        target_v.troops_in_village = {}
                    target_v.troops_in_village.update(in_village_units)

        logger.info(
            f"[{account.world}] {building.capitalize()}: {len(orders)} ordens na fila "
            f"(Total em treino: {sum(state.total_in_queue.values())} tropas)."
        )
        return state

    async def train_units(
        self,
        account: TribalAccount,
        building: str,
        orders: Dict[str, int],
        village_id: Optional[int] = None,
    ) -> bool:
        """
        Submete o formulário de treino de unidades para 'screen={building}&action=train'.
        Injeta o token CSRF e micro-jitter de toque em ecrã.
        """
        valid_orders = {u: int(cnt) for u, cnt in orders.items() if int(cnt) > 0}
        if not valid_orders:
            return False

        v_id = village_id or account.current_village_id
        order_summary = ", ".join(f"{cnt}x {u}" for u, cnt in valid_orders.items())
        logger.info(f"[{account.world}] A recrutar no {building.capitalize()}: {order_summary}...")

        # Prepara payload compatível com inputs planos ('spear=10') e aninhados ('units[spear]=10')
        post_data = {}
        for u, cnt in valid_orders.items():
            post_data[u] = str(cnt)
            post_data[f"units[{u}]"] = str(cnt)
        if account.csrf_token:
            post_data["h"] = account.csrf_token

        try:
            html = await account.post_action(
                screen=building,
                action="train",
                data=post_data,
                village_id=v_id,
                extra_params={"mode": "train"},
                apply_jitter=True,
            )

            # 1. Inspeciona se o jogo reportou erro (ex.: falta de recursos, unidade bloqueada)
            if isinstance(html, str):
                import re
                error_m = re.search(
                    r'<div[^>]*class=["\'][^"\']*(?:error_box|info_box\s+error|error_message)[^"\']*["\'][^>]*>(.*?)</div>|<span[^>]*class=["\']error["\'][^>]*>(.*?)</span>',
                    html,
                    re.DOTALL | re.IGNORECASE,
                )
                if error_m:
                    raw_err = error_m.group(1) or error_m.group(2) or ""
                    clean_err = re.sub(r'<[^>]+>', ' ', raw_err).strip()
                    if clean_err:
                        logger.warning(f"[{account.world}] ⚠️ Aviso do jogo ao recrutar no {building}: {clean_err}")
                        return False

                # 2. Confirma se a fila de treino foi atualizada
                parsed_res = parse_recruitment_page(html)
                active_q = parsed_res.get("queue", [])
                total_in_q = sum(parsed_res.get("total_in_queue", {}).values())

                logger.info(
                    f"[{account.world}] ✅ Recrutamento processado no {building.capitalize()}: {order_summary} "
                    f"({len(active_q)} ordens ativas na fila, {total_in_q} tropas em treino)."
                )
            else:
                logger.info(f"[{account.world}] ✅ Recrutamento processado no {building.capitalize()}: {order_summary}")

            try:
                tracker = getattr(account, "stats_tracker", None) or (account.get_stats_tracker() if hasattr(account, "get_stats_tracker") else None)
                if tracker:
                    for u, cnt in valid_orders.items():
                        if int(cnt) > 0:
                            tracker.record_recruitment(village_id=v_id or 0, unit=u, count=int(cnt))
            except Exception as e_st:
                logger.warning(f"Aviso ao registar estatísticas de recrutamento: {e_st}")

            if hasattr(account, "_broadcast_sync") and callable(account._broadcast_sync):
                account._broadcast_sync("STATS_UPDATED", {"reason": "recruitment", "units": valid_orders})
                account._broadcast_sync("RECRUITMENT_UPDATED", {"village_id": v_id, "units": valid_orders})

            return True
        except Exception as e:
            logger.error(f"[{account.world}] Falha ao recrutar no {building}: {e}")
            return False

    async def run_recruitment_cycle(
        self,
        account: TribalAccount,
        targets: Dict[str, int],
        batch_sizes: Dict[str, int],
        min_free_pop: int = 10,
        village_id: Optional[int] = None,
        max_queue_elements: int = 3,
    ) -> Dict[str, int]:
        """
        Executa um ciclo inteligente de recrutamento:
        1. Valida população livre na fazenda.
        2. Inspeciona tropas na aldeia e em treino para calcular o défice exato até à meta.
        3. Recruta em lotes configuráveis sem exceder os recursos disponíveis.
        """
        recruited_summary: Dict[str, int] = {}
        v_id = village_id or account.current_village_id

        # 1. Validação de População Livre da Fazenda
        free_pop = 9999
        try:
            village = await account.refresh_state(village_id=v_id)
            free_pop = village.resources.free_pop
            if free_pop <= 0 or (min_free_pop > 0 and free_pop < min_free_pop):
                logger.info(
                    f"[{account.world}] População livre ({free_pop}) < limite de segurança "
                    f"({min_free_pop}). Recrutamento suspenso para preservar melhorias de edifícios."
                )
                return recruited_summary
        except Exception as e:
            logger.warning(f"Não foi possível verificar população antes de recrutar: {e}")

        # Orçamento de população disponível para este ciclo
        pop_budget = max(0, free_pop - min_free_pop) if min_free_pop > 0 else free_pop

        # Recursos disponíveis na aldeia (acompanhados e deduzidos dinamicamente, respeitando reserva para edifícios)
        min_reserve = 0
        if hasattr(account, "config") and hasattr(account.config, "recruitment"):
            min_reserve = getattr(account.config.recruitment, "min_reserve_resources", 0)

        raw_wood = village.resources.wood if village else 0
        raw_stone = village.resources.stone if village else 0
        raw_iron = village.resources.iron if village else 0

        avail_wood = max(0, raw_wood - min_reserve) if min_reserve > 0 else raw_wood
        avail_stone = max(0, raw_stone - min_reserve) if min_reserve > 0 else raw_stone
        avail_iron = max(0, raw_iron - min_reserve) if min_reserve > 0 else raw_iron

        logger.info(
            f"[{account.world}] 🛡️⚔️ Ciclo de Recrutamento (Aldeia {v_id}): "
            f"Recursos Úteis: {avail_wood}M, {avail_stone}A, {avail_iron}F (Reserva: {min_reserve}) | Pop Livre: {free_pop} (Orçamento: {pop_budget}) | "
            f"Metas: {', '.join(f'{k}:{v}' for k, v in targets.items() if v > 0) or 'Nenhuma'}"
        )

        # 2. Leitura de tropas existentes na aldeia ativa
        try:
            place_state = await self.place_manager.get_state(account, village_id=v_id)
            troops_home = place_state.units.to_dict()
            if hasattr(self.place_manager, "get_village_units_overview"):
                await self.place_manager.get_village_units_overview(account, village_id=v_id)
        except Exception as e:
            logger.warning(f"Falha ao ler tropas na aldeia para cálculo de metas: {e}")
            troops_home = {}

        # Obtém níveis de edifícios conhecidos da aldeia
        village_buildings: Dict[str, int] = {}
        if village and hasattr(village, "buildings") and village.buildings:
            village_buildings = village.buildings
        elif v_id in account.villages and account.villages[v_id].buildings:
            village_buildings = account.villages[v_id].buildings

        # 3. Auto-pesquisa no Ferreiro para unidades necessárias cujos requisitos de edifícios foram atingidos
        needed_target_units = [u for u, target in targets.items() if target > 0]
        if needed_target_units and self.smith_manager:
            try:
                await self.smith_manager.auto_research_needed_units(
                    account=account,
                    village_id=v_id,
                    needed_units=needed_target_units,
                )
            except Exception as e:
                logger.debug(f"Erro suave ao auto-pesquisar tropas no Ferreiro: {e}")

        # 4. Processamento por edifício militar
        buildings_to_check = set()
        for u, target in targets.items():
            if target > 0 and u in UNIT_TO_BUILDING:
                buildings_to_check.add(UNIT_TO_BUILDING[u])

        for building in ("barracks", "stable", "garage"):
            if building not in buildings_to_check:
                continue

            # Verificação 1: Se os edifícios da aldeia são conhecidos e o edifício está nível 0
            if village_buildings and village_buildings.get(building, 0) < 1:
                logger.info(
                    f"[{account.world}] Edifício '{building}' ainda não construído na aldeia {v_id} (nível 0). "
                    f"Recrutamento ignorado para este edifício."
                )
                continue

            try:
                b_state = await self.get_building_state(account, building, village_id=v_id)
            except Exception as e:
                logger.warning(f"Falha ao consultar {building}: {e}")
                continue

            # Limite estrito de elementos simultâneos na fila de recrutamento (padrão: 3)
            current_queue_len = len(b_state.queue)
            if current_queue_len >= max_queue_elements:
                logger.info(
                    f"[{account.world}] ⏳ {building.capitalize()} com fila no limite "
                    f"({current_queue_len}/{max_queue_elements} ordens ativas). "
                    f"A aguardar conclusão antes de recrutar mais tropas."
                )
                continue

            slots_available = max(0, max_queue_elements - current_queue_len)
            orders_for_building: Dict[str, int] = {}

            # Prioriza o recrutamento das unidades com menor custo total de recursos
            candidate_units = sorted(
                BUILDING_UNITS.get(building, []),
                key=lambda u: UNIT_TOTAL_COST.get(u, 9999),
            )

            for unit in candidate_units:
                target_count = targets.get(unit, 0)
                if target_count <= 0:
                    continue

                # Verificação 2: Pré-requisitos de edifícios da unidade (apenas se a unidade NÃO estiver já disponível no ecrã)
                reqs = UNIT_BUILDING_REQUIREMENTS.get(unit, {})
                if village_buildings and reqs and unit not in b_state.available_units:
                    unmet = [
                        f"{req_b} nv{req_lvl} (atual: {village_buildings.get(req_b, 0)})"
                        for req_b, req_lvl in reqs.items()
                        if village_buildings.get(req_b, 0) < req_lvl
                    ]
                    if unmet:
                        if unit == "axe":
                            logger.info(
                                f"[{account.world}] ⚔️ [RUSH VIKINGS ATIVADO] Quartel parado/inapto para Vikings na aldeia {v_id} "
                                f"por falta de requisitos ({', '.join(unmet)}). Rush de Edifício Principal/Quartel/Ferreiro em prioridade máxima!"
                            )
                        elif unit == "light":
                            logger.info(
                                f"[{account.world}] 🐎 [RUSH CL ATIVADO] Estábulo parado/inapto para CL na aldeia {v_id} "
                                f"por falta de requisitos ({', '.join(unmet)}). Rush de Edifício Principal/Quartel/Ferreiro/Estábulo em prioridade máxima!"
                            )
                        else:
                            logger.info(
                                f"[{account.world}] Pré-requisitos não cumpridos para {unit.capitalize()} na aldeia {v_id}: "
                                f"{', '.join(unmet)}. Ignorando."
                            )
                        continue

                # Verificação 3: Unidade desbloqueada/pesquisada no ecrã de treino
                if unit not in b_state.available_units:
                    if unit == "axe":
                        logger.info(
                            f"[{account.world}] ⚔️ [RUSH VIKINGS] Vikings não pesquisados no Ferreiro da aldeia {v_id}. "
                            f"Pesquisa priorizada com urgência máxima no Ferreiro."
                        )
                    elif unit == "light":
                        logger.info(
                            f"[{account.world}] 🐎 [RUSH CL] Cavalaria Leve não pesquisada no Ferreiro da aldeia {v_id}. "
                            f"Pesquisa priorizada com urgência máxima no Ferreiro."
                        )
                    else:
                        logger.info(
                            f"[{account.world}] {unit.capitalize()} não está pesquisado ou desbloqueado no {building.capitalize()} "
                            f"da aldeia {v_id}. Ignorando."
                        )
                    continue

                # Tropas que PERTENCEM à aldeia (na aldeia + fora em apoio + a caminho/farm)
                # Prioridade 1: Extraído diretamente da linha da unidade no edifício militar (padrão X/Y do servidor)
                own_count = b_state.own_units.get(unit) if getattr(b_state, "own_units", None) else None

                # Prioridade 2: Consulta tropas próprias já catalogadas da aldeia
                if own_count is None:
                    target_v = account.villages.get(v_id) or account.current_village
                    if target_v and getattr(target_v, "own_troops", None) and unit in target_v.own_troops:
                        own_count = target_v.own_troops.get(unit)

                # Prioridade 3: Fallback defensivo (ex: mocks em testes que só informam troops_home)
                if own_count is None:
                    own_count = troops_home.get(unit, 0)

                in_queue_count = b_state.total_in_queue.get(unit, 0)
                needed = target_count - (own_count + in_queue_count)

                if needed <= 0:
                    logger.debug(
                        f"[{account.world}] Meta de {unit} atingida na aldeia {v_id} "
                        f"({own_count} pertencentes à aldeia + {in_queue_count} na fila >= {target_count})."
                    )
                    continue

                # Verificação prévia de recursos disponíveis na aldeia
                cost = UNIT_RESOURCE_COSTS.get(unit, {"wood": 50, "stone": 30, "iron": 10})
                max_by_res = min(
                    avail_wood // cost["wood"] if cost["wood"] > 0 else 9999,
                    avail_stone // cost["stone"] if cost["stone"] > 0 else 9999,
                    avail_iron // cost["iron"] if cost["iron"] > 0 else 9999,
                )

                # Limite da página web/mobile se existir
                server_max = b_state.available_units.get(unit, 999)
                max_recruitable = min(max_by_res, server_max)

                if max_recruitable <= 0:
                    logger.info(
                        f"[{account.world}] Recursos insuficientes para recrutar {unit.capitalize()} "
                        f"(Disponível: {avail_wood}M, {avail_stone}A, {avail_iron}F | Custo unid: {cost['wood']}M, {cost['stone']}A, {cost['iron']}F)."
                    )
                    continue

                # Limita pela população livre disponível
                pop_per_unit = UNIT_POP_COST.get(unit, 1)
                max_by_pop = pop_budget // pop_per_unit if pop_per_unit > 0 else needed
                if max_by_pop <= 0:
                    logger.info(f"[{account.world}] População livre insuficiente para treinar {unit.capitalize()}.")
                    continue

                # Lote dinâmico em porções de 5 (ou conforme batch_sizes configurado)
                portion = batch_sizes.get(unit, 5) if batch_sizes else 5
                to_recruit = min(needed, portion, max_recruitable, max_by_pop)

                if to_recruit > 0:
                    orders_for_building[unit] = to_recruit
                    pop_budget -= to_recruit * pop_per_unit
                    avail_wood -= to_recruit * cost["wood"]
                    avail_stone -= to_recruit * cost["stone"]
                    avail_iron -= to_recruit * cost["iron"]
                    logger.info(
                        f"[{account.world}] 🏹 Lote dinâmico planeado: {to_recruit}x {unit.capitalize()} "
                        f"(Meta: {target_count} | Aldeia possui: {own_count} | Na fila: {in_queue_count} | Faltam: {needed} | "
                        f"Custo: {to_recruit * cost['wood']}M, {to_recruit * cost['stone']}A, {to_recruit * cost['iron']}F | "
                        f"Recursos restantes: {avail_wood}M, {avail_stone}A, {avail_iron}F)."
                    )

                    # Interrompe se preencheu o número máximo de vagas restantes na fila
                    if len(orders_for_building) >= slots_available:
                        logger.debug(
                            f"[{account.world}] Limite de vagas na fila preenchido para {building} "
                            f"({len(orders_for_building)}/{slots_available} vagas preenchidas neste ciclo)."
                        )
                        break

            if orders_for_building:
                success = await self.train_units(
                    account=account,
                    building=building,
                    orders=orders_for_building,
                    village_id=v_id,
                )
                if success:
                    recruited_summary.update(orders_for_building)

        return recruited_summary

    def schedule_auto_recruit(
        self,
        scheduler: TaskScheduler,
        account: TribalAccount,
        recruit_config: Any,
        village_id: Optional[int] = None,
        enabled_check: Optional[Callable[[], bool]] = None,
        bot_config: Optional[Any] = None,
    ) -> None:
        """
        Agenda no TaskScheduler a rotina periódica contínua de Recrutamento Militar.
        """
        interval_minutes = getattr(recruit_config, "interval_minutes", 5.0)
        interval_seconds = interval_minutes * 60.0

        async def auto_recruit_task():
            if enabled_check and not enabled_check():
                return

            try:
                v_id = village_id or account.current_village_id
                if bot_config and hasattr(bot_config, "get_village_recruitment_targets"):
                    targets = bot_config.get_village_recruitment_targets(v_id)
                elif hasattr(recruit_config, "models") and isinstance(recruit_config.models, dict):
                    targets = recruit_config.models.get("attack", {}) or getattr(recruit_config, "targets", {})
                else:
                    targets = getattr(recruit_config, "targets", {})

                batch_sizes = getattr(recruit_config, "batch_sizes", {})
                min_free_pop = getattr(recruit_config, "min_free_pop", 10)
                max_queue_elements = getattr(recruit_config, "max_queue_elements", 3)

                recruited = await self.run_recruitment_cycle(
                    account=account,
                    targets=targets,
                    batch_sizes=batch_sizes,
                    min_free_pop=min_free_pop,
                    village_id=village_id,
                    max_queue_elements=max_queue_elements,
                )
                if recruited and hasattr(account, "_broadcast_sync") and callable(account._broadcast_sync):
                    account._broadcast_sync("STATS_UPDATED", {"reason": "auto_recruit", "recruited": recruited})
                    account._broadcast_sync("RECRUITMENT_UPDATED", {"village_id": v_id, "recruited": recruited})
            except Exception as e:
                logger.warning(f"Erro na rotina de recrutamento: {e}")
            finally:
                if scheduler.is_running and not scheduler.is_paused:
                    if not enabled_check or enabled_check():
                        scheduler.schedule_human_like(
                            name=f"AutoRecruit-Village-{village_id or 'active'}",
                            priority=TaskPriority.RECRUIT,
                            action=auto_recruit_task,
                            base_seconds=interval_seconds,
                            std_dev=interval_seconds * 0.15,
                            min_seconds=max(30.0, interval_seconds * 0.5),
                            max_seconds=interval_seconds * 1.5,
                        )

        # Agenda a primeira execução após 10 segundos
        scheduler.schedule(
            name=f"AutoRecruit-Village-{village_id or 'active'}",
            priority=TaskPriority.RECRUIT,
            action=auto_recruit_task,
            delay_seconds=10.0,
        )
        logger.info(f"Recrutamento Militar agendado a cada ~{interval_minutes:.1f} minutos.")
