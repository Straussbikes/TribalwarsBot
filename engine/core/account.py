"""
Tribal Wars Mobile Automation Engine - TribalAccount
Gerenciador de sessão assíncrona com spoofing de fingerprint TLS/JA3/JA4,
headers móveis Android, gestão de estado, renovação de tokens e interceção anti-bot.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from curl_cffi.requests import AsyncSession, Response

from engine.core.exceptions import (
    ActionFailedError,
    BotProtectionError,
    GameMaintenanceError,
    NetworkTimeoutError,
    RateLimitError,
    SessionExpiredError,
    TribalWarsException,
)
from engine.core.models import PlayerData, Resources, VillageData
from engine.utils.parsers import (
    extract_csrf_token,
    extract_game_data,
    extract_resources,
    extract_village_and_player,
    is_bot_protection_present,
    is_session_expired,
)
from engine.utils.timing import get_click_jitter

logger = logging.getLogger(__name__)

# User-Agent e headers consistentes para Android Chrome Mobile
DEFAULT_MOBILE_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36"
)

DEFAULT_MOBILE_HEADERS = {
    "User-Agent": DEFAULT_MOBILE_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-CH-UA-Mobile": "?1",
    "Sec-CH-UA-Platform": '"Android"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Upgrade-Insecure-Requests": "1",
}


class TribalAccount:
    """
    Cliente assíncrono para automação de uma conta do Tribal Wars no modo mobile.
    Utiliza curl_cffi para mascaramento criptográfico do handshake TLS/JA3.
    """

    def __init__(
        self,
        world: str,
        sid: str,
        domain: str = "tribalwars.com.pt",
        proxy: Optional[str] = None,
        impersonate: str = "chrome124",
        timeout: float = 20.0,
    ):
        """
        :param world: Subdomínio do mundo ativo (ex.: 'pt117').
        :param sid: Cookie de autenticação de sessão.
        :param domain: Domínio TLD do servidor do jogo.
        :param proxy: URL do proxy residencial/dedicado (ex.: 'http://user:pass@ip:port').
        :param impersonate: Perfil de impersonation TLS do curl_cffi.
        :param timeout: Timeout das requisições em segundos.
        """
        self.world = world.strip().lower()
        self.sid = sid.strip()
        self.domain = domain.strip().lower()
        self.proxy = proxy
        self.impersonate = impersonate
        self.timeout = timeout

        # URLs base
        self.host = f"{self.world}.{self.domain}"
        self.base_url = f"https://{self.host}/game.php"

        # Estado da Conta
        self.player: Optional[PlayerData] = None
        self.current_village_id: Optional[int] = None
        self.villages: Dict[int, VillageData] = {}
        self.csrf_token: Optional[str] = None
        self.last_game_data: Optional[Dict[str, Any]] = None

        # Sessão HTTP curl_cffi
        self._session: Optional[AsyncSession] = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "TribalAccount":
        await self.init_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def init_session(self) -> None:
        """Inicializa a AsyncSession do curl_cffi com os cookies e headers móveis."""
        if self._session is not None:
            return

        self._session = AsyncSession(
            impersonate=self.impersonate,
            headers=DEFAULT_MOBILE_HEADERS.copy(),
            proxy=self.proxy,
            timeout=self.timeout,
            verify=True,
        )

        # Injeta o cookie de sessão 'sid' no jar de cookies para o domínio específico
        self._session.cookies.set("sid", self.sid, domain=self.host)

        logger.info(
            f"[{self.world}] Sessão de rede inicializada via curl_cffi (impersonate={self.impersonate})"
        )

    async def close(self) -> None:
        """Encerra a sessão assíncrona e liberta recursos de rede."""
        if self._session is not None:
            await self._session.close()
            self._session = None
            logger.info(f"[{self.world}] Sessão fechada com sucesso.")

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("A sessão não foi inicializada. Chame 'init_session()' primeiro.")
        return self._session

    @property
    def resources(self) -> Resources:
        """Retorna os recursos da aldeia ativa atual."""
        if self.current_village_id and self.current_village_id in self.villages:
            return self.villages[self.current_village_id].resources
        return Resources()

    @property
    def current_village(self) -> Optional[VillageData]:
        """Retorna a aldeia ativa atual."""
        if self.current_village_id and self.current_village_id in self.villages:
            return self.villages[self.current_village_id]
        return None

    def _inspect_response(self, response: Response, html: str) -> None:
        """
        Inspeciona a resposta HTTP para verificar exceções do jogo,
        bloqueios anti-bot, manutenção ou expiração de sessão.
        """
        # 1. Tratamento de Rate Limiting
        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", 30.0))
            raise RateLimitError(
                f"Taxa limite atingida (HTTP 429) no mundo {self.world}.",
                retry_after=retry_after,
            )

        # 2. Servidor indisponível / Manutenção
        if response.status_code in (502, 503, 504) or "indisponíveis temporariamente" in html:
            raise GameMaintenanceError(
                f"Servidor {self.world} em manutenção ou temporariamente inacessível (status {response.status_code})."
            )

        # 3. Deteção de Proteção Anti-Bot (Captcha)
        if is_bot_protection_present(html):
            snippet = html[:1200]
            logger.critical(f"[{self.world}] ALERTA ANTI-BOT INTERCETADO!")
            raise BotProtectionError(
                message=f"Verificação anti-bot ativada no mundo {self.world}! Intervenção requerida.",
                html_snippet=snippet,
            )

        # 4. Sessão Expirada / Ecrã de Login
        final_url = str(response.url) if response.url else ""
        if is_session_expired(html, current_url=final_url):
            raise SessionExpiredError(
                f"Sessão expirada para o mundo {self.world}. É necessário renovar o cookie 'sid'."
            )

        # 5. Validação de status code padrão
        if response.status_code >= 400:
            raise TribalWarsException(
                f"Erro HTTP {response.status_code} ao aceder ao endpoint do jogo: {response.text[:200]}"
            )

    def _update_state_from_html(self, html: str, url: str = "") -> None:
        """Extrai game_data, atualiza CSRF, recursos e informações de aldeia."""
        game_data = extract_game_data(html)
        if game_data:
            self.last_game_data = game_data

        # 1. Atualização do token CSRF
        new_csrf = extract_csrf_token(html, game_data)
        if new_csrf:
            self.csrf_token = new_csrf

        # 2. Atualização de Aldeia e Jogador
        village, player = extract_village_and_player(html, game_data)
        if player:
            self.player = player

        if village:
            self.current_village_id = village.id
            if village.id not in self.villages:
                self.villages[village.id] = village
            else:
                # Preserva recursos anteriores e atualiza dados
                curr_res = self.villages[village.id].resources
                self.villages[village.id] = village
                self.villages[village.id].resources = curr_res

        # 3. Atualização dos Recursos da aldeia ativa
        if self.current_village_id:
            res = extract_resources(html, game_data)
            if self.current_village_id in self.villages:
                self.villages[self.current_village_id].resources = res

    async def get_screen(
        self,
        screen: str,
        village_id: Optional[int] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        apply_jitter: bool = True,
    ) -> str:
        """
        Navega até um ecrã do jogo (ex.: 'screen=main', 'screen=place', 'screen=barracks')
        assegurando sempre 'page=mobile' e parâmetros de identificação.
        """
        if apply_jitter:
            await asyncio.sleep(get_click_jitter())

        async with self._lock:
            v_id = village_id or self.current_village_id
            params: Dict[str, Any] = {
                "page": "mobile",
                "screen": screen,
            }
            if v_id:
                params["village"] = v_id
            if extra_params:
                params.update(extra_params)

            try:
                response = await self.session.get(
                    self.base_url,
                    params=params,
                )
            except Exception as e:
                logger.error(f"Erro de conexão ao obter screen '{screen}': {e}")
                raise NetworkTimeoutError(f"Falha de conexão com {self.host}: {e}") from e

            html = response.text
            self._inspect_response(response, html)
            self._update_state_from_html(html, str(response.url))
            return html

    async def post_action(
        self,
        screen: str,
        action: str,
        data: Optional[Dict[str, Any]] = None,
        village_id: Optional[int] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        apply_jitter: bool = True,
    ) -> str:
        """
        Executa uma ação HTTP POST (ex.: enviar ataque, colocar edifício na fila),
        injetando automaticamente o token CSRF ('h') obrigatório.
        """
        if apply_jitter:
            await asyncio.sleep(get_click_jitter())

        async with self._lock:
            if not self.csrf_token:
                logger.warning("Token CSRF ausente. A atualizar estado antes da ação...")
                await self._refresh_state_internal()

            v_id = village_id or self.current_village_id
            params: Dict[str, Any] = {
                "page": "mobile",
                "screen": screen,
                "action": action,
                "h": self.csrf_token,
            }
            if v_id:
                params["village"] = v_id
            if extra_params:
                params.update(extra_params)

            post_data = (data or {}).copy()
            if "h" not in post_data and self.csrf_token:
                post_data["h"] = self.csrf_token

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": f"https://{self.host}",
                "Referer": f"{self.base_url}?village={v_id}&screen={screen}&page=mobile",
            }

            try:
                response = await self.session.post(
                    self.base_url,
                    params=params,
                    data=post_data,
                    headers=headers,
                )
            except Exception as e:
                logger.error(f"Erro de conexão ao executar action '{action}': {e}")
                raise NetworkTimeoutError(f"Falha de rede ao enviar ação {action}: {e}") from e

            html = response.text
            self._inspect_response(response, html)
            self._update_state_from_html(html, str(response.url))
            return html

    async def _refresh_state_internal(self) -> None:
        """Atualização interna sem bloqueio extra de lock."""
        params = {"page": "mobile", "screen": "main"}
        if self.current_village_id:
            params["village"] = self.current_village_id

        try:
            response = await self.session.get(self.base_url, params=params)
            html = response.text
            self._inspect_response(response, html)
            self._update_state_from_html(html, str(response.url))
        except Exception as e:
            logger.error(f"Falha ao atualizar estado: {e}")
            raise

    async def refresh_state(self, village_id: Optional[int] = None) -> VillageData:
        """
        Atualiza o estado completo da conta carregando o ecrã principal ('main').
        Retorna a VillageData atualizada com recursos e população.
        """
        await self.get_screen("main", village_id=village_id, apply_jitter=False)
        if not self.current_village:
            raise ActionFailedError("Não foi possível carregar as informações da aldeia.")
        return self.current_village
