"""
Tribal Wars Bot - Gestor de Perfis de Conta e Segurança (ProfileManager)
Armazenamento e gestão de múltiplos perfis de conta, proxies e ofuscação/encriptação
segura de credenciais para multi-mundo e multi-conta.
"""

import base64
from dataclasses import asdict, dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import platform
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Ficheiro padrão de armazenamento de perfis
DEFAULT_PROFILES_PATH = Path("profiles.json")


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
    """Perfil isolado de uma conta ou mundo do Tribal Wars."""

    id: str                                  # Identificador único (ex: 'pt117_main')
    name: str                                # Nome legível (ex: 'Conta Principal pt117')
    world: str = "pt117"                     # Subdomínio do mundo
    sid: str = ""                            # Cookie de autenticação de sessão
    domain: str = "tribalwars.com.pt"        # Domínio TLD
    proxy: Optional[str] = None              # Proxy dedicado (ex: http://user:pass@ip:port)
    username: Optional[str] = None           # Nome de utilizador
    password_enc: Optional[str] = None       # Senha encriptada/ofuscada
    auto_login: bool = True                  # Ativar auto-login perante expiração
    keep_alive: bool = True                  # Ativar pulso de keep-alive
    building_template: str = "rush_resources"# Template de construção ativo
    is_active: bool = False                  # Perfil atualmente selecionado

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
        pwd = data.pop("password", None)
        pwd_enc = data.get("password_enc")
        profile = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        if pwd and not pwd_enc:
            profile.password = pwd
        return profile


class ProfileManager:
    """Gestor de persistência e alternância de perfis de conta."""

    def __init__(self, file_path: Path = DEFAULT_PROFILES_PATH):
        self.file_path = Path(file_path)
        self.profiles: Dict[str, AccountProfile] = {}
        self.load()

    def load(self) -> Dict[str, AccountProfile]:
        """Carrega os perfis guardados no ficheiro JSON."""
        self.profiles.clear()
        if not self.file_path.exists():
            return self.profiles

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                items = data.get("profiles", [])
                for item in items:
                    prof = AccountProfile.from_dict(item)
                    self.profiles[prof.id] = prof
            logger.info(f"Carregados {len(self.profiles)} perfis de conta a partir de {self.file_path}.")
        except Exception as e:
            logger.error(f"Erro ao carregar ficheiro de perfis {self.file_path}: {e}")

        return self.profiles

    def save(self) -> None:
        """Guarda todos os perfis no ficheiro JSON de forma segura e atómica."""
        tmp_file = self.file_path.with_suffix(".tmp")
        try:
            payload = {
                "_version": "2.0",
                "_comment": "Perfis de conta do Tribal Wars Bot com credenciais ofuscadas.",
                "profiles": [p.to_dict() for p in self.profiles.values()],
            }
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            tmp_file.replace(self.file_path)
            logger.debug(f"Perfis guardados com sucesso em {self.file_path}.")
        except Exception as e:
            logger.error(f"Falha ao guardar perfis em {self.file_path}: {e}")
            if tmp_file.exists():
                tmp_file.unlink()

    def get_profile(self, profile_id: str) -> Optional[AccountProfile]:
        return self.profiles.get(profile_id)

    def get_active_profile(self) -> Optional[AccountProfile]:
        """Retorna o perfil atualmente ativo."""
        for p in self.profiles.values():
            if p.is_active:
                return p
        # Se nenhum estiver explicitamente ativo, retorna o primeiro disponível
        if self.profiles:
            first = next(iter(self.profiles.values()))
            first.is_active = True
            return first
        return None

    def set_active_profile(self, profile_id: str) -> Optional[AccountProfile]:
        """Marca um perfil como ativo e desativa os restantes."""
        target = self.profiles.get(profile_id)
        if not target:
            return None

        for p in self.profiles.values():
            p.is_active = (p.id == profile_id)
        self.save()
        logger.info(f"Perfil ativo alterado para '{target.name}' ({target.id}).")
        return target

    def add_or_update_profile(self, profile: AccountProfile) -> None:
        """Adiciona ou atualiza um perfil e persiste as alterações."""
        self.profiles[profile.id] = profile
        self.save()

    def delete_profile(self, profile_id: str) -> bool:
        """Remove um perfil."""
        if profile_id in self.profiles:
            del self.profiles[profile_id]
            self.save()
            return True
        return False

    def list_profiles(self) -> List[Dict[str, Any]]:
        """Retorna a lista de perfis para apresentação na UI (sem expor passwords)."""
        return [p.to_dict(include_plain_password=False) for p in self.profiles.values()]


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
            # Testa contra o endpoint de IP
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
