"""
Tribal Wars Mobile Automation Engine - Config & Settings Loader
Carrega definições a partir de 'config.json' e variáveis de ambiente com validações.
"""

from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class BuildingConfig:
    """Configurações da rotina do Edifício Principal."""
    enabled: bool = True
    template: str = "default_plan"     # Modelo padrão único ou 'custom'
    max_queue: int = 2                 # Máximo de construções sem custos adicionais
    interval_seconds: float = 75.0     # Intervalo médio entre verificações
    custom_plan: List[Tuple[str, int]] = field(default_factory=list)


@dataclass
class FarmConfig:
    """Configurações da rotina de Micro-Farming e Assistente de Saque."""
    enabled: bool = True
    mode: str = "am_farm"              # 'am_farm' (Assistente de Farm), 'place' (Praça de Reunião) ou 'radar' (Radar de Bárbaras)
    template: str = "A"                # 'A' ou 'B'
    default_template: str = "A"        # 'A' ou 'B' (alias)
    max_distance: float = 25.0         # Raio máximo de ataque em campos (X campos)
    scan_all_radius_barbarians: bool = True  # Varre ativamente e ataca TODAS as bárbaras no raio
    bootstrap_unlisted_barbarians: bool = True  # Dispara ataque inicial via Praça para incluir bárbaras novas no AM Farm
    avoid_concurrent_attacks: bool = True  # Evita enviar múltiplos ataques para a mesma bárbara em trânsito
    stop_on_losses: bool = True        # Ignorar aldeias bárbaras com perdas (amarelas/vermelhas)
    skip_losses: bool = True           # Alias compatível
    skip_wall: bool = True             # Ignorar aldeias com muralha > 0
    skip_active_targets: bool = True   # Alias compatível
    min_interval_seconds: int = 120    # Intervalo mínimo entre ciclos de varredura (aliviado anti-timeout)
    max_interval_seconds: int = 240    # Intervalo máximo entre ciclos de varredura (aliviado anti-timeout)
    min_delay_per_attack_ms: int = 500 # Atraso mínimo entre ataques individuais (aliviado anti-timeout)
    max_delay_per_attack_ms: int = 1100 # Atraso máximo entre ataques individuais (aliviado anti-timeout)
    interval_minutes: float = 10.0     # Frequência de envio de ondas em minutos (compatibilidade)
    custom_targets: List[Any] = field(default_factory=list)
    custom_troops: Dict[str, int] = field(default_factory=lambda: {"spear": 5, "spy": 1})
    template_a_troops: Dict[str, int] = field(default_factory=lambda: {"spear": 0, "sword": 0, "axe": 0, "archer": 0, "spy": 0, "light": 5, "marcher": 0, "heavy": 0, "ram": 0, "catapult": 0, "knight": 0, "snob": 0})
    template_b_troops: Dict[str, int] = field(default_factory=lambda: {"spear": 0, "sword": 0, "axe": 0, "archer": 0, "spy": 0, "light": 10, "marcher": 0, "heavy": 0, "ram": 0, "catapult": 0, "knight": 0, "snob": 0})
    use_map_scanner: bool = True       # Descoberta automática de bárbaras pelo mapa
    map_scan_radius: float = 25.0      # Raio de varredura em campos
    map_cache_ttl_hours: float = 12.0  # Validade da cache de aldeias bárbaras mapeadas

    def __post_init__(self):
        if self.template != "A" and self.default_template == "A":
            self.default_template = self.template
        elif self.default_template != "A" and self.template == "A":
            self.template = self.default_template
        if not self.skip_losses:
            self.stop_on_losses = False
        if not self.skip_active_targets:
            self.avoid_concurrent_attacks = False


DEFAULT_ATTACK_MODEL: Dict[str, int] = {
    "spear": 30,
    "sword": 0,
    "axe": 6000,
    "archer": 0,
    "spy": 50,
    "light": 3000,
    "marcher": 0,
    "heavy": 0,
    "ram": 250,
    "catapult": 10,
}

