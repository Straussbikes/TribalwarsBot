"""
Tribal Wars Bot - Gestor de Perfis de Conta e Segurança (ProfileManager)
Armazenamento e gestão de múltiplos perfis de conta, proxies e ofuscação/encriptação
segura de credenciais para multi-mundo e multi-conta.
"""

import base64
from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import platform
import time
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)

# Diretório padrão para armazenamento isolado de perfis (profiles/{account_id}.json)
DEFAULT_PROFILES_DIR = Path("profiles")
LEGACY_PROFILES_PATH = Path("profiles.json")


def _get_machine_key() -> bytes:
    """Gera uma chave determinística local baseada no hardware da máquina para ofuscação de senhas."""
    seed = f"{platform.node()}-{platform.processor()}-{os.environ.get('USERNAME', 'twbot')}"
    return hashlib.sha256(seed.encode("utf-8")).digest()


def obfuscate_password(plain: str) -> str:
    """Ofusca/encripta uma senha usando XOR com a chave da máquina e codificação Base64."""
    if not plain:
        return ""
    key = _get_machine_key()
    plain_bytes = plain.encode("utf-8")
    cipher_bytes = bytes(b ^ key[i % len(key)] for i, b in enumerate(plain_bytes))
    return "enc:" + base64.b64encode(cipher_bytes).decode("ascii")


def deobfuscate_password(cipher: str) -> str:
    """Restaura a senha original a partir do formato ofuscado."""
    if not cipher:
        return ""
    if not cipher.startswith("enc:"):
        return cipher  # Permite compatibilidade se estiver em texto puro
    raw_b64 = cipher[4:]
    try:
        cipher_bytes = base64.b64decode(raw_b64.encode("ascii"))
        key = _get_machine_key()
        plain_bytes = bytes(b ^ key[i % len(key)] for i, b in enumerate(cipher_bytes))
        return plain_bytes.decode("utf-8")
    except Exception as e:
        logger.debug(f"Falha ao desofuscar credencial: {e}")
        return ""


