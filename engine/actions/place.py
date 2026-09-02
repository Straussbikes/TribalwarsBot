"""
Tribal Wars Mobile Automation Engine - PlaceManager (screen=place)
Gestão da Praça de Reunião: leitura de tropas disponíveis, leitura de comandos em curso,
e envio de ordens militares (Ataques e Apoios) em 2 etapas seguras.
"""

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional, Tuple

from engine.core.account import TribalAccount
from engine.utils.parsers import (
    parse_available_units,
    parse_command_confirmation,
    parse_place_commands,
)

logger = logging.getLogger(__name__)


class UnitType:
    """Identificadores canónicos das 12 unidades do Tribal Wars."""
    SPEAR = "spear"        # Lanceiro
    SWORD = "sword"        # Espadachim
    AXE = "axe"            # Viking / Bárbaro
    ARCHER = "archer"      # Arqueiro
    SPY = "spy"            # Explorador
    LIGHT = "light"        # Cavalaria Leve
    MARCHER = "marcher"    # Arqueiro a Cavalo
    HEAVY = "heavy"        # Cavalaria Pesada
    RAM = "ram"            # Aríete
    CATAPULT = "catapult"  # Catapulta
    KNIGHT = "knight"      # Paladino
    SNOB = "snob"          # Nobre


# Capacidade de transporte de saque de cada unidade em recursos (madeira/argila/ferro)
CARRY_CAPACITY: Dict[str, int] = {
    UnitType.SPEAR: 25,
    UnitType.SWORD: 15,
    UnitType.AXE: 10,
    UnitType.ARCHER: 10,
    UnitType.SPY: 0,
    UnitType.LIGHT: 80,
    UnitType.MARCHER: 50,
    UnitType.HEAVY: 50,
    UnitType.RAM: 0,
    UnitType.CATAPULT: 0,
    UnitType.KNIGHT: 100,
    UnitType.SNOB: 0,
}

# Custo de população consumida pela fazenda por unidade
POP_COST: Dict[str, int] = {
    UnitType.SPEAR: 1,
    UnitType.SWORD: 1,
    UnitType.AXE: 1,
    UnitType.ARCHER: 1,
    UnitType.SPY: 2,
    UnitType.LIGHT: 4,
    UnitType.MARCHER: 5,
    UnitType.HEAVY: 6,
    UnitType.RAM: 5,
    UnitType.CATAPULT: 8,
    UnitType.KNIGHT: 10,
    UnitType.SNOB: 100,
}

# Velocidade de marcha base (minutos por campo no mundo de velocidade 1)
UNIT_SPEED_MIN_PER_FIELD: Dict[str, float] = {
    UnitType.SPY: 9.0,
    UnitType.LIGHT: 10.0,
    UnitType.KNIGHT: 10.0,
    UnitType.HEAVY: 11.0,
    UnitType.AXE: 18.0,
    UnitType.SPEAR: 18.0,
    UnitType.ARCHER: 18.0,
    UnitType.SWORD: 22.0,
    UnitType.RAM: 30.0,
    UnitType.CATAPULT: 30.0,
    UnitType.SNOB: 35.0,
}

UNIT_NAMES_PT: Dict[str, str] = {
    UnitType.SPEAR: "Lanceiro",
    UnitType.SWORD: "Espadachim",
    UnitType.AXE: "Viking",
    UnitType.ARCHER: "Arqueiro",
    UnitType.SPY: "Explorador",
    UnitType.LIGHT: "Cavalaria Leve",
    UnitType.MARCHER: "Arqueiro a Cavalo",
    UnitType.HEAVY: "Cavalaria Pesada",
    UnitType.RAM: "Aríete",
    UnitType.CATAPULT: "Catapulta",
    UnitType.KNIGHT: "Paladino",
    UnitType.SNOB: "Nobre",
}