DEFAULT_DEFENSE_MODEL: Dict[str, int] = {
    "spear": 7000,
    "sword": 7000,
    "axe": 0,
    "archer": 0,
    "spy": 50,
    "light": 0,
    "marcher": 0,
    "heavy": 1000,
    "ram": 0,
    "catapult": 0,
}


@dataclass
class RecruitmentConfig:
    """Configurações da rotina de Recrutamento Militar e Modelos de Tropas (Ataque/Defesa)."""
    enabled: bool = False
    models: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: {
            "attack": DEFAULT_ATTACK_MODEL.copy(),
            "defense": DEFAULT_DEFENSE_MODEL.copy(),
        }
    )
    targets: Dict[str, int] = field(default_factory=lambda: {"spear": 50, "sword": 50, "axe": 50})
    batch_sizes: Dict[str, int] = field(
        default_factory=lambda: {
            "spear": 5,
            "sword": 5,
            "axe": 5,
            "archer": 5,
            "spy": 5,
            "light": 5,
            "marcher": 5,
            "heavy": 5,
            "ram": 5,
            "catapult": 5,
        }
    )
    min_free_pop: int = 10
    interval_minutes: float = 5.0
    max_queue_elements: int = 3


@dataclass
class ArbitrageConfig:
    """Configurações da rotina de Arbitragem Económica & Fila Sempre Ativa (Item 2.12)."""
    enabled: bool = False
    emergency_queue_seconds: float = 900.0  # 15 minutos (limiar de ativação de micro-lotes de emergência)
    min_military_batch: int = 5             # Quantidade mínima de tropas para micro-lotes
    interval_seconds: float = 60.0          # Intervalo de avaliação da concorrência


@dataclass
class AuthConfig:
    """Configurações de autenticação automática e renovação de sessão."""
    username: str = ""
    password: str = ""
    auto_login: bool = False
    keep_alive: bool = True
    keep_alive_interval_minutes: float = 15.0


@dataclass
class QuestConfig:
    """Configurações da rotina de Missões, Bónus Diário e Inventário (uso de inventário apenas manual)."""
    enabled: bool = True
    auto_claim_quests: bool = True
    auto_daily_bonus: bool = True
    safe_storage_margin: float = 0.95  # Não recolher se ultrapassar 95% da capacidade do armazém
    interval_minutes: float = 30.0


@dataclass
class VillageConfig:
    """Configurações de categorização e templates de uma aldeia específica."""
    category: str = "attack"  # Estritamente 'attack' (Ataque) ou 'defense' (Defesa)
    building_template: Optional[str] = None
    recruitment_targets: Optional[Dict[str, int]] = None


@dataclass
class MarketConfig:
    """Configurações da rotina do Mercado e Balanceamento de Recursos."""
    enabled: bool = False
    interval_minutes: float = 30.0
    auto_balance: bool = True           # Balanceamento automático entre aldeias da conta
    reserve_margin: float = 0.20        # Margem de reserva mínima na doadora (20% do armazém)
    overflow_threshold: float = 0.90    # Considera doadora urgente se recursos >= 90% do armazém
    deficit_threshold: float = 0.30     # Considera recetora se recursos <= 30% do armazém
    min_transfer_amount: int = 1000     # Mínimo para transferência (1 mercador = 1000 recursos)
    auto_trade_offers: bool = False     # Criar ofertas 1:1 no mercado próprio para trocas de excedente local
    max_merchant_ratio: float = 0.80    # Percentagem máxima de mercadores livres a comprometer por ciclo

    @property
    def auto_balance_enabled(self) -> bool:
        return self.auto_balance

    @auto_balance_enabled.setter
    def auto_balance_enabled(self, val: bool) -> None:
        self.auto_balance = val


