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

from engine.actions.main_building import (
    DEFAULT_BUILD_PLAN,
    DEFAULT_BUILDING_TEMPLATE,
)

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
    """Configurações da rotina de Micro-Farming."""
    enabled: bool = False
    mode: str = "am_farm"              # 'am_farm' (Assistente de Farm), 'place' (Praça de Reunião) ou 'radar' (Radar de Bárbaras)
    template: str = "A"                # 'A' ou 'B'
    max_distance: float = 15.0         # Raio máximo de ataque em campos
    skip_losses: bool = True           # Ignorar aldeias com relatórios amarelos/vermelhos
    skip_wall: bool = True             # Ignorar aldeias com muralha > 0
    skip_active_targets: bool = True   # Não enviar ataques repetidos a bárbaras que já tenham ataques a caminho
    interval_minutes: float = 10.0     # Frequência de envio de ondas em minutos
    custom_targets: List[Tuple[int, int]] = field(default_factory=list)
    custom_troops: Dict[str, int] = field(default_factory=lambda: {"spear": 5, "spy": 1})
    use_map_scanner: bool = True       # Descoberta automática de bárbaras pelo mapa
    map_scan_radius: float = 15.0      # Raio de varredura em campos
    map_cache_ttl_hours: float = 12.0  # Validade da cache de aldeias bárbaras mapeadas


