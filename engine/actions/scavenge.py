"""
Tribal Wars Mobile Automation Engine - Scavenging (Coleta de Recursos)
Módulo responsável por:
1. Inspecionar o estado das 4 categorias de coleta (Lazy, Humble, Clever, Great).
2. Monitorizar expedições ativas e temporizadores de retorno.
3. Desbloquear categorias de coleta de forma inteligente.
4. Otimizar a distribuição proporcional de tropas para retorno simultâneo.
"""

from dataclasses import dataclass, field
import logging
import time
from typing import Dict, List, Optional

from engine.core.account import TribalAccount
from engine.utils.parsers import (
    parse_scavenge_available_troops,
    parse_scavenge_options,
)

logger = logging.getLogger(__name__)


UNIT_CARRY_CAPACITIES: Dict[str, int] = {
    "spear": 25,
    "sword": 15,
    "axe": 10,
    "archer": 10,
    "light": 80,
    "heavy": 50,
    "knight": 100,
}


def calculate_optimal_distribution(
    available_troops: Dict[str, int],
    ready_options: List[ScavengeOption],
    eligible_units: Optional[List[str]] = None,
    min_reserved: Optional[Dict[str, int]] = None,
) -> Dict[int, Dict[str, int]]:
    """
    Calcula a distribuição proporcional das tropas disponíveis entre as opções prontas
    de modo a igualar aproximadamente os tempos de regresso de todas as categorias.

    A capacidade de transporte alocada a cada opção é ponderada pela sua taxa de saque (loot_ratio).
    """
    if not ready_options:
        return {}

    if eligible_units is None:
        eligible_units = ["spear", "sword", "axe", "archer", "light"]
    if min_reserved is None:
        min_reserved = {}

    total_weight = sum(opt.loot_ratio for opt in ready_options)
    if total_weight <= 0:
        return {}

    distribution: Dict[int, Dict[str, int]] = {opt.id: {} for opt in ready_options}

    for unit in eligible_units:
        raw_count = available_troops.get(unit, 0)
        reserved = min_reserved.get(unit, 0)
        usable = max(0, raw_count - reserved)
        if usable <= 0:
            continue

        allocated_so_far = 0
        for opt in ready_options:
            weight_ratio = opt.loot_ratio / total_weight
            count = int(usable * weight_ratio)
            if count > 0:
                distribution[opt.id][unit] = count
                allocated_so_far += count

        remainder = usable - allocated_so_far
        if remainder > 0:
            # Atribui o restante à opção de maior multiplicador de saque
            highest_opt = max(ready_options, key=lambda o: o.loot_ratio)
            distribution[highest_opt.id][unit] = distribution[highest_opt.id].get(unit, 0) + remainder

    # Remove opções que ficaram sem tropas
    return {opt_id: units for opt_id, units in distribution.items() if any(c > 0 for c in units.values())}


@dataclass
class ScavengeOption:
    """Representação de uma das 4 categorias de Coleta de Recursos."""

    id: int  # 1: Lazy, 2: Humble, 3: Clever, 4: Great
    name: str
    description: str = ""
    is_unlocked: bool = False
    is_locked: bool = True
    is_scavenging: bool = False
    unlock_cost: Dict[str, int] = field(default_factory=lambda: {"wood": 0, "stone": 0, "iron": 0})
    unlock_time_seconds: int = 0
    time_remaining_seconds: int = 0
    return_time_iso: Optional[str] = None
    loot_ratio: float = 0.10
    duration_factor: float = 1.0

    @property
    def is_available_for_send(self) -> bool:
        """Indica se a categoria está pronta para receber uma nova expedição."""
        return self.is_unlocked and not self.is_scavenging


@dataclass
class ScavengeState:
    """Estado consolidado do ecrã de Coleta de Recursos da aldeia."""

    village_id: int
    options: List[ScavengeOption] = field(default_factory=list)
    available_troops: Dict[str, int] = field(default_factory=dict)
    active_expeditions_count: int = 0
    min_return_time_seconds: Optional[int] = None
    last_updated: float = field(default_factory=time.time)

    @property
    def unlocked_options(self) -> List[ScavengeOption]:
        return [opt for opt in self.options if opt.is_unlocked]

    @property
    def ready_options(self) -> List[ScavengeOption]:
        return [opt for opt in self.options if opt.is_available_for_send]


