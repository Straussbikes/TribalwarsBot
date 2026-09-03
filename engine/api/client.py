"""
Tribal Wars Mobile Automation Engine - ApiClient
Cliente HTTP assíncrono para comunicação e orquestração exclusiva com o backend Cloud API.
Garante que todas as consultas e operações transacionais operam de forma 100% cloud-native.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import httpx

from engine.storage.token_storage import TokenStorage, token_storage

logger = logging.getLogger("TribalWarsBot.ApiClient")


class ApiClient:
    """Cliente HTTP para a API Sidecar / Cloud API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        storage: Optional[TokenStorage] = None,
        timeout: float = 15.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.storage = storage or token_storage
        self.timeout = timeout
        self._current_token: Optional[str] = self.storage.load_token()

    @property
    def token(self) -> Optional[str]:
        return self._current_token

    def set_token(self, token: Optional[str], email: str = "") -> None:
        self._current_token = token
        if token:
            self.storage.save_token(token, email=email)
        else:
            self.storage.clear_token()

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._current_token:
            headers["Authorization"] = f"Bearer {self._current_token}"
        return headers

    async def check_health(self) -> bool:
        """Verifica a conectividade básica com o backend da API."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/health")
                return res.status_code == 200
        except Exception:
            return False

    async def register(self, email: str, password: str, license_type: str = "standard") -> Dict[str, Any]:
        """Regista um novo utilizador na aplicação via Cloud SQL."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(
                f"{self.base_url}/api/auth/register",
                json={"email": email, "password": password, "license_type": license_type},
            )
            data = res.json()
            if res.status_code != 200:
                raise ValueError(data.get("detail") or data.get("message") or "Erro ao registar utilizador.")
            if "token" in data:
                self.set_token(data["token"], email=email)
            return data

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """Efetua login, obtém JWT e armazena em auth.dat."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(
                f"{self.base_url}/api/auth/login",
                json={"email": email, "password": password},
            )
            data = res.json()
            if res.status_code != 200:
                raise ValueError(data.get("detail") or data.get("message") or "Credenciais inválidas.")
            token = data.get("token")
            if token:
                self.set_token(token, email=email)
            return data

    async def verify_auth(self) -> Optional[Dict[str, Any]]:
        """Verifica se o token armazenado é válido e retorna o utilizador."""
        token = self._current_token or self.storage.load_token()
        if not token:
            return None

        self._current_token = token
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(
                    f"{self.base_url}/api/auth/me",
                    headers=self._get_headers(),
                )
                if res.status_code == 200:
                    data = res.json()
                    if data.get("status") == "success" and data.get("user"):
                        return data.get("user")
        except Exception as e:
            logger.warning(f"[ApiClient] Falha ao verificar autenticação: {e}")
        return None

    async def get_accounts(self) -> List[Dict[str, Any]]:
        """Obtém as contas de jogo associadas ao utilizador."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.get(f"{self.base_url}/api/accounts", headers=self._get_headers())
            if res.status_code == 200:
                data = res.json()
                return data.get("accounts", [])
            return []

    async def get_building_templates(self) -> List[Dict[str, Any]]:
        """Obtém os modelos padrão de construção a partir da API."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.get(f"{self.base_url}/api/templates/building", headers=self._get_headers())
            if res.status_code == 200:
                data = res.json()
                return data.get("templates", [])
            return []

    async def switch_account(self, game_username: str, account_id: Optional[str] = None) -> Dict[str, Any]:
        """Solicita a troca atómica de conta com lock exclusivo."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            res = await client.post(
                f"{self.base_url}/api/accounts/switch",
                json={"game_username": game_username, "account_id": account_id},
                headers=self._get_headers(),
            )
            return res.json()

    def logout(self) -> None:
        """Limpa o token em memória e apaga o ficheiro auth.dat."""
        self.set_token(None)
