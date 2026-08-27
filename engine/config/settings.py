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
    BALANCED_TEMPLATE,
    MILITARY_RUSH_TEMPLATE,
    RUSH_RESOURCES_TEMPLATE,
)

logger = logging.getLogger(__name__)


@dataclass
class BuildingConfig:
    """Configurações da rotina do Edifício Principal."""
    template: str = "rush_resources"  # 'rush_resources', 'balanced', 'military_rush', 'custom'
    max_queue: int = 2                 # Máximo de construções sem custos adicionais
    interval_seconds: float = 75.0     # Intervalo médio entre verificações
    custom_plan: List[Tuple[str, int]] = field(default_factory=list)


@dataclass
class FarmConfig:
    """Configurações da rotina de Micro-Farming."""
    enabled: bool = False
    mode: str = "am_farm"              # 'am_farm' (Assistente de Farm) ou 'place' (Praça de Reunião)
    template: str = "A"                # 'A' ou 'B'
    max_distance: float = 15.0         # Raio máximo de ataque em campos
    skip_losses: bool = True           # Ignorar aldeias com relatórios amarelos/vermelhos
    skip_wall: bool = True             # Ignorar aldeias com muralha > 0
    interval_minutes: float = 10.0     # Frequência de envio de ondas em minutos
    custom_targets: List[Tuple[int, int]] = field(default_factory=list)
    custom_troops: Dict[str, int] = field(default_factory=lambda: {"spear": 5, "spy": 1})


@dataclass
class RecruitmentConfig:
    """Configurações da rotina de Recrutamento Militar."""
    enabled: bool = False
    targets: Dict[str, int] = field(default_factory=lambda: {"spear": 50, "sword": 50, "axe": 50})
    batch_sizes: Dict[str, int] = field(default_factory=lambda: {"spear": 10, "sword": 10, "axe": 10, "light": 5})
    min_free_pop: int = 10
    interval_minutes: float = 5.0


@dataclass
class AuthConfig:
    """Configurações de autenticação automática e renovação de sessão."""
    username: str = ""
    password: str = ""
    auto_login: bool = False
    keep_alive: bool = True
    keep_alive_interval_minutes: float = 15.0


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



    def get_active_build_plan(self) -> List[Tuple[str, int]]:
        """
        Retorna a lista de metas de construção com base no template configurado.
        """
        tmpl = self.building.template.lower().strip()
        if tmpl == "balanced":
            return BALANCED_TEMPLATE
        elif tmpl in ("military", "military_rush"):
            return MILITARY_RUSH_TEMPLATE
        elif tmpl == "custom" and self.building.custom_plan:
            return self.building.custom_plan
        else:
            return RUSH_RESOURCES_TEMPLATE

    @property
    def effective_building_plan(self) -> List[Tuple[str, int]]:
        """Propriedade de compatibilidade que retorna o plano ativo."""
        return self.get_active_build_plan()