@dataclass
class AccountProfile:
    """Perfil isolado de uma conta do Tribal Wars."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Minha Conta"
    world_domain: str = "pt117.tribalwars.com.pt"
    world: str = "pt117"
    domain: str = "tribalwars.com.pt"
    village_id: Optional[int] = None
    session_cookie: str = ""                         # Valor do cookie 'sid'
    sid: str = ""                                    # Alias para compatibilidade
    build_order_strategy: str = "rush_resources"     # Template de construção associado
    building_template: str = "rush_resources"        # Alias para compatibilidade
    farm_presets: Dict[str, Any] = field(default_factory=dict)
    recruitment_models: Dict[str, Any] = field(default_factory=dict)
    proxy: Optional[str] = None
    username: Optional[str] = None
    password_enc: Optional[str] = None
    auto_login: bool = True
    keep_alive: bool = True
    last_used: Optional[str] = None
    created_at: Optional[str] = None
    is_active: bool = False

    def __post_init__(self):
        # Sincroniza sid e session_cookie
        if not self.session_cookie and self.sid:
            self.session_cookie = self.sid
        elif not self.sid and self.session_cookie:
            self.sid = self.session_cookie

        # Sincroniza build_order_strategy e building_template
        if not self.build_order_strategy and self.building_template:
            self.build_order_strategy = self.building_template
        elif not self.building_template and self.build_order_strategy:
            self.building_template = self.build_order_strategy

        # Normaliza world e domain a partir de world_domain se aplicável
        if self.world_domain:
            wd = self.world_domain.strip().lower()
            if "." in wd:
                parts = wd.split(".", 1)
                self.world = parts[0]
                self.domain = parts[1]
            else:
                self.world = wd
                self.domain = self.domain or "tribalwars.com.pt"
                self.world_domain = f"{self.world}.{self.domain}"
        elif self.world and self.domain:
            self.world_domain = f"{self.world}.{self.domain}"

        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    @property
    def password(self) -> str:
        """Retorna a senha em texto puro desencriptada."""
        return deobfuscate_password(self.password_enc or "")

    @password.setter
    def password(self, plain_text: str) -> None:
        """Guarda a senha encriptada."""
        self.password_enc = obfuscate_password(plain_text)

    def to_dict(self, include_plain_password: bool = False) -> Dict[str, Any]:
        """Converte o perfil para um dicionário serializável."""
        data = asdict(self)
        if include_plain_password:
            data["password"] = self.password
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccountProfile":
        """Reconstrói um AccountProfile a partir de um dicionário."""
        data_copy = dict(data)
        pwd = data_copy.pop("password", None)
        pwd_enc = data_copy.get("password_enc")
        
        # Mapeamentos de campos legados
        if "sid" in data_copy and "session_cookie" not in data_copy:
            data_copy["session_cookie"] = data_copy["sid"]
        if "building_template" in data_copy and "build_order_strategy" not in data_copy:
            data_copy["build_order_strategy"] = data_copy["building_template"]

        valid_keys = {f for f in cls.__dataclass_fields__}
        profile = cls(**{k: v for k, v in data_copy.items() if k in valid_keys})
        if pwd and not pwd_enc:
            profile.password = pwd
        return profile


from engine.storage.database import AccountsDatabase


class ProfileManager:
    """Gestor de persistência e isolamento de perfis de conta com suporte a SQLite e JSON."""

    def __init__(self, profiles_dir: Path = DEFAULT_PROFILES_DIR, db_path: Optional[Path] = None):
        self.profiles_dir = Path(profiles_dir)
        self.profiles: Dict[str, AccountProfile] = {}
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        if db_path is None and self.profiles_dir != DEFAULT_PROFILES_DIR:
            db_path = self.profiles_dir / "accounts.db"
        self.db = AccountsDatabase(db_path=db_path)
        # Migração automática inicial de perfis JSON legados para a base de dados SQLite
        self.db.migrate_from_sources(profiles_dir=self.profiles_dir)
        self.load()

    def load(self) -> Dict[str, AccountProfile]:
        """Carrega os perfis guardados na base de dados SQLite e sincroniza a memória."""
        self.profiles.clear()
        db_accounts = self.db.list_accounts()

        # Se a base de dados ainda estiver vazia, tenta ler da pasta JSON
        if not db_accounts:
            self.db.migrate_from_sources(profiles_dir=self.profiles_dir)
            db_accounts = self.db.list_accounts()

        for acc in db_accounts:
            prof = AccountProfile.from_dict(acc)
            self.profiles[prof.id] = prof

        logger.info(f"Carregados {len(self.profiles)} perfis de conta a partir do repositório SQLite.")
        return self.profiles

    def save_profile(self, profile: AccountProfile) -> None:
        """Guarda um perfil na base de dados SQLite e no ficheiro JSON individual."""
        # 1. Base de dados SQLite
        self.db.save_account(profile.to_dict())

        # 2. Espelho JSON em profiles/{account_id}.json
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.profiles_dir / f"{profile.id}.json"
        tmp_file = file_path.with_suffix(".tmp")
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(profile.to_dict(include_plain_password=False), f, indent=2, ensure_ascii=False)
            tmp_file.replace(file_path)
            self.profiles[profile.id] = profile
            logger.debug(f"Perfil '{profile.name}' ({profile.id}) guardado em SQLite e {file_path}.")
        except Exception as e:
            logger.error(f"Falha ao guardar perfil {profile.id} em {file_path}: {e}")
            if tmp_file.exists():
                tmp_file.unlink()

    def get_profile(self, profile_id: str) -> Optional[AccountProfile]:
        """Obtém um perfil pelo ID."""
        if profile_id not in self.profiles:
            acc_data = self.db.get_account(profile_id)
            if acc_data:
                self.profiles[profile_id] = AccountProfile.from_dict(acc_data)
        return self.profiles.get(profile_id)

    def get_active_profile(self) -> Optional[AccountProfile]:
        """Retorna o perfil atualmente ativo."""
        active_data = self.db.get_active_account()
        if active_data:
            return AccountProfile.from_dict(active_data)
        for p in self.profiles.values():
            if p.is_active:
                return p
        return None

    def set_active_profile(self, profile_id: str) -> Optional[AccountProfile]:
        """Marca um perfil como ativo na base de dados e desativa os restantes."""
        target = self.get_profile(profile_id)
        if not target:
            return None

        # Bloqueio monousuário na base de dados
        self.db.set_active_account(profile_id)

        for p in self.profiles.values():
            p.is_active = (p.id == profile_id)
            if p.id == profile_id:
                p.last_used = datetime.now().isoformat()
            self.save_profile(p)

        logger.info(f"Perfil ativo alterado para '{target.name}' ({target.id}).")
        return target

    def deactivate_all(self) -> None:
        """Desativa todas as contas na base de dados (modo Offline)."""
        self.db.deactivate_all_accounts()
        for p in self.profiles.values():
            p.is_active = False
            file_path = self.profiles_dir / f"{p.id}.json"
            if file_path.exists():
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(p.to_dict(include_plain_password=False), f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
        logger.info("Todas as contas foram desativadas (Modo Offline).")

    def add_or_update_profile(self, profile: AccountProfile) -> None:
        """Adiciona ou atualiza um perfil e persiste no repositório."""
        self.save_profile(profile)

    def delete_profile(self, profile_id: str) -> bool:
        """Remove um perfil da base de dados e o ficheiro JSON correspondente."""
        self.db.delete_account(profile_id)
        if profile_id in self.profiles:
            del self.profiles[profile_id]
        file_path = self.profiles_dir / f"{profile_id}.json"
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Perfil {profile_id} eliminado de {file_path}.")
            except Exception as e:
                logger.error(f"Erro ao eliminar ficheiro do perfil {file_path}: {e}")
        return True

    def list_profiles(self) -> List[Dict[str, Any]]:
        """Retorna a lista de perfis para apresentação na UI a partir da base de dados."""
        accounts = self.db.list_accounts()
        if not accounts:
            return [p.to_dict(include_plain_password=False) for p in self.profiles.values()]
        return accounts


async def test_proxy_connection(proxy_url: str, timeout: float = 6.0) -> Dict[str, Any]:
    """
    Testa a conectividade de um proxy residencial ou dedicado via curl_cffi.
    Retorna o status, latência e IP público de saída.
    """
    import asyncio
    from curl_cffi.requests import AsyncSession

    start_t = time.time()
    try:
        async with AsyncSession(proxy=proxy_url, timeout=timeout, verify=True) as session:
            resp = await session.get("https://api.ipify.org?format=json")
            latency = (time.time() - start_t) * 1000
            if resp.status_code == 200:
                ip_data = resp.json()
                return {
                    "status": "online",
                    "ip": ip_data.get("ip", "desconhecido"),
                    "latency_ms": round(latency, 1),
                    "proxy": proxy_url,
                }
            return {
                "status": "error",
                "error": f"HTTP {resp.status_code}",
                "proxy": proxy_url,
            }
    except Exception as e:
        return {
            "status": "offline",
            "error": str(e),
            "proxy": proxy_url,
        }

