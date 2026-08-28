"""
Tribal Wars Mobile Automation Engine - TribalAccount
Gerenciador de sessão assíncrona com spoofing de fingerprint TLS/JA3/JA4,
headers móveis Android, gestão de estado, renovação de tokens e interceção anti-bot.
"""

import asyncio
from collections import deque
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlparse

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
    extract_all_villages,
    extract_csrf_token,
    extract_game_data,
    extract_resources,
    extract_village_and_player,
    is_bot_protection_present,
    is_session_expired,
    parse_available_units,
    parse_building_levels,
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

        # Histórico e telemetria de requisições de rede
        self._req_counter: int = 0
        self.request_history: deque = deque(maxlen=100)

        # Sessão HTTP curl_cffi
        self._session: Optional[AsyncSession] = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "TribalAccount":
        await self.init_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def update_sid(self, new_sid: str) -> None:
        """Atualiza o SID da conta e renova a sessão curl_cffi com os novos cookies."""
        clean_sid = new_sid.strip().strip('"').strip("'")
        if clean_sid.lower().startswith("sid="):
            clean_sid = clean_sid[4:].strip()
        self.sid = clean_sid
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None
        await self.init_session()

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

        # Normaliza o valor do SID (remove aspas, espaços e prefixo 'sid=')
        clean_sid = self.sid.strip().strip('"').strip("'")
        if clean_sid.lower().startswith("sid="):
            clean_sid = clean_sid[4:].strip()
        self.sid = clean_sid

        # Injeta o cookie de sessão 'sid' no jar de cookies para o subdomínio e para o domínio raiz
        self._session.cookies.set("sid", self.sid, domain=self.host)
        if self.domain:
            self._session.cookies.set("sid", self.sid, domain=f".{self.domain}")
            self._session.cookies.set("sid", self.sid, domain=self.domain)

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

    @resources.setter
    def resources(self, res: Resources) -> None:
        """Define os recursos da aldeia ativa atual."""
        v_id = self.current_village_id or 0
        if v_id in self.villages:
            self.villages[v_id].resources = res
        else:
            self.villages[v_id] = VillageData(id=v_id, resources=res)

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
            logger.warning(f"[{self.world}] Sessão expirada ou redirecionada. URL final: '{final_url}'")
            raise SessionExpiredError(
                f"Sessão expirada para o mundo {self.world}. É necessário renovar o cookie 'sid'."
            )

        # 5. Verifica se o servidor rotacionou o cookie 'sid' na sessão
        if self._session is not None:
            jar_sid = self._session.cookies.get("sid")
            if jar_sid and jar_sid != self.sid:
                logger.info(f"[{self.world}] Cookie 'sid' rotacionado pelo servidor. A atualizar...")
                self.sid = jar_sid
                from engine.config.settings import save_config_sid
                save_config_sid(jar_sid)

        # 6. Validação de status code padrão
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

        # 2. Atualização de Aldeias e Jogador
        village, player = extract_village_and_player(html, game_data)
        if player:
            self.player = player

        # Extrai todas as aldeias pertencentes à conta (suporte multi-aldeia)
        all_vills = extract_all_villages(html, game_data)
        for v_id, v_data in all_vills.items():
            if v_id not in self.villages:
                self.villages[v_id] = v_data
            else:
                curr_res = self.villages[v_id].resources
                self.villages[v_id] = v_data
                self.villages[v_id].resources = curr_res

        if village:
            self.current_village_id = village.id
            if village.id not in self.villages:
                self.villages[village.id] = village

        # 3. Atualização dos Recursos da aldeia ativa
        if self.current_village_id:
            res = extract_resources(html, game_data)
            if self.current_village_id in self.villages:
                self.villages[self.current_village_id].resources = res

        # 4. Atualização das Tropas disponíveis na aldeia ativa
        if self.current_village_id and self.current_village_id in self.villages:
            try:
                units = parse_available_units(html)
                if any(units.values()):
                    self.villages[self.current_village_id].troops = units
            except Exception:
                pass

        # 5. Atualização dos Níveis de Edifícios da aldeia ativa
        if self.current_village_id and self.current_village_id in self.villages:
            try:
                blds = parse_building_levels(html, game_data)
                if blds:
                    self.villages[self.current_village_id].buildings.update(blds)
            except Exception:
                pass


    def _record_request(
        self,
        req_id: int,
        method: str,
        url: str,
        params: Dict[str, Any],
        status_code: int,
        duration_ms: float,
        size_bytes: int,
        error: Optional[str] = None,
    ) -> None:
        """Regista no histórico em memória para diagnóstico e telemetria."""
        self.request_history.append({
            "id": req_id,
            "timestamp": time.time(),
            "method": method,
            "url": url,
            "params": params,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 1),
            "size_bytes": size_bytes,
            "error": error,
        })

    def get_recent_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retorna as requisições HTTP mais recentes registadas."""
        history = list(self.request_history)
        return history[-limit:]

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
        Emite logs detalhados e telemetria de cada requisição.
        """
        if apply_jitter:
            await asyncio.sleep(get_click_jitter())

        async with self._lock:
            self._req_counter += 1
            req_id = self._req_counter

            v_id = village_id or self.current_village_id
            params: Dict[str, Any] = {
                "screen": screen,
                "page": "mobile",
            }
            if v_id:
                params["village"] = v_id
            if extra_params:
                params.update(extra_params)

            # Se a requisição contiver 'action', garante que o token CSRF ('h') está presente
            if "action" in params and ("h" not in params or not params["h"]):
                if not self.csrf_token:
                    logger.warning(f"[{self.world}] Token CSRF ausente. A atualizar estado antes de executar a ação...")
                    await self._refresh_state_internal()
                if self.csrf_token:
                    params["h"] = self.csrf_token

            query_str = urlencode({k: str(v) for k, v in params.items()})
            full_url = f"{self.base_url}?{query_str}"
            logger.info(
                f"[{self.world}] 🌐 [REQ #{req_id}] GET {self.base_url}?{query_str}"
            )

            start_t = time.monotonic()
            try:
                response = await self.session.get(
                    self.base_url,
                    params=params,
                )
            except Exception as e:
                duration_ms = (time.monotonic() - start_t) * 1000
                self._record_request(
                    req_id=req_id,
                    method="GET",
                    url=full_url,
                    params=params,
                    status_code=0,
                    duration_ms=duration_ms,
                    size_bytes=0,
                    error=str(e),
                )
                logger.error(f"[{self.world}] ❌ [REQ #{req_id}] Erro de conexão após {duration_ms:.0f}ms ao obter screen '{screen}': {e}")
                raise NetworkTimeoutError(f"Falha de conexão com {self.host}: {e}") from e

            duration_ms = (time.monotonic() - start_t) * 1000
            html = response.text
            size_bytes = len(response.content) if hasattr(response, "content") else len(html.encode("utf-8"))
            size_str = f"{size_bytes / 1024:.1f} KB" if size_bytes >= 1024 else f"{size_bytes} B"

            logger.info(
                f"[{self.world}] 📥 [RESP #{req_id}] HTTP {response.status_code} ({duration_ms:.0f}ms, {size_str}) - screen={screen}"
            )

            self._record_request(
                req_id=req_id,
                method="GET",
                url=full_url,
                params=params,
                status_code=response.status_code,
                duration_ms=duration_ms,
                size_bytes=size_bytes,
            )

            self._inspect_response(response, html)
            self._update_state_from_html(html, str(response.url))
            return html

    async def post_action(
        self,
        screen: str,
        action: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        village_id: Optional[int] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        apply_jitter: bool = True,
    ) -> str:
        """
        Executa uma ação HTTP POST (ex.: enviar ataque, colocar edifício na fila),
        injetando automaticamente o token CSRF ('h') obrigatório e 'page=mobile'.
        Emite logs detalhados e telemetria da requisição.
        """
        if apply_jitter:
            await asyncio.sleep(get_click_jitter())

        async with self._lock:
            self._req_counter += 1
            req_id = self._req_counter

            if not self.csrf_token:
                logger.warning(f"[{self.world}] Token CSRF ausente. A atualizar estado antes da ação...")
                await self._refresh_state_internal()

            v_id = village_id or self.current_village_id
            params: Dict[str, Any] = {
                "screen": screen,
                "page": "mobile",
            }
            if action:
                params["action"] = action
            if self.csrf_token:
                params["h"] = self.csrf_token
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

            query_str = urlencode({k: str(v) for k, v in params.items()})
            full_url = f"{self.base_url}?{query_str}"
            logger.info(
                f"[{self.world}] 🌐 [REQ #{req_id}] POST {self.base_url}?{query_str} | Data: {post_data}"
            )

            start_t = time.monotonic()
            try:
                response = await self.session.post(
                    self.base_url,
                    params=params,
                    data=post_data,
                    headers=headers,
                )
            except Exception as e:
                duration_ms = (time.monotonic() - start_t) * 1000
                self._record_request(
                    req_id=req_id,
                    method="POST",
                    url=full_url,
                    params=params,
                    status_code=0,
                    duration_ms=duration_ms,
                    size_bytes=0,
                    error=str(e),
                )
                logger.error(f"[{self.world}] ❌ [REQ #{req_id}] Erro de conexão após {duration_ms:.0f}ms ao executar action '{action}': {e}")
                raise NetworkTimeoutError(f"Falha de rede ao enviar ação {action}: {e}") from e

            duration_ms = (time.monotonic() - start_t) * 1000
            html = response.text
            size_bytes = len(response.content) if hasattr(response, "content") else len(html.encode("utf-8"))
            size_str = f"{size_bytes / 1024:.1f} KB" if size_bytes >= 1024 else f"{size_bytes} B"

            logger.info(
                f"[{self.world}] 📥 [RESP #{req_id}] HTTP {response.status_code} ({duration_ms:.0f}ms, {size_str}) - action={action}"
            )

            self._record_request(
                req_id=req_id,
                method="POST",
                url=full_url,
                params=params,
                status_code=response.status_code,
                duration_ms=duration_ms,
                size_bytes=size_bytes,
            )

            self._inspect_response(response, html)
            self._update_state_from_html(html, str(response.url))
            return html

    async def _refresh_state_internal(self) -> None:
        """Atualização interna sem bloqueio extra de lock."""
        params = {"screen": "main", "page": "mobile"}
        if self.current_village_id:
            params["village"] = self.current_village_id

        try:
            response = await self.session.get(self.base_url, params=params)
            html = response.text
            self._inspect_response(response, html)
            self._update_state_from_html(html, str(response.url))
        except Exception as e:
            logger.error(f"[{self.world}] Falha ao atualizar estado interno: {e}")
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

    async def switch_village(self, village_id: int) -> VillageData:
        """
        Alterna o contexto ativo para uma aldeia específica do jogador.
        Atualiza recursos e edifícios da aldeia selecionada.
        """
        logger.info(f"[{self.world}] A alternar contexto ativo para aldeia {village_id}...")
        await self.get_screen("overview", village_id=village_id, apply_jitter=True)
        self.current_village_id = village_id
        if village_id in self.villages:
            return self.villages[village_id]
        return VillageData(id=village_id, name=f"Aldeia {village_id}")

    async def refresh_village_details(self, village_id: Optional[int] = None) -> VillageData:
        """
        Navega até à Praça de Reunião para ler os recursos e tropas disponíveis mais recentes.
        """
        v_id = village_id or self.current_village_id
        await self.get_screen("place", village_id=v_id)
        if v_id and v_id in self.villages:
            return self.villages[v_id]
        return self.current_village or VillageData(id=v_id or 0)