def load_config(config_file: str = "config.json") -> BotConfig:
    """
    Carrega as configurações a partir de 'config.json' na raiz do projeto.
    Se o ficheiro não existir, cria um exemplo por defeito e recorre às variáveis de ambiente.
    """
    config_path = Path(config_file)
    data: Dict[str, Any] = {}

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Ficheiro de configuração '{config_file}' carregado com sucesso.")
        except Exception as e:
            logger.warning(f"Erro ao ler '{config_file}', usando valores por defeito: {e}")
    else:
        # Se não existe, cria um modelo documentado para facilidade do utilizador
        _create_default_config_file(config_path)

    # 1. Carrega dados básicos (variáveis de ambiente só sobrepõem se não estiverem vazias)
    env_world = (os.getenv("TW_WORLD") or "").strip()
    env_sid = (os.getenv("TW_SID") or "").strip()
    env_proxy = (os.getenv("TW_PROXY") or "").strip()

    world = env_world if env_world else data.get("world", "pt117")
    sid = env_sid if env_sid else data.get("sid", "")
    domain = data.get("domain", "tribalwars.com.pt")
    proxy = env_proxy if env_proxy else data.get("proxy")


    # 2. Carrega configurações do Edifício Principal
    b_data = data.get("building", {})
    template = b_data.get("template", "rush_resources")
    max_queue = int(b_data.get("max_queue", 2))
    interval_seconds = float(b_data.get("interval_seconds", 75.0))

    # Converte custom_plan se fornecido como lista de listas/tuplos no JSON
    raw_custom = b_data.get("custom_plan", [])
    custom_plan: List[Tuple[str, int]] = []
    for item in raw_custom:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            custom_plan.append((str(item[0]).strip().lower(), int(item[1])))

    building_config = BuildingConfig(
        template=template,
        max_queue=max_queue,
        interval_seconds=interval_seconds,
        custom_plan=custom_plan,
    )

    # 3. Carrega configurações do Micro-Farming
    f_data = data.get("farm", {})
    raw_targets = f_data.get("custom_targets", [])
    custom_targets: List[Tuple[int, int]] = []
    for t in raw_targets:
        if isinstance(t, (list, tuple)) and len(t) == 2:
            custom_targets.append((int(t[0]), int(t[1])))

    raw_troops = f_data.get("custom_troops", {"spear": 5, "spy": 1})
    custom_troops = (
        {str(k): int(v) for k, v in raw_troops.items()}
        if isinstance(raw_troops, dict)
        else {"spear": 5, "spy": 1}
    )

    farm_config = FarmConfig(
        enabled=bool(f_data.get("enabled", False)),
        mode=str(f_data.get("mode", "am_farm")),
        template=str(f_data.get("template", "A")),
        max_distance=float(f_data.get("max_distance", 15.0)),
        skip_losses=bool(f_data.get("skip_losses", True)),
        skip_wall=bool(f_data.get("skip_wall", True)),
        interval_minutes=float(f_data.get("interval_minutes", 10.0)),
        custom_targets=custom_targets,
        custom_troops=custom_troops,
    )

    # 4. Carrega configurações de Recrutamento Militar
    r_data = data.get("recruitment", {})
    raw_r_targets = r_data.get("targets", {"spear": 50, "sword": 50, "axe": 50})
    r_targets = (
        {str(k): int(v) for k, v in raw_r_targets.items()}
        if isinstance(raw_r_targets, dict)
        else {}
    )

    raw_r_batches = r_data.get("batch_sizes", {"spear": 10, "sword": 10, "axe": 10, "light": 5})
    r_batches = (
        {str(k): int(v) for k, v in raw_r_batches.items()}
        if isinstance(raw_r_batches, dict)
        else {}
    )

    recruitment_config = RecruitmentConfig(
        enabled=bool(r_data.get("enabled", False)),
        targets=r_targets,
        batch_sizes=r_batches,
        min_free_pop=int(r_data.get("min_free_pop", 10)),
        interval_minutes=float(r_data.get("interval_minutes", 5.0)),
    )

    # 5. Carrega configurações de Autenticação Automática
    a_data = data.get("auth", {})
    auth_config = AuthConfig(
        username=str(a_data.get("username", os.environ.get("TW_USERNAME", ""))).strip(),
        password=str(a_data.get("password", os.environ.get("TW_PASSWORD", ""))).strip(),
        auto_login=bool(a_data.get("auto_login", False)),
        keep_alive=bool(a_data.get("keep_alive", True)),
        keep_alive_interval_minutes=float(a_data.get("keep_alive_interval_minutes", 15.0)),
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
    )


def save_config_sid(sid: str, config_path: Optional[Path] = None) -> bool:
    """Atualiza atomicamente o cookie 'sid' no ficheiro config.json."""
    path = config_path or Path("config.json")
    if not path.exists():
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["sid"] = sid.strip()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Cookie 'sid' atualizado e persistido com sucesso em '{path.name}'.")
        return True
    except Exception as e:
        logger.error(f"Erro ao persistir novo 'sid' em '{path.name}': {e}")
        return False





def _create_default_config_file(target_path: Path) -> None:
    """Cria um ficheiro config.json inicial documentado."""
    default_payload = {
        "world": "pt117",
        "sid": "",
        "building": {
            "_info": "Opções de template: 'rush_resources', 'balanced', 'military_rush' ou 'custom'",
            "template": "rush_resources",
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