class ScavengeManager:
    """
    Controlador de automação da Coleta de Recursos (Scavenging).
    """

    async def get_scavenge_state(
        self,
        account: TribalAccount,
        village_id: Optional[int] = None,
    ) -> ScavengeState:
        """
        Carrega o ecrã de Coleta (screen=place&mode=scavenge) e devolve o estado consolidado.
        """
        v_id = village_id or account.current_village_id or 0
        html = await account.get_screen(
            screen="place",
            mode="scavenge",
            village_id=village_id,
            apply_jitter=True,
        )

        raw_options = parse_scavenge_options(html)
        options: List[ScavengeOption] = []
        active_count = 0
        min_return: Optional[int] = None

        for raw in raw_options:
            opt = ScavengeOption(
                id=raw["id"],
                name=raw["name"],
                description=raw["description"],
                is_unlocked=raw["is_unlocked"],
                is_locked=raw["is_locked"],
                is_scavenging=raw["is_scavenging"],
                unlock_cost=raw.get("unlock_cost", {"wood": 0, "stone": 0, "iron": 0}),
                unlock_time_seconds=raw.get("unlock_time_seconds", 0),
                time_remaining_seconds=raw.get("time_remaining_seconds", 0),
                return_time_iso=raw.get("return_time_iso"),
                loot_ratio=raw.get("loot_ratio", 0.10),
                duration_factor=raw.get("duration_factor", 1.0),
            )
            if opt.is_scavenging:
                active_count += 1
                if opt.time_remaining_seconds > 0:
                    if min_return is None or opt.time_remaining_seconds < min_return:
                        min_return = opt.time_remaining_seconds

            options.append(opt)

        troops = parse_scavenge_available_troops(html)

        return ScavengeState(
            village_id=v_id,
            options=options,
            available_troops=troops,
            active_expeditions_count=active_count,
            min_return_time_seconds=min_return,
        )

    async def unlock_scavenge_option(
        self,
        account: TribalAccount,
        option_id: int,
        village_id: Optional[int] = None,
    ) -> bool:
        """
        Envia ordem de desbloqueio para a categoria de coleta indicada (2, 3 ou 4).
        """
        if option_id <= 1 or option_id > 4:
            return False

        try:
            data = {
                "option_id": str(option_id),
                "action": "unlock",
                "h": account.csrf_token or "",
            }
            await account.post_action(
                screen="place",
                mode="scavenge",
                action="unlock",
                village_id=village_id,
                data=data,
                apply_jitter=True,
            )
            logger.info(f"[{account.world}] Ordem de desbloqueio da Coleta Categoria {option_id} enviada.")
            return True
        except Exception as e:
            logger.warning(f"[{account.world}] Falha ao desbloquear Coleta Categoria {option_id}: {e}")
            return False

    async def send_scavenge_squad(
        self,
        account: TribalAccount,
        option_id: int,
        units: Dict[str, int],
        village_id: Optional[int] = None,
    ) -> bool:
        """
        Envia um esquadrão de tropas para uma expedição de coleta indicada.
        """
        if not units or not any(v > 0 for v in units.values()):
            return False

        data: Dict[str, str] = {
            "option_id": str(option_id),
            "h": account.csrf_token or "",
        }
        for u_name, u_count in units.items():
            if u_count > 0:
                data[f"candidate_squad[unit_counts][{u_name}]"] = str(u_count)
                data[f"squad_requests[0][candidate_squad][unit_counts][{u_name}]"] = str(u_count)

        data["squad_requests[0][option_id]"] = str(option_id)
        data["squad_requests[0][use_premium]"] = "false"
        if village_id:
            data["squad_requests[0][village_id]"] = str(village_id)

        try:
            await account.post_action(
                screen="place",
                mode="scavenge",
                action="send_squad",
                village_id=village_id,
                data=data,
                apply_jitter=True,
            )
            logger.info(
                f"[{account.world}] 🌾 Expedição de Coleta Categoria {option_id} enviada com sucesso! "
                f"Tropas: {units}"
            )
            return True
        except Exception as e:
            logger.warning(f"[{account.world}] Erro ao enviar expedição de coleta Categoria {option_id}: {e}")
            return False

    async def execute_scavenge_cycle(
        self,
        account: TribalAccount,
        config: Any,
        village_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Executa uma ronda completa de análise e envio de coletas para a aldeia:
        1. Carrega o estado atual da coleta e tropas disponíveis.
        2. Tenta auto-desbloquear a próxima categoria se configurado e houver recursos.
        3. Calcula a distribuição proporcional ideal entre as opções prontas.
        4. Dispara as expedições para maximizar a colheita com retorno sincronizado.
        """
        v_id = village_id or account.current_village_id or 0
        state = await self.get_scavenge_state(account, village_id=v_id)

        ready = state.ready_options
        sent_expeditions = []

        # 1. Tentativa de auto-desbloqueio sequencial
        if getattr(config, "auto_unlock", True):
            for opt in state.options:
                if opt.is_locked and opt.unlock_cost:
                    # Verifica recursos da aldeia se disponíveis no game_data
                    vill_data = account.game_data.get("village", {}) if hasattr(account, "game_data") else {}
                    wood = vill_data.get("wood", 999999)
                    stone = vill_data.get("stone", 999999)
                    iron = vill_data.get("iron", 999999)
                    cost = opt.unlock_cost
                    if wood >= cost.get("wood", 0) and stone >= cost.get("stone", 0) and iron >= cost.get("iron", 0):
                        unlocked_ok = await self.unlock_scavenge_option(account, opt.id, village_id=v_id)
                        if unlocked_ok:
                            logger.info(f"[{account.world}] Categoria {opt.id} colocada em desbloqueio!")
                    break  # Apenas tenta desbloquear uma de cada vez

        # 2. Se houver opções prontas, distribui e envia
        if ready and state.available_troops:
            eligible = getattr(config, "eligible_units", ["spear", "sword", "axe", "archer", "light"])
            min_res = getattr(config, "min_reserved_units", {})
            dist = calculate_optimal_distribution(state.available_troops, ready, eligible, min_res)

            for opt_id, units in dist.items():
                ok = await self.send_scavenge_squad(account, opt_id, units, village_id=v_id)
                if ok:
                    sent_expeditions.append({"option_id": opt_id, "units": units})

        return {
            "status": "success",
            "village_id": v_id,
            "sent_expeditions": sent_expeditions,
            "active_expeditions_count": state.active_expeditions_count + len(sent_expeditions),
            "min_return_time_seconds": state.min_return_time_seconds,
        }