@dataclass
class DefenseConfig:
    """Configurações da rotina de Defesa, Alarme de Ataques e Auto-Dodge (Item 2.8)."""
    enabled: bool = True               # Monitorização em tempo real de incomings
    auto_dodge_enabled: bool = False   # Desvio automático de tropas antes do impacto
    dodge_lead_time_seconds: int = 30  # Antecedência do envio de esquiva (segundos antes do impacto)
    dodge_cancel_delay_seconds: int = 5 # Atraso pós-impacto para cancelamento (segundos após impacto)
    escape_coords: Optional[str] = None # Coordenadas de fuga (None = bárbara mais próxima)
    auto_dodge_all_units: bool = True  # True: todas as tropas; False: apenas ofensivas
    alarm_sound_enabled: bool = True   # Alarme sonoro em caso de ataque a chegar
    check_interval_seconds: float = 45.0 # Intervalo do ciclo de verificação de incomings (aliviado anti-timeout)


@dataclass
class CombatConfig:
    """Configurações de Táticas de Combate & Sincronização ao Milissegundo (Item 2.9)."""
    noble_train_gap_ms: int = 100         # Intervalo entre ataques no comboio (50ms a 250ms)
    failsafe_enabled: bool = True          # Cancelamento automático se a dispersão exceder o limiar
    failsafe_max_spread_ms: int = 400      # Dispersão máxima aceitável entre 1º e último ataque (ms)
    default_noble_escort: Dict[str, int] = field(default_factory=lambda: {"axe": 50, "light": 20})
    snipe_tolerance_ms: int = 150          # Tolerância de intercalação de sniper (ms)
    clock_sync_interval_seconds: float = 60.0 # Intervalo de ressincronização com o servidor


@dataclass
class ScavengeConfig:
    """Configurações da Coleta de Recursos / Scavenging (Ponto 2.4 & Fase 4)."""
    enabled: bool = False
    auto_unlock: bool = True
    eligible_units: List[str] = field(default_factory=lambda: ["spear", "sword", "axe", "archer", "light"])
    min_reserved_units: Dict[str, int] = field(default_factory=lambda: {"spear": 10, "sword": 10})
    check_interval_seconds: float = 300.0


@dataclass
class SnobConfig:
    """Configurações da Academia & Cunha de Moedas (Ponto 2.6 & Fase 4)."""
    auto_mint_enabled: bool = False
    storage_threshold_percent: float = 85.0  # Cunhar moedas se armazém >= 85%
    reserve_wood: int = 50000
    reserve_stone: int = 50000
    reserve_iron: int = 50000
    auto_recruit_nobles: bool = False
    max_nobles: int = 4


