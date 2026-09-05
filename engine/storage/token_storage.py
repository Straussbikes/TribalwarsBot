"""
Tribal Wars Mobile Automation Engine - Token Storage
O ÚNICO armazenamento persistente local autorizado pelo sistema.
Gere a gravação e leitura do token JWT encriptado em 'auth.dat' com AES-256-GCM.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import platform
import sys
import time
from typing import Optional, Dict, Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import hashlib

logger = logging.getLogger("TribalWarsBot.TokenStorage")


class TokenStorage:
    """Armazenamento seguro do token JWT de autenticação do utilizador."""

    AUTH_FILENAME = "auth.dat"

    def __init__(self, custom_path: Optional[Path] = None):
        self._auth_file = custom_path or self._resolve_default_path()
        self._key = self._derive_device_key()
        self._aesgcm = AESGCM(self._key)

    def _resolve_default_path(self) -> Path:
        """Determina o diretório seguro para guardar auth.dat."""
        if sys.platform == "win32":
            base_dir = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            if base_dir:
                target_dir = Path(base_dir) / "TribalWarsBot"
            else:
                target_dir = Path.home() / ".tribalwarsbot"
        else:
            target_dir = Path.home() / ".config" / "tribalwarsbot"

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            return target_dir / self.AUTH_FILENAME
        except Exception:
            # Fallback seguro para o diretório de execução se não houver permissão
            local_dir = Path("data")
            local_dir.mkdir(parents=True, exist_ok=True)
            return local_dir / self.AUTH_FILENAME

    def _derive_device_key(self) -> bytes:
        """Deriva uma chave criptográfica AES-256 (32 bytes) a partir da identidade da máquina."""
        device_sig = f"{platform.node()}:{platform.machine()}:{platform.processor()}:{os.environ.get('USERNAME', 'tribal')}"
        digest = hashlib.sha256(device_sig.encode("utf-8")).digest()
        return digest

    @property
    def auth_file_path(self) -> Path:
        return self._auth_file

    def save_token(self, token: str, email: str = "") -> None:
        """Serializa e encripta o token JWT em 'auth.dat'."""
        if not token or not token.strip():
            self.clear_token()
            return

        payload: Dict[str, Any] = {
            "token": token.strip(),
            "email": email.strip(),
            "saved_at": time.time(),
        }

        plaintext = json.dumps(payload).encode("utf-8")
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
        encrypted_bytes = nonce + ciphertext

        try:
            self._auth_file.parent.mkdir(parents=True, exist_ok=True)
            self._auth_file.write_bytes(encrypted_bytes)
            logger.info(f"[TokenStorage] Token de autenticação guardado com sucesso em '{self._auth_file}'.")
        except Exception as e:
            logger.error(f"[TokenStorage] Erro ao gravar token em '{self._auth_file}': {e}")
            raise

    def load_token(self) -> Optional[str]:
        """Lê e desencripta o token JWT guardado em 'auth.dat'. Retorna None se inexistente ou corrompido."""
        if not self._auth_file.exists():
            return None

        try:
            raw_bytes = self._auth_file.read_bytes()
            if len(raw_bytes) < 28:
                return None

            nonce = raw_bytes[:12]
            ciphertext = raw_bytes[12:]
            decrypted = self._aesgcm.decrypt(nonce, ciphertext, None)
            payload = json.loads(decrypted.decode("utf-8"))
            return payload.get("token")
        except Exception as e:
            logger.warning(f"[TokenStorage] Não foi possível ler/desencriptar 'auth.dat': {e}")
            return None

    def load_payload(self) -> Optional[Dict[str, Any]]:
        """Lê os metadados completos da sessão guardada."""
        if not self._auth_file.exists():
            return None
        try:
            raw_bytes = self._auth_file.read_bytes()
            if len(raw_bytes) < 28:
                return None
            nonce = raw_bytes[:12]
            ciphertext = raw_bytes[12:]
            decrypted = self._aesgcm.decrypt(nonce, ciphertext, None)
            return json.loads(decrypted.decode("utf-8"))
        except Exception:
            return None

    def clear_token(self) -> None:
        """Remove o ficheiro 'auth.dat'."""
        try:
            if self._auth_file.exists():
                self._auth_file.unlink()
                logger.info(f"[TokenStorage] Ficheiro de autenticação '{self._auth_file}' removido.")
        except Exception as e:
            logger.warning(f"[TokenStorage] Falha ao remover '{self._auth_file}': {e}")


# Singleton global padrão
token_storage = TokenStorage()