DEFAULT_ATTACK_MODEL: Dict[str, int] = {
    "spear": 0,
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


@dataclass
class ArbitrageConfig:
    """Configurações da rotina de Arbitragem Económica & Fila Sempre Ativa (Item 2.12)."""
    enabled: bool = False
    emergency_queue_seconds: float = 900.0  # 15 minutos (limiar de ativação de micro-lotes de emergência)
    min_military_batch: int = 2             # Quantidade mínima de tropas para micro-lotes
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
    category: str = "balanced"  # 'attack', 'defense', 'balanced'
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
class BotConfig:
    """Configuração global consolidada do bot."""
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
    villages: Dict[str, VillageConfig] = field(default_factory=dict)

    def get_active_build_plan(
        self,
        village_id: Optional[Any] = None,
        db: Optional[Any] = None,
    ) -> List[Tuple[str, int]]:
        """
        Retorna a lista de metas de construção com base no template configurado
        ou na categoria e template atribuídos à aldeia específica.
        Resolve modelos customizados a partir do SQLite (data/accounts.db) ou constantes.
        """
        if isinstance(self.building, dict):
            tmpl = str(self.building.get("template", "default_plan")).lower().strip()
            custom_plan = self.building.get("custom_plan")
        else:
            tmpl = self.building.template.lower().strip()
            custom_plan = self.building.custom_plan

        if village_id and str(village_id) in self.villages:
            v_cfg = self.villages[str(village_id)]
            if v_cfg.building_template:
                tmpl = v_cfg.building_template.lower().strip()
        elif isinstance(village_id, str) and not village_id.isdigit():
            # Permitir passar diretamente o nome do template no primeiro argumento
            tmpl = village_id.lower().strip()

        if tmpl in ("custom", "custom_plan") and custom_plan:
            return custom_plan
        elif tmpl in ("default", "default_plan", "standard"):
            return DEFAULT_BUILD_PLAN

        # Tenta resolver template customizado a partir do SQLite
        try:
            if db is None:
                from engine.storage.database import AccountsDatabase
                db = AccountsDatabase()
            db_tmpl = db.get_building_template(tmpl)
            if db_tmpl and db_tmpl.get("priority_list"):
                plan = []
                for item in db_tmpl["priority_list"]:
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
        Retorna as metas de recrutamento da aldeia conforme o seu modelo (Ataque/Defesa/Customizado).
        O bot segue o modelo definido para a categoria da aldeia na gestão de multi-aldeias.
        """
        from engine.core.models import VillageCategory, CATEGORY_RECRUITMENT_TARGETS
        cat = model_name or "defense"
        if not model_name and village_id and str(village_id) in self.villages:
            v_cfg = self.villages[str(village_id)]
            if v_cfg.recruitment_targets:
                return v_cfg.recruitment_targets
            cat = str(v_cfg.category).lower().strip() if v_cfg.category else "defense"
        elif not model_name and isinstance(village_id, str) and not village_id.isdigit():
            cat = village_id.lower().strip()

        # 1. Verifica no dicionário local em memória
        if hasattr(self.recruitment, "models") and cat in self.recruitment.models:
            return self.recruitment.models[cat]
        if cat == "attack" and hasattr(self.recruitment, "models") and "attack" in self.recruitment.models:
            return self.recruitment.models["attack"]
        if cat == "defense" and hasattr(self.recruitment, "models") and "defense" in self.recruitment.models:
            return self.recruitment.models["defense"]

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

        # 3. Fallback para enum/constantes de categoria
        try:
            v_cat = VillageCategory(cat)
            return CATEGORY_RECRUITMENT_TARGETS.get(v_cat, self.recruitment.targets)
        except Exception as e:
            logger.debug(f"Aviso ao converter categoria '{cat}' para VillageCategory: {e}")

        if hasattr(self.recruitment, "models") and "defense" in self.recruitment.models:
            return self.recruitment.models["defense"]
        return self.recruitment.targets

    def get_village_template(self, village_id: Optional[Any] = None) -> str:
        """
        Retorna o identificador do template de construção ativo para a aldeia
        (ex: 'DEFAULT_PLAN', 'CUSTOM').
        """
        tmpl = self.building.template.lower().strip()
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

    # 9. Carrega configurações e categorização de Aldeias
    v_data = data.get("villages", {})
    villages_config = {}
    if isinstance(v_data, dict):
        for vid, vinfo in v_data.items():
            if isinstance(vinfo, dict):
                villages_config[str(vid)] = VillageConfig(
                    category=str(vinfo.get("category", "balanced")).lower().strip(),
                    building_template=vinfo.get("building_template"),
                    recruitment_targets=vinfo.get("recruitment_targets"),
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
        villages=villages_config,
    )


def load_config(
    config_file: Optional[Union[str, Path]] = None,
    account_id: Optional[str] = None,
    db: Optional[Any] = None,
) -> BotConfig:
    """
    Carrega as configurações do bot com prioridade para a base de dados SQLite (data/accounts.db).
    Se config_file for fornecido (e existir como ficheiro), lê diretamente do ficheiro para compatibilidade e testes.
    Caso contrário, tenta resolver do SQLite (para account_id ou conta ativa).
    """
    # 1. Se config_file for um ficheiro existente no disco
    if config_file:
        config_path = Path(config_file)
        if config_path.exists():
            data: Dict[str, Any] = {}
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.debug(f"Configuração lida a partir de '{config_path.name}'.")
            except Exception as e:
                logger.debug(f"Erro ao ler '{config_path.name}': {e}")
            return parse_config_dict(data)

    # 2. Tenta carregar a partir do SQLite (data/accounts.db)
    try:
        if db is None:
            from engine.storage.database import AccountsDatabase
            db = AccountsDatabase()
        
        target_acc = None
        if account_id:
            target_acc = db.get_account(account_id)
        elif config_file and not str(config_file).endswith(".json"):
            target_acc = db.get_account(str(config_file))

        if not target_acc:
            target_acc = db.get_active_account()

        if target_acc:
            from engine.core.profile_manager import AccountProfile
            prof = AccountProfile.from_dict(target_acc)
            return prof.to_bot_config()
    except Exception as e:
        logger.debug(f"Aviso ao consultar configuração no SQLite: {e}")

    # 3. Fallback para config.json padrão se existir
    default_path = Path("config.json")
    if default_path.exists():
        try:
            with open(default_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return parse_config_dict(data)
        except Exception as e:
            logger.debug(f"Aviso ao ler fallback config.json: {e}")

    return parse_config_dict({})


def save_config_sid(
    sid: str,
    account_id: Optional[str] = None,
    config_path: Optional[Path] = None,
    db: Optional[Any] = None,
) -> bool:
    """Atualiza e persiste atomicamente o cookie 'sid' no SQLite da conta ativa e/ou ficheiro de configuração."""
    saved_any = False

    # 1. Se ficheiro for explicitamente fornecido, atualiza o ficheiro
    if config_path and Path(config_path).exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["sid"] = sid.strip()
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Cookie 'sid' atualizado no ficheiro '{Path(config_path).name}'.")
            saved_any = True
        except Exception as e:
            logger.error(f"Erro ao persistir sid no ficheiro: {e}")

    # 2. Persiste na base de dados SQLite
    try:
        if db is None:
            from engine.storage.database import AccountsDatabase
            db = AccountsDatabase()

        target_acc = db.get_account(account_id) if account_id else db.get_active_account()
        if target_acc:
            target_acc["session_cookie"] = sid.strip()
            target_acc["sid"] = sid.strip()
            db.save_account(target_acc)
            logger.info(f"Cookie 'sid' atualizado no SQLite para a conta '{target_acc.get('name')}'.")
            saved_any = True
    except Exception as e:
        logger.debug(f"Aviso ao persistir sid no SQLite: {e}")

    return saved_any


def _create_default_config_file(target_path: Path) -> None:
    """Cria um ficheiro config.json inicial documentado."""
    default_payload = {
        "world": "pt117",
        "sid": "",
        "building": {
            "_info": "Opções de template: 'default_plan' (padrão oficial) ou 'custom'",
            "template": "default_plan",
            "max_queue": 2,
            "interval_seconds": 75.0,
            "custom_plan": [
                ["wood", 1],
                ["stone", 1],
                ["iron", 1],
                ["main", 2],
                ["main", 3],
                ["barracks", 1],
                ["wood", 2],
                ["stone", 2],
                ["storage", 2],
                ["farm", 2],
                ["wood", 3],
                ["stone", 3],
                ["iron", 2]
            ]
        }
    }
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(default_payload, f, indent=2, ensure_ascii=False)
        logger.info(f"Ficheiro de exemplo '{target_path.name}' gerado na raiz do projeto.")
    except Exception as e:
        logger.debug(f"Não foi possível criar '{target_path.name}': {e}")