@dataclass
class BotConfig:
    """Configurações globais consolidadas do Bot."""
    world: str = "pt117"
    sid: str = ""
    domain: str = "tribalwars.com.pt"
    proxy: Optional[str] = None
    auth: AuthConfig = field(default_factory=AuthConfig)
    building: BuildingConfig = field(default_factory=BuildingConfig)
    farm: FarmConfig = field(default_factory=FarmConfig)
    recruitment: RecruitmentConfig = field(default_factory=RecruitmentConfig)
    arbitrage: ArbitrageConfig = field(default_factory=ArbitrageConfig)
    quest: QuestConfig = field(default_factory=QuestConfig)
    market: MarketConfig = field(default_factory=MarketConfig)
    defense: DefenseConfig = field(default_factory=DefenseConfig)
    combat: CombatConfig = field(default_factory=CombatConfig)
    scavenge: ScavengeConfig = field(default_factory=ScavengeConfig)
    snob: SnobConfig = field(default_factory=SnobConfig)
    villages: Dict[str, VillageConfig] = field(default_factory=dict)

    def get_active_build_plan(
        self,
        template_name: Optional[str] = None,
        village_id: Optional[Any] = None,
        db: Optional[Any] = None,
    ) -> List[Tuple[str, int]]:
        """
        Retorna o plano de construção correspondente ao template ativo ou customizado.
        Prioridade 1: Modelo Padrão Oficial 'default_plan' (268 passos).
        Prioridade 2: Tabela SQLite 'building_templates'.
        """
        tmpl = template_name or self.building.template
        if not template_name and village_id and str(village_id) in self.villages:
            v_cfg = self.villages[str(village_id)]
            if v_cfg.building_template:
                tmpl = v_cfg.building_template
            elif v_cfg.category:
                from engine.core.models import VillageCategory, CATEGORY_BUILDING_TEMPLATES
                v_cat = VillageCategory.DEFENSE if "def" in str(v_cfg.category).lower() else VillageCategory.ATTACK
                tmpl = CATEGORY_BUILDING_TEMPLATES.get(v_cat, "default_plan")

        tmpl = tmpl.lower().strip()
        custom_plan = getattr(self.building, "custom_plan", None)
        from engine.actions.main_building import DEFAULT_BUILD_PLAN

        if tmpl in ("custom", "custom_plan") and custom_plan:
            return custom_plan

        from engine.config.templates import DEFAULT_BUILD_TEMPLATES
        for official_t in DEFAULT_BUILD_TEMPLATES:
            if official_t.get("id", "").lower() == tmpl:
                return official_t.get("priority_list", DEFAULT_BUILD_PLAN)

        if tmpl in ("default_plan", "default", "ee02gd68de", "rush_resources", "balanced", "military_rush"):
            return DEFAULT_BUILD_PLAN

        try:
            if db is None:
                from engine.storage.database import AccountsDatabase
                db = AccountsDatabase()
            db_template = db.get_building_template(tmpl)
            if db_template:
                steps_data = db_template.get("steps") or db_template.get("priority_list") or []
                plan = []
                for item in steps_data:
                    if isinstance(item, (list, tuple)) and len(item) == 2:
                        plan.append((str(item[0]).strip().lower(), int(item[1])))
                if plan:
                    return plan
        except Exception as e:
            logger.debug(f"Aviso ao consultar template '{tmpl}' no SQLite: {e}")

        return custom_plan if custom_plan else DEFAULT_BUILD_PLAN

    def get_village_recruitment_targets(
        self,
        village_id: Optional[Any] = None,
        model_name: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> Dict[str, int]:
        """
        Retorna as metas de recrutamento da aldeia conforme o seu modelo (Ataque ou Defesa).
        - Aldeia de Ataque -> Modelo de recrutamento de Ataque ('attack')
        - Aldeia de Defesa -> Modelo de recrutamento de Defesa ('defense')
        """
        from engine.core.models import VillageCategory, CATEGORY_RECRUITMENT_TARGETS
        cat = model_name or "attack"
        if not model_name and village_id and str(village_id) in self.villages:
            v_cfg = self.villages[str(village_id)]
            if v_cfg.recruitment_targets:
                return v_cfg.recruitment_targets
            cat = str(v_cfg.category).lower().strip() if v_cfg.category else "attack"
        elif not model_name and isinstance(village_id, str) and not village_id.isdigit():
            cat = village_id.lower().strip()

        # 1. Verifica se existe o modelo no dicionário de modelos em memória
        if hasattr(self.recruitment, "models") and cat in self.recruitment.models:
            return self.recruitment.models[cat]

        # 2. Tenta consultar modelo correspondente no SQLite
        try:
            if db is None:
                from engine.storage.database import AccountsDatabase
                db = AccountsDatabase()
            db_model = db.get_recruitment_model(cat)
            if db_model and db_model.get("units"):
                return {str(k): int(v) for k, v in db_model["units"].items()}
        except Exception as e:
            logger.debug(f"Aviso ao consultar modelo de recrutamento no SQLite para categoria '{cat}': {e}")

        # 3. Normalização estrita para 'defense' ou 'attack'
        norm_cat = "defense" if "def" in cat else "attack"
        if hasattr(self.recruitment, "models") and norm_cat in self.recruitment.models:
            return self.recruitment.models[norm_cat]

        # 4. Fallback para arquétipos padrão de categoria
        v_cat = VillageCategory.DEFENSE if norm_cat == "defense" else VillageCategory.ATTACK
        return CATEGORY_RECRUITMENT_TARGETS.get(v_cat, self.recruitment.targets)

    def get_village_template(self, village_id: Optional[Any] = None) -> str:
        """
        Retorna o identificador do template de construção ativo para a aldeia
        (ex: 'DEFAULT_PLAN', 'CUSTOM').
        """
        tmpl = (self.building.template or "default_plan").lower().strip()
        if village_id and str(village_id) in self.villages:
            v_cfg = self.villages[str(village_id)]
            if v_cfg.building_template:
                tmpl = v_cfg.building_template.lower().strip()
        return tmpl.upper()

    @property
    def effective_building_plan(self) -> List[Tuple[str, int]]:
        """Propriedade de compatibilidade que retorna o plano ativo."""
        return self.get_active_build_plan()

    def to_dict(self) -> Dict[str, Any]:
        """Converte as configurações para um dicionário serializável."""
        return {
            "world": self.world,
            "sid": self.sid,
            "domain": self.domain,
            "proxy": self.proxy,
            "auth": asdict(self.auth) if hasattr(self.auth, "__dataclass_fields__") else self.auth,
            "building": asdict(self.building) if hasattr(self.building, "__dataclass_fields__") else self.building,
            "farm": asdict(self.farm) if hasattr(self.farm, "__dataclass_fields__") else self.farm,
            "recruitment": asdict(self.recruitment) if hasattr(self.recruitment, "__dataclass_fields__") else self.recruitment,
            "arbitrage": asdict(self.arbitrage) if hasattr(self.arbitrage, "__dataclass_fields__") else self.arbitrage,
            "quest": asdict(self.quest) if hasattr(self.quest, "__dataclass_fields__") else self.quest,
            "market": asdict(self.market) if hasattr(self.market, "__dataclass_fields__") else self.market,
            "defense": asdict(self.defense) if hasattr(self.defense, "__dataclass_fields__") else self.defense,
            "combat": asdict(self.combat) if hasattr(self.combat, "__dataclass_fields__") else self.combat,
            "scavenge": asdict(self.scavenge) if hasattr(self.scavenge, "__dataclass_fields__") else self.scavenge,
            "snob": asdict(self.snob) if hasattr(self.snob, "__dataclass_fields__") else self.snob,
            "villages": {k: asdict(v) if hasattr(v, "__dataclass_fields__") else v for k, v in self.villages.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotConfig":
        """Reconstrói uma instância BotConfig a partir de um dicionário."""
        return parse_config_dict(data)


def parse_config_dict(data: Dict[str, Any]) -> BotConfig:
    """Faz o parse estruturado de um dicionário de configuração para instâncias tipadas."""
    env_world = (os.getenv("TW_WORLD") or "").strip()
    env_sid = (os.getenv("TW_SID") or "").strip()
    env_proxy = (os.getenv("TW_PROXY") or "").strip()

    world = env_world if env_world else data.get("world", "pt117")
    sid = env_sid if env_sid else data.get("sid", "")
    domain = data.get("domain", "tribalwars.com.pt")
    proxy = env_proxy if env_proxy else data.get("proxy")

    # 2. Carrega configurações do Edifício Principal
    b_data = data.get("building", {})
    enabled = bool(b_data.get("enabled", True))
    template = b_data.get("template", "default_plan")
    max_queue = int(b_data.get("max_queue", 2))
    interval_seconds = float(b_data.get("interval_seconds", 75.0))

    raw_plan = b_data.get("custom_plan", [])
    custom_plan = []
    if isinstance(raw_plan, list):
        for item in raw_plan:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                b_name = str(item[0]).strip().lower()
                try:
                    b_lvl = int(item[1])
                    custom_plan.append((b_name, b_lvl))
                except (ValueError, TypeError):
                    continue

    building_config = BuildingConfig(
        enabled=enabled,
        template=template,
        max_queue=max_queue,
        interval_seconds=interval_seconds,
        custom_plan=custom_plan,
    )

    # 3. Carrega configurações do Farm
    f_data = data.get("farm", {})
    f_enabled = bool(f_data.get("enabled", True))
    f_mode = str(f_data.get("mode", "am_farm")).lower().strip()
    f_template = str(f_data.get("template", "A")).upper().strip()
    f_max_dist = float(f_data.get("max_distance", 15.0))
    f_skip_losses = bool(f_data.get("skip_losses", True))
    f_skip_wall = bool(f_data.get("skip_wall", True))
    f_interval = float(f_data.get("interval_minutes", 10.0))
    f_min_interval = int(f_data.get("min_interval_seconds", 120))
    f_max_interval = int(f_data.get("max_interval_seconds", 240))
    f_min_delay = int(f_data.get("min_delay_per_attack_ms", 500))
    f_max_delay = int(f_data.get("max_delay_per_attack_ms", 1100))

    raw_targets = f_data.get("custom_targets", [])
    custom_targets = []
    if isinstance(raw_targets, list):
        for item in raw_targets:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                try:
                    tx, ty = int(item[0]), int(item[1])
                    custom_targets.append((tx, ty))
                except (ValueError, TypeError):
                    continue

    raw_troops = f_data.get("custom_troops", {"spear": 5, "spy": 1})
    custom_troops = {str(k): int(v) for k, v in raw_troops.items()} if isinstance(raw_troops, dict) else {}
    use_map_scanner = bool(f_data.get("use_map_scanner", True))
    map_scan_radius = float(f_data.get("map_scan_radius", 15.0))
    map_cache_ttl_hours = float(f_data.get("map_cache_ttl_hours", 12.0))

    farm_config = FarmConfig(
        enabled=f_enabled,
        mode=f_mode,
        template=f_template,
        max_distance=f_max_dist,
        skip_losses=f_skip_losses,
        skip_wall=f_skip_wall,
        min_interval_seconds=f_min_interval,
        max_interval_seconds=f_max_interval,
        min_delay_per_attack_ms=f_min_delay,
        max_delay_per_attack_ms=f_max_delay,
        interval_minutes=f_interval,
        custom_targets=custom_targets,
        custom_troops=custom_troops,
        use_map_scanner=use_map_scanner,
        map_scan_radius=map_scan_radius,
        map_cache_ttl_hours=map_cache_ttl_hours,
    )

    # 4. Carrega configurações de Recrutamento
    r_data = data.get("recruitment", {})
    r_enabled = bool(r_data.get("enabled", False))
    r_interval = float(r_data.get("interval_minutes", 5.0))
    r_min_pop = int(r_data.get("min_free_pop", 10))
    r_max_queue = int(r_data.get("max_queue_elements", 3))

    models_data = r_data.get("models", {})
    parsed_models = {}
    if isinstance(models_data, dict):
        for m_name, m_targets in models_data.items():
            if isinstance(m_targets, dict):
                parsed_models[str(m_name)] = {str(k): int(v) for k, v in m_targets.items()}

    batch_data = r_data.get("batch_sizes", {})
    parsed_batches = {}
    if isinstance(batch_data, dict):
        parsed_batches = {str(k): int(v) for k, v in batch_data.items()}

    targets_data = r_data.get("targets", {})
    parsed_targets = {str(k): int(v) for k, v in targets_data.items()} if isinstance(targets_data, dict) else {}

    recruitment_config = RecruitmentConfig(
        enabled=r_enabled,
        models=parsed_models or {"attack": DEFAULT_ATTACK_MODEL.copy(), "defense": DEFAULT_DEFENSE_MODEL.copy()},
        targets=parsed_targets or {"spear": 50, "sword": 50, "axe": 50},
        batch_sizes=parsed_batches or {
            "spear": 5, "sword": 5, "axe": 5, "archer": 5, "spy": 5,
            "light": 5, "marcher": 5, "heavy": 5, "ram": 5, "catapult": 5
        },
        min_free_pop=r_min_pop,
        interval_minutes=r_interval,
        max_queue_elements=r_max_queue,
    )

    # 5. Carrega configurações de Arbitragem Económica
    arb_data = data.get("arbitrage", {})
    arbitrage_config = ArbitrageConfig(
        enabled=bool(arb_data.get("enabled", False)),
        emergency_queue_seconds=float(arb_data.get("emergency_queue_seconds", 900.0)),
        min_military_batch=int(arb_data.get("min_military_batch", 2)),
        interval_seconds=float(arb_data.get("interval_seconds", 60.0)),
    )

    # 6. Carrega configurações de Autenticação
    auth_data = data.get("auth", {})
    auth_config = AuthConfig(
        username=str(auth_data.get("username", "")),
        password=str(auth_data.get("password", "")),
        auto_login=bool(auth_data.get("auto_login", False)),
        keep_alive=bool(auth_data.get("keep_alive", True)),
        keep_alive_interval_minutes=float(auth_data.get("keep_alive_interval_minutes", 15.0)),
    )

    # 7. Carrega configurações de Missões
    q_data = data.get("quest", {})
    quest_config = QuestConfig(
        enabled=bool(q_data.get("enabled", True)),
        auto_claim_quests=bool(q_data.get("auto_claim_quests", True)),
        auto_daily_bonus=bool(q_data.get("auto_daily_bonus", True)),
        safe_storage_margin=float(q_data.get("safe_storage_margin", 0.95)),
        interval_minutes=float(q_data.get("interval_minutes", 30.0)),
    )

    # 8. Carrega configurações do Mercado
    m_data = data.get("market", {})
    auto_bal = m_data.get("auto_balance", m_data.get("auto_balance_enabled", True))
    res_margin = m_data.get("reserve_margin", m_data.get("reserve_margin_percent", 0.20))
    max_merch = m_data.get("max_merchant_ratio", m_data.get("max_merchants_percent", 0.80))
    market_config = MarketConfig(
        enabled=bool(m_data.get("enabled", False)),
        interval_minutes=float(m_data.get("interval_minutes", 30.0)),
        auto_balance=bool(auto_bal),
        reserve_margin=float(res_margin),
        overflow_threshold=float(m_data.get("overflow_threshold", 0.90)),
        deficit_threshold=float(m_data.get("deficit_threshold", 0.30)),
        min_transfer_amount=int(m_data.get("min_transfer_amount", 1000)),
        auto_trade_offers=bool(m_data.get("auto_trade_offers", False)),
        max_merchant_ratio=float(max_merch),
    )

    # 9. Carrega configurações e categorização de Aldeias (estritamente 'attack' ou 'defense')
    v_data = data.get("villages", {})
    villages_config = {}
    if isinstance(v_data, dict):
        for vid, vinfo in v_data.items():
            if isinstance(vinfo, dict):
                raw_cat = str(vinfo.get("category", "attack")).lower().strip()
                cat = "defense" if "def" in raw_cat else "attack"
                villages_config[str(vid)] = VillageConfig(
                    category=cat,
                    building_template=vinfo.get("building_template"),
                    recruitment_targets=vinfo.get("recruitment_targets"),
                )

    # 10. Carrega configurações de Defesa e Alarme
    def_data = data.get("defense", {})
    defense_config = DefenseConfig(
        enabled=bool(def_data.get("enabled", True)),
        auto_dodge_enabled=bool(def_data.get("auto_dodge_enabled", False)),
        dodge_lead_time_seconds=int(def_data.get("dodge_lead_time_seconds", 30)),
        dodge_cancel_delay_seconds=int(def_data.get("dodge_cancel_delay_seconds", 5)),
        escape_coords=def_data.get("escape_coords"),
        auto_dodge_all_units=bool(def_data.get("auto_dodge_all_units", True)),
        alarm_sound_enabled=bool(def_data.get("alarm_sound_enabled", True)),
        check_interval_seconds=float(def_data.get("check_interval_seconds", 45.0)),
    )

    # 8. Configurações de Combate & Sincronização ao Milissegundo (Item 2.9)
    cmb_data = data.get("combat", {})
    combat_config = CombatConfig(
        noble_train_gap_ms=int(cmb_data.get("noble_train_gap_ms", 100)),
        failsafe_enabled=bool(cmb_data.get("failsafe_enabled", True)),
        failsafe_max_spread_ms=int(cmb_data.get("failsafe_max_spread_ms", 400)),
        default_noble_escort=cmb_data.get("default_noble_escort", {"axe": 50, "light": 20}),
        snipe_tolerance_ms=int(cmb_data.get("snipe_tolerance_ms", 150)),
        clock_sync_interval_seconds=float(cmb_data.get("clock_sync_interval_seconds", 60.0)),
    )

    # 9. Configurações de Coleta de Recursos (Scavenging)
    scv_data = data.get("scavenge", {})
    scavenge_config = ScavengeConfig(
        enabled=bool(scv_data.get("enabled", False)),
        auto_unlock=bool(scv_data.get("auto_unlock", True)),
        eligible_units=scv_data.get("eligible_units", ["spear", "sword", "axe", "archer", "light"]),
        min_reserved_units=scv_data.get("min_reserved_units", {"spear": 10, "sword": 10}),
        check_interval_seconds=float(scv_data.get("check_interval_seconds", 300.0)),
    )

    # 10. Configurações de Academia & Moedas
    snb_data = data.get("snob", {})
    snob_config = SnobConfig(
        auto_mint_enabled=bool(snb_data.get("auto_mint_enabled", False)),
        storage_threshold_percent=float(snb_data.get("storage_threshold_percent", 85.0)),
        reserve_wood=int(snb_data.get("reserve_wood", 50000)),
        reserve_stone=int(snb_data.get("reserve_stone", 50000)),
        reserve_iron=int(snb_data.get("reserve_iron", 50000)),
        auto_recruit_nobles=bool(snb_data.get("auto_recruit_nobles", False)),
        max_nobles=int(snb_data.get("max_nobles", 4)),
    )

    return BotConfig(
        world=world.strip().lower(),
        sid=sid.strip(),
        domain=domain.strip().lower(),
        proxy=proxy,
        auth=auth_config,
        building=building_config,
        farm=farm_config,
        recruitment=recruitment_config,
        arbitrage=arbitrage_config,
        quest=quest_config,
        market=market_config,
        defense=defense_config,
        combat=combat_config,
        scavenge=scavenge_config,
        snob=snob_config,
        villages=villages_config,
    )


def load_config(
    data: Optional[Union[Dict[str, Any], str, Path]] = None,
    account_id: Optional[str] = None,
    db: Optional[Any] = None,
) -> BotConfig:
    """
    Carrega as configurações do bot de forma 100% cloud-native e em memória.
    Elimina qualquer dependência de persistência em disco legada (config.json ou SQLite).
    """
    if isinstance(data, dict):
        return parse_config_dict(data)

    if data and isinstance(data, (str, Path)):
        p = Path(data)
        if p.exists() and p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    content = json.load(f)
                return parse_config_dict(content)
            except Exception as e:
                logger.debug(f"Aviso ao carregar dados: {e}")

    env_data: Dict[str, Any] = {}
    if os.environ.get("TW_WORLD"):
        env_data["world"] = os.environ.get("TW_WORLD")
    if os.environ.get("TW_SID"):
        env_data["sid"] = os.environ.get("TW_SID")
    if os.environ.get("TW_DOMAIN"):
        env_data["domain"] = os.environ.get("TW_DOMAIN")
    if os.environ.get("TW_PROXY"):
        env_data["proxy"] = os.environ.get("TW_PROXY")

    return parse_config_dict(env_data)


def save_config_sid(
    sid: str,
    account_id: Optional[str] = None,
    config_path: Optional[Path] = None,
    db: Optional[Any] = None,
) -> bool:
    """Atualização em runtime. Se config_path ou db forem explicitamente fornecidos (testes), atualiza o alvo."""
    if config_path and Path(config_path).exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["sid"] = sid.strip()
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    if db is not None:
        try:
            target_acc = db.get_account(account_id) if account_id else db.get_active_account()
            if target_acc:
                target_acc["session_cookie"] = sid.strip()
                target_acc["sid"] = sid.strip()
                db.save_account(target_acc)
                return True
        except Exception:
            return False

    return True