@dataclass
class UnitsCount:
    """Contagem tipada de unidades na aldeia ou num comando militar."""
    spear: int = 0
    sword: int = 0
    axe: int = 0
    archer: int = 0
    spy: int = 0
    light: int = 0
    marcher: int = 0
    heavy: int = 0
    ram: int = 0
    catapult: int = 0
    knight: int = 0
    snob: int = 0

    @property
    def total(self) -> int:
        """Contagem numérica absoluta de tropas."""
        return sum(self.to_dict().values())

    def total_units(self) -> int:
        """Contagem numérica absoluta de tropas (alias)."""
        return self.total

    def carrying_capacity(self) -> int:
        """Capacidade total de carga de recursos do conjunto de tropas."""
        return sum(
            getattr(self, u, 0) * CARRY_CAPACITY.get(u, 0)
            for u in CARRY_CAPACITY
        )

    def total_population(self) -> int:
        """População total consumida pelo conjunto de tropas."""
        return sum(
            getattr(self, u, 0) * POP_COST.get(u, 0)
            for u in POP_COST
        )

    def to_summary_str(self) -> str:
        """Representação textual descritiva das tropas presentes (> 0)."""
        parts = [f"{getattr(self, u)} {u}" for u in CARRY_CAPACITY if getattr(self, u, 0) > 0]
        return ", ".join(parts) if parts else "0 tropas"

    def has_units(self, required: "UnitsCount") -> bool:
        """Verifica se existem tropas suficientes para satisfazer o pedido."""
        for u in CARRY_CAPACITY:
            if getattr(self, u, 0) < getattr(required, u, 0):
                return False
        return True

    def clamp_to_available(self, available: "UnitsCount") -> "UnitsCount":
        """Limita o pedido à quantidade máxima de tropas disponível na aldeia."""
        clamped = {}
        for u in CARRY_CAPACITY:
            wanted = getattr(self, u, 0)
            avail = getattr(available, u, 0)
            clamped[u] = max(0, min(wanted, avail))
        return UnitsCount.from_dict(clamped)

    def to_dict(self) -> Dict[str, int]:
        """Converte a contagem para dicionário manipulável por formulários HTTP."""
        return {
            UnitType.SPEAR: self.spear,
            UnitType.SWORD: self.sword,
            UnitType.AXE: self.axe,
            UnitType.ARCHER: self.archer,
            UnitType.SPY: self.spy,
            UnitType.LIGHT: self.light,
            UnitType.MARCHER: self.marcher,
            UnitType.HEAVY: self.heavy,
            UnitType.RAM: self.ram,
            UnitType.CATAPULT: self.catapult,
            UnitType.KNIGHT: self.knight,
            UnitType.SNOB: self.snob,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UnitsCount":
        """Instancia UnitsCount a partir de dicionário com tolerância a tipos."""
        kwargs = {}
        for u in CARRY_CAPACITY:
            val = d.get(u, 0)
            try:
                kwargs[u] = max(0, int(val))
            except (ValueError, TypeError):
                kwargs[u] = 0
        return cls(**kwargs)


@dataclass
class CommandMovement:
    """Representação de uma marcha de tropas listada na Praça de Reunião."""
    command_id: str
    movement_type: str  # 'attack', 'support', 'return'
    target_name: str
    target_coords: str
    timer_str: str = ""


@dataclass
class PlaceState:
    """Estado consolidado da Praça de Reunião de uma aldeia."""
    village_id: int
    units: UnitsCount = field(default_factory=UnitsCount)
    commands: List[CommandMovement] = field(default_factory=list)

    @property
    def total_home_units(self) -> int:
        return self.units.total_units()

    @property
    def total_carrying_capacity(self) -> int:
        return self.units.carrying_capacity()


class PlaceManager:
    """
    Controlador de automação da Praça de Reunião (screen=place).
    Permite ler tropas, inspecionar comandos e despachar ataques e apoios em 2 etapas.
    """

    async def get_state(
        self, account: TribalAccount, village_id: Optional[int] = None
    ) -> PlaceState:
        """
        Navega até o ecrã 'screen=place' e extrai as tropas disponíveis e movimentos em curso.
        """
        html = await account.get_screen("place", village_id=village_id)
        v_id = village_id or account.current_village_id or 0

        # 1. Parsing das tropas disponíveis
        raw_units = parse_available_units(html)
        units = UnitsCount.from_dict(raw_units)
        if v_id in account.villages:
            account.villages[v_id].troops = raw_units
        elif account.current_village:
            account.current_village.troops = raw_units

        # 2. Parsing de movimentos em curso
        raw_commands = parse_place_commands(html)
        commands: List[CommandMovement] = [
            CommandMovement(
                command_id=str(c.get("command_id", "")),
                movement_type=str(c.get("type", "command")),
                target_name=str(c.get("target_name", "")),
                target_coords=str(c.get("target_coords", "")),
                timer_str=str(c.get("timer_str", "")),
            )
            for c in raw_commands
        ]

        logger.info(
            f"[{account.world}] Praça de Reunião (Aldeia {v_id}): "
            f"{units.total_units()} tropas disponíveis (Capacidade: {units.carrying_capacity()}), "
            f"{len(commands)} comandos ativos."
        )
        return PlaceState(village_id=v_id, units=units, commands=commands)

    async def prepare_command(
        self,
        account: TribalAccount,
        target_x: int,
        target_y: int,
        units: UnitsCount,
        is_attack: bool = True,
        village_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Etapa 1: Envia o formulário de preparação de comando para 'screen=place&try=confirm'.
        Retorna o dicionário de confirmação com os tokens ocultos (ex.: 'chck', 'action_id').
        """
        v_id = village_id or account.current_village_id
        cmd_type_label = "Ataque" if is_attack else "Apoio"
        logger.info(
            f"[{account.world}] A preparar {cmd_type_label} para ({target_x}|{target_y}) "
            f"com {units.total_units()} tropas..."
        )

        post_data: Dict[str, Any] = units.to_dict()
        post_data["x"] = str(target_x)
        post_data["y"] = str(target_y)
        post_data["target_x"] = str(target_x)
        post_data["target_y"] = str(target_y)
        if is_attack:
            post_data["attack"] = "Ataque"
        else:
            post_data["support"] = "Apoio"

        try:
            html = await account.post_action(
                screen="place",
                action=None,
                data=post_data,
                village_id=v_id,
                extra_params={"try": "confirm"},
                apply_jitter=True,
            )
            confirm_data = parse_command_confirmation(html)
            if not confirm_data["success"]:
                logger.warning(
                    f"[{account.world}] Falha na preparação do comando: {confirm_data['error_message']}"
                )
            else:
                logger.info(
                    f"[{account.world}] Preparação concluída. Alvo: {confirm_data['target_name']} "
                    f"({confirm_data['target_coords']}) | Duração: {confirm_data['duration_str']}"
                )
            return confirm_data
        except Exception as e:
            logger.error(f"[{account.world}] Erro de rede ao preparar comando: {e}")
            return {"success": False, "error_message": str(e), "hidden_fields": {}}

    async def confirm_command(
        self,
        account: TribalAccount,
        confirmation_data: Dict[str, Any],
        village_id: Optional[int] = None,
    ) -> bool:
        """
        Etapa 2: Envia a requisição de confirmação final (action=command) utilizando os
        inputs ocultos extraídos da Etapa 1.
        """
        if not confirmation_data.get("success"):
            logger.warning("Tentativa de confirmar comando inválido ou com falha na Etapa 1.")
            return False

        hidden_fields = confirmation_data.get("hidden_fields", {})
        if not hidden_fields:
            logger.warning("Campos de confirmação ausentes na Etapa 2.")
            return False

        v_id = village_id or account.current_village_id
        logger.info(f"[{account.world}] A disparar confirmação final de comando militar...")

        try:
            html = await account.post_action(
                screen="place",
                action="command",
                data=hidden_fields,
                village_id=v_id,
                apply_jitter=True,
            )
            # Valida se não houve erro no envio final
            err = parse_command_confirmation(html)
            if not err["success"] and err["error_message"]:
                logger.error(f"[{account.world}] Erro na confirmação final: {err['error_message']}")
                return False

            target_name = confirmation_data.get("target_name") or "Alvo"
            target_coords = confirmation_data.get("target_coords") or ""
            dur = confirmation_data.get("duration_str") or "N/A"
            logger.info(f"[{account.world}] ✅ [COMANDO DESPACHADO] {target_name} ({target_coords}) | Duração: {dur}")
            return True
        except Exception as e:
            logger.error(f"[{account.world}] Falha ao confirmar comando final: {e}")
            return False

    async def send_command(
        self,
        account: TribalAccount,
        target_coords: Tuple[int, int],
        units: UnitsCount,
        is_attack: bool = True,
        village_id: Optional[int] = None,
        allow_partial: bool = False,
        adapt_missing_spies: bool = False,
    ) -> bool:
        """
        Fluxo completo de envio de comando militar (Etapa 1 + Etapa 2):
        1. Valida tropas disponíveis na aldeia de acordo com o modelo requisitado.
        2. Submete o formulário de preparação.
        3. Valida e despacha a confirmação final.
        """
        if isinstance(target_coords, str) and "|" in target_coords:
            tx_s, ty_s = target_coords.split("|", 1)
            target_x, target_y = int(tx_s), int(ty_s)
        else:
            target_x, target_y = target_coords

        # 1. Validação de tropas existentes
        state = await self.get_state(account, village_id=village_id)
        if allow_partial:
            troops_to_send = units.clamp_to_available(state.units)
            if troops_to_send.total_units() == 0:
                logger.warning(
                    f"[{account.world}] Nenhuma tropa disponível para envio parcial para ({target_x}|{target_y})."
                )
                return False
        else:
            missing = []
            for u in CARRY_CAPACITY:
                wanted = getattr(units, u, 0)
                avail = getattr(state.units, u, 0)
                if avail < wanted:
                    missing.append(f"{wanted - avail} {u}")

            troops_to_send = units
            # Apenas se expressamente configurado para adaptação de espião em early-game
            if adapt_missing_spies and missing == [f"{units.spy} spy"] and (state.units.spear > 0 or state.units.axe > 0 or state.units.light > 0):
                adapted_dict = units.to_dict()
                adapted_dict["spy"] = 0
                adapted_units = UnitsCount.from_dict(adapted_dict)
                if state.units.has_units(adapted_units) and adapted_units.total_units() > 0:
                    logger.info(
                        f"[{account.world}] Aldeia sem espiões (spy=0). A adaptar envio de tropas para ({target_x}|{target_y}): {adapted_units.to_summary_str()}."
                    )
                    troops_to_send = adapted_units
                    missing = []

            if missing:
                logger.warning(
                    f"[{account.world}] Tropas insuficientes para ({target_x}|{target_y}). "
                    f"Em falta: {', '.join(missing)}! "
                    f"[Requerido: {units.to_summary_str()} | Disponível na aldeia: {state.units.to_summary_str()}]."
                )
                return False

        # 2. Etapa 1 - Preparação
        prep = await self.prepare_command(
            account=account,
            target_x=target_x,
            target_y=target_y,
            units=troops_to_send,
            is_attack=is_attack,
            village_id=village_id,
        )
        if not prep.get("success"):
            return False

        # 3. Etapa 2 - Confirmação
        return await self.confirm_command(
            account=account,
            confirmation_data=prep,
            village_id=village_id,
        )

    # Alias para compatibilidade de API
    send_attack = send_command
