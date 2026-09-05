"""
Tribal Wars Mobile Automation Engine - TribalWarsAuthHandler
Módulo dedicado de autenticação assíncrona com impersonation de fingerprint TLS (curl_cffi),
gestão segura de credenciais, deteção de CAPTCHA/Bot Protection e seleção automática de mundo.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from curl_cffi.requests import AsyncSession

from engine.core.exceptions import (
    TribalWarsException,
)
from engine.utils.parsers import is_bot_protection_present
from engine.utils.timing import get_click_jitter

logger = logging.getLogger(__name__)

DEFAULT_DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_AUTH_HEADERS = {
    "User-Agent": DEFAULT_DESKTOP_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


class AuthException(TribalWarsException):
    """Exceção base para falhas de autenticação."""
    pass


class InvalidCredentialsError(AuthException):
    """Credenciais de utilizador ou palavra-passe incorretas."""
    pass


class CaptchaRequiredError(AuthException):
    """Desafio de CAPTCHA ou Bot Protection detetado durante o fluxo de login."""
    def __init__(self, message: str = "Desafio anti-bot / CAPTCHA intercetado no login.", html_snippet: str = ""):
        super().__init__(message)
        self.html_snippet = html_snippet


class AccountLockedError(AuthException):
    """Conta suspensa ou bloqueada pelo suporte do jogo."""
    pass


class AuthResult:
    """Resultado estruturado de uma tentativa de autenticação."""

    def __init__(
        self,
        success: bool,
        sid: Optional[str] = None,
        world: Optional[str] = None,
        username: Optional[str] = None,
        error_type: Optional[str] = None,
        message: Optional[str] = None,
        captcha_detected: bool = False,
        available_worlds: Optional[List[str]] = None,
    ):
        self.success = success
        self.sid = sid
        self.world = world
        self.username = username
        self.error_type = error_type
        self.message = message or ""
        self.captcha_detected = captcha_detected
        self.available_worlds = available_worlds or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "sid": self.sid,
            "world": self.world,
            "username": self.username,
            "error_type": self.error_type,
            "message": self.message,
            "captcha_detected": self.captcha_detected,
            "available_worlds": self.available_worlds,
        }


class TribalWarsAuthHandler:
    """
    Gestor de autenticação HTTP assíncrono para o Tribal Wars.
    Realiza o handshake, submissão de credenciais, resolução de mundos e extração de SID.
    """

    def __init__(
        self,
        domain: str = "tribalwars.com.pt",
        proxy: Optional[str] = None,
        impersonate: str = "chrome124",
        timeout: float = 25.0,
    ):
        self.domain = domain.strip().lower()
        self.proxy = proxy
        self.impersonate = impersonate
        self.timeout = timeout
        self.base_domain_url = f"https://www.{self.domain}"

    def _create_session(self) -> AsyncSession:
        """Instancia uma sessão curl_cffi com impersonation TLS de browser genuíno."""
        session = AsyncSession(
            impersonate=self.impersonate,
            timeout=self.timeout,
            proxy=self.proxy,
            headers=DEFAULT_AUTH_HEADERS.copy(),
        )
        return session

    async def login(
        self,
        username: str,
        password: str,
        target_world: str = "pt117",
    ) -> AuthResult:
        """
        Executa o fluxo completo de login automático:
        1. Handshake inicial na home page do Tribal Wars.
        2. POST de credenciais para /index.php?action=login.
        3. Seleção de mundo pretendido (se página de seleção for retornada).
        4. Validação e extração do cookie 'sid'.
        """
        user = username.strip()
        pwd = password.strip()
        world = target_world.strip().lower()

        if not user or not pwd:
            return AuthResult(
                success=False,
                error_type="invalid_input",
                message="Nome de utilizador e palavra-passe são obrigatórios.",
            )

        session = self._create_session()
        try:
            # -------------------------------------------------------------
            # PASSO 1: Handshake Inicial
            # -------------------------------------------------------------
            logger.info(f"[{user}] A iniciar handshake de autenticação em {self.base_domain_url}...")
            try:
                home_res = await session.get(self.base_domain_url)
            except Exception as net_err:
                logger.error(f"[{user}] Falha de rede no handshake inicial: {net_err}")
                return AuthResult(
                    success=False,
                    error_type="network_error",
                    message=f"Erro de conexão ao servidor de autenticação: {net_err}",
                )

            # Verifica desafio anti-bot logo no portal
            if is_bot_protection_present(home_res.text):
                logger.critical(f"[{user}] Anti-Bot / CAPTCHA intercetado no portal inicial!")
                return AuthResult(
                    success=False,
                    captcha_detected=True,
                    error_type="captcha_required",
                    message="Verificação anti-bot / CAPTCHA intercetada no portal inicial.",
                )

            await asyncio.sleep(get_click_jitter(0.2, 0.45))

            # -------------------------------------------------------------
            # PASSO 2: Submissão de Credenciais
            # -------------------------------------------------------------
            login_url = f"{self.base_domain_url}/index.php?action=login"
            login_data = {
                "user": user,
                "password": pwd,
                "remember": "1",
                "cookie": "1",
            }

            post_headers = DEFAULT_AUTH_HEADERS.copy()
            post_headers.update({
                "Origin": self.base_domain_url,
                "Referer": f"{self.base_domain_url}/",
                "Content-Type": "application/x-www-form-urlencoded",
            })

            logger.info(f"[{user}] A submeter credenciais para autenticação...")
            try:
                login_res = await session.post(
                    login_url,
                    data=login_data,
                    headers=post_headers,
                    allow_redirects=True,
                )
            except Exception as post_err:
                logger.error(f"[{user}] Erro no envio de credenciais: {post_err}")
                return AuthResult(
                    success=False,
                    error_type="network_error",
                    message=f"Erro no envio de credenciais: {post_err}",
                )

            final_url = str(login_res.url)
            html = login_res.text or ""

            # Deteção de CAPTCHA / Verificação Anti-Bot na resposta de login
            if is_bot_protection_present(html) or "recaptcha" in html.lower() or "hcaptcha" in html.lower() or "bot_check" in html.lower():
                logger.critical(f"[{user}] Desafio anti-bot detetado na resposta de login!")
                return AuthResult(
                    success=False,
                    captcha_detected=True,
                    error_type="captcha_required",
                    message="Desafio anti-bot / CAPTCHA detetado na resposta de login. Resolução manual necessária.",
                )

            # Deteção de Credenciais Inválidas ou Erro de Login
            if self._is_invalid_credentials(html):
                logger.warning(f"[{user}] Credenciais rejeitadas pelo servidor do Tribal Wars.")
                return AuthResult(
                    success=False,
                    error_type="invalid_credentials",
                    message="Nome de utilizador ou palavra-passe incorretos.",
                )

            if "conta foi bloqueada" in html.lower() or "account has been locked" in html.lower():
                logger.critical(f"[{user}] Conta suspensa ou bloqueada pelo jogo!")
                return AuthResult(
                    success=False,
                    error_type="account_locked",
                    message="A conta de jogo foi suspensa ou bloqueada pelas regras do Tribal Wars.",
                )

            # -------------------------------------------------------------
            # PASSO 3: Resolução de Mundo
            # -------------------------------------------------------------
            # Pode redirecionar direto para o mundo (ex: https://pt117.tribalwars.com.pt/game.php)
            # ou apresentar a página de seleção de mundos (/page/play/...)
            sid = session.cookies.get("sid")
            available_worlds = self._extract_available_worlds(html)

            # Se ainda não entrou diretamente no mundo alvo:
            if f"{world}." not in final_url:
                logger.info(f"[{user}] A selecionar mundo '{world}' (Mundos disponíveis detetados: {available_worlds})...")
                world_play_url = f"{self.base_domain_url}/page/play/{world}"
                
                try:
                    world_res = await session.get(world_play_url, allow_redirects=True)
                    final_url = str(world_res.url)
                    html = world_res.text or ""
                    sid = session.cookies.get("sid") or sid
                except Exception as w_err:
                    logger.warning(f"[{user}] Aviso ao selecionar mundo '{world}': {w_err}")

            # -------------------------------------------------------------
            # PASSO 4: Verificação Final do Cookie 'sid'
            # -------------------------------------------------------------
            if not sid:
                # Tenta extrair do jar por domínio
                for cookie in session.cookies.jar:
                    if cookie.name == "sid" and cookie.value:
                        sid = cookie.value
                        break

            if sid and len(sid) >= 16:
                logger.info(f"[{user}] Autenticação bem-sucedida no mundo {world}! Cookie 'sid' capturado com sucesso.")
                return AuthResult(
                    success=True,
                    sid=sid,
                    world=world,
                    username=user,
                    available_worlds=available_worlds,
                    message=f"Login automático concluído com sucesso no mundo {world}.",
                )

            # Se chegou aqui sem SID e sem erro explícito:
            logger.warning(f"[{user}] Resposta inesperada: cookie 'sid' não capturado. URL final: '{final_url}'")
            return AuthResult(
                success=False,
                error_type="sid_not_found",
                message="Não foi possível capturar o cookie de sessão 'sid' após o login.",
                available_worlds=available_worlds,
            )

        finally:
            try:
                await session.close()
            except Exception as e:
                logger.debug(f"Aviso ao fechar sessão temporária de login: {e}")

    def _is_invalid_credentials(self, html: str) -> bool:
        """Verifica se o HTML de resposta indica erro de autenticação / password errada."""
        lower = html.lower()
        patterns = [
            "palavra-passe errada",
            "palavra-passe incorreta",
            "dados de acesso errados",
            "utilizador não existe",
            "invalid password",
            "wrong password",
            "user does not exist",
            "senha errada",
            "senha incorreta",
        ]
        return any(p in lower for p in patterns)

    def _extract_available_worlds(self, html: str) -> List[str]:
        """Extrai a lista de mundos disponíveis no ecrã de seleção de mundos."""
        found = set(re.findall(r"/page/play/([a-zA-Z0-9]+)", html))
        # Também busca por links para mundos
        for m in re.findall(r"([a-zA-Z]{2,4}\d+)\.tribalwars\.", html):
            found.add(m.lower())
        return sorted(list(found))
