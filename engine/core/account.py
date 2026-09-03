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
from urllib.parse import urlencode

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
    extract_player_worlds,
    extract_resources,
    extract_village_and_player,
    is_bot_protection_present,
    is_session_expired,
    parse_available_units,
    parse_building_levels,
    parse_overview_villages,
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
        max_network_retries: int = 3,
        retry_backoff_base: float = 1.0,
    ):
        """
        :param world: Subdomínio do mundo ativo (ex.: 'pt117').
        :param sid: Cookie de autenticação de sessão.
        :param domain: Domínio TLD do servidor do jogo.
        :param proxy: URL do proxy residencial/dedicado (ex.: 'http://user:pass@ip:port').
        :param impersonate: Perfil de impersonation TLS do curl_cffi.
        :param timeout: Timeout das requisições em segundos.
        :param max_network_retries: Número de tentativas em caso de erro de conexão/rede transitório.
        :param retry_backoff_base: Tempo base em segundos para backoff exponencial entre retentativas.
        """
        self.world = world.strip().lower()
        self.sid = sid.strip()
        self.domain = domain.strip().lower()
        self.proxy = proxy
        self.impersonate = impersonate
        self.timeout = timeout
        self.max_network_retries = max(1, max_network_retries)
        self.retry_backoff_base = max(0.1, retry_backoff_base)

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
        self.stats_tracker: Optional[Any] = None

        # Sessão HTTP curl_cffi
        self._session: Optional[AsyncSession] = None
        self._lock = asyncio.Lock()

    @property
    def game_data(self) -> Dict[str, Any]:
        """Retorna os dados do jogo mais recentes obtidos via script game_data."""
        return self.last_game_data or {}

    @game_data.setter
    def game_data(self, value: Dict[str, Any]) -> None:
        self.last_game_data = value

    def get_stats_tracker(self) -> Any:
        """Retorna ou instancia o rastreador de estatísticas do mundo e conta."""
        if getattr(self, "stats_tracker", None) is not None:
            return self.stats_tracker
        from engine.core.stats import StatsTracker
        acc_id = getattr(self, "username", None) or getattr(self, "profile_id", None) or "default"
        self.stats_tracker = StatsTracker(world=self.world, account_id=acc_id)
        return self.stats_tracker

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
            except Exception as e:
                logger.debug(f"Aviso ao encerrar sessão curl_cffi: {e}")
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
        clean_sid = self.sid.strip().strip('"').strip("'") if self.sid else ""
        if clean_sid.lower().startswith("sid="):
            clean_sid = clean_sid[4:].strip()
        self.sid = clean_sid

        # Injeta o cookie de sessão 'sid' no jar de cookies para o subdomínio e para o domínio raiz
        if self.sid:
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

    def get_stats_tracker(self) -> Any:
        """Obtém ou instancia o StatsTracker associado a esta conta."""
        if hasattr(self, "stats_tracker") and self.stats_tracker:
            return self.stats_tracker
        from engine.core.stats import StatsTracker
        account_id = getattr(self, "account_id", None) or getattr(self, "profile_id", "default_main")
        self.stats_tracker = StatsTracker(world=self.world, account_id=account_id)
        return self.stats_tracker

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


    def _update_state_from_html(
        self, html: str, url: str = "", requested_village_id: Optional[int] = None
    ) -> None:
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
        valid_vills = {
            v_id: v_data for v_id, v_data in all_vills.items()
            if v_id > 0 and not (v_data.x == 0 and v_data.y == 0 and v_data.name.lower() in ("farm", "fazenda"))
        }

        # Se game_data trouxer a lista estrita de aldeias do jogador, purga chaves obsoletas
        if game_data and isinstance(game_data.get("player"), dict):
            p_villages = game_data["player"].get("villages")
            if isinstance(p_villages, dict) and p_villages:
                valid_ids = {int(k) for k in p_villages.keys() if str(k).isdigit() and int(k) > 0}
                if village and village.id > 0:
                    valid_ids.add(village.id)
                stale_ids = [vid for vid in self.villages if vid not in valid_ids]
                for sid in stale_ids:
                    del self.villages[sid]

        for v_id, v_data in valid_vills.items():
            if v_id not in self.villages:
                self.villages[v_id] = v_data
            else:
                # Preserva recursos, tropas e edifícios já conhecidos
                curr_res = self.villages[v_id].resources
                curr_troops = self.villages[v_id].troops
                curr_blds = self.villages[v_id].buildings
                self.villages[v_id] = v_data
                self.villages[v_id].resources = curr_res
                self.villages[v_id].troops = curr_troops
                self.villages[v_id].buildings = curr_blds

        # Remove qualquer entrada inválida remanescente com id <= 0 ou nome de edifício corrompido
        for invalid_id in [k for k, v in self.villages.items() if k <= 0 or (v.x == 0 and v.y == 0 and v.name.lower() in ("farm", "fazenda"))]:
            del self.villages[invalid_id]

        # Identifica a aldeia que foi renderizada na resposta HTML
        rendered_village_id = village.id if village else (requested_village_id or self.current_village_id)

        if village:
            if village.id not in self.villages:
                self.villages[village.id] = village

            # Só altera current_village_id se não estiver definido ou se a requisição não foi para outra aldeia específica
            if self.current_village_id is None or requested_village_id is None or requested_village_id == self.current_village_id:
                self.current_village_id = village.id

        # 3. Atualização dos Recursos da aldeia renderizada
        if rendered_village_id:
            res = extract_resources(html, game_data)
            if rendered_village_id in self.villages:
                self.villages[rendered_village_id].resources = res

        # 4. Atualização das Tropas disponíveis na aldeia renderizada
        if rendered_village_id and rendered_village_id in self.villages:
            try:
                units = parse_available_units(html)
                if any(units.values()):
                    self.villages[rendered_village_id].troops = units
            except Exception as e:
                logger.debug(f"Falha ao extrair tropas disponíveis na aldeia {rendered_village_id}: {e}")

        # 5. Atualização dos Níveis de Edifícios da aldeia renderizada
        if rendered_village_id and rendered_village_id in self.villages:
            try:
                blds = parse_building_levels(html, game_data)
                if blds:
                    self.villages[rendered_village_id].buildings.update(blds)
            except Exception as e:
                logger.debug(f"Falha ao extrair níveis de edifícios na aldeia {rendered_village_id}: {e}")


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
        mode: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Navega até um ecrã do jogo (ex.: 'screen=main', 'screen=place', 'screen=barracks')
        assegurando sempre 'page=mobile' e parâmetros de identificação.
        Emite logs detalhados e telemetria de cada requisição.
        """
        if apply_jitter:
            await asyncio.sleep(get_click_jitter())

        async with self._lock:
            if self._session is None:
                await self.init_session()

            self._req_counter += 1
            req_id = self._req_counter

            v_id = village_id or self.current_village_id
            params: Dict[str, Any] = {
                "screen": screen,
                "page": "mobile",
            }
            if mode:
                params["mode"] = mode
            if kwargs:
                params.update(kwargs)
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

            attempt = 0
            response = None
            start_t = time.monotonic()

            while attempt < self.max_network_retries:
                attempt += 1
                req_start_t = time.monotonic()
                try:
                    response = await self.session.get(
                        self.base_url,
                        params=params,
                    )
                    break
                except Exception as e:
                    duration_ms = (time.monotonic() - req_start_t) * 1000
                    if attempt < self.max_network_retries:
                        backoff = self.retry_backoff_base * (1.5 ** (attempt - 1))
                        logger.warning(
                            f"[{self.world}] ⚠️ [REDE] Falha de conexão ao obter screen '{screen}' ({e}). "
                            f"Tentativa {attempt}/{self.max_network_retries}. A restabelecer sessão e retentar em {backoff:.1f}s..."
                        )
                        try:
                            if self._session is not None:
                                await self._session.close()
                        except Exception:
                            pass
                        self._session = None
                        await self.init_session()
                        await asyncio.sleep(backoff)
                    else:
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
                        logger.error(
                            f"[{self.world}] ❌ [REQ #{req_id}] Erro de conexão após {self.max_network_retries} tentativas ao obter screen '{screen}': {e}"
                        )
                        raise NetworkTimeoutError(f"Falha de conexão persistente com {self.host}: {e}") from e

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
            self._update_state_from_html(html, str(response.url), requested_village_id=village_id)
            return html

    async def post_action(
        self,
        screen: str,
        action: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        village_id: Optional[int] = None,
        extra_params: Optional[Dict[str, Any]] = None,
        apply_jitter: bool = True,
        mode: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Executa uma ação HTTP POST (ex.: enviar ataque, colocar edifício na fila),
        injetando automaticamente o token CSRF ('h') obrigatório e 'page=mobile'.
        Emite logs detalhados e telemetria da requisição.
        """
        if apply_jitter:
            await asyncio.sleep(get_click_jitter())

        async with self._lock:
            if self._session is None:
                await self.init_session()

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
            if mode:
                params["mode"] = mode
            if kwargs:
                params.update(kwargs)
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

            attempt = 0
            response = None
            start_t = time.monotonic()

            while attempt < self.max_network_retries:
                attempt += 1
                req_start_t = time.monotonic()
                try:
                    response = await self.session.post(
                        self.base_url,
                        params=params,
                        data=post_data,
                        headers=headers,
                    )
                    break
                except Exception as e:
                    duration_ms = (time.monotonic() - req_start_t) * 1000
                    if attempt < self.max_network_retries:
                        backoff = self.retry_backoff_base * (1.5 ** (attempt - 1))
                        logger.warning(
                            f"[{self.world}] ⚠️ [REDE] Falha de conexão na ação '{action}' ({e}). "
                            f"Tentativa {attempt}/{self.max_network_retries}. A restabelecer sessão e retentar em {backoff:.1f}s..."
                        )
                        try:
                            if self._session is not None:
                                await self._session.close()
                        except Exception:
                            pass
                        self._session = None
                        await self.init_session()
                        await asyncio.sleep(backoff)
                    else:
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
                        logger.error(
                            f"[{self.world}] ❌ [REQ #{req_id}] Erro de conexão após {self.max_network_retries} tentativas na ação '{action}': {e}"
                        )
                        raise NetworkTimeoutError(f"Falha de rede persistente ao enviar ação {action}: {e}") from e

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
            self._update_state_from_html(html, str(response.url), requested_village_id=village_id)
            return html

    async def _refresh_state_internal(self) -> None:
        """Atualização interna sem bloqueio extra de lock."""
        if self._session is None:
            await self.init_session()

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
        v_id = village_id or self.current_village_id
        await self.get_screen("main", village_id=v_id, apply_jitter=False)
        if not self.current_village:
            raise ActionFailedError("Não foi possível carregar as informações da aldeia.")
        return self.current_village

    async def switch_village(self, village_id: int) -> VillageData:
        """
        Alterna o contexto ativo para uma aldeia específica do jogador.
        Atualiza recursos e edifícios da aldeia selecionada.
        """
        logger.info(f"[{self.world}] A alternar contexto ativo para aldeia {village_id}...")
        self.current_village_id = village_id
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

    async def fetch_all_villages_overview(self) -> Dict[int, VillageData]:
        """
        Consulta o ecrã 'overview_villages' (modo produção) para extrair em lote
        todas as aldeias da conta e respetivos recursos, armazém e população.
        """
        try:
            html = await self.get_screen(
                "overview_villages",
                extra_params={"mode": "prod"},
                apply_jitter=False,
            )
            overview_vills = parse_overview_villages(html)
            if overview_vills:
                for vid, vdata in overview_vills.items():
                    if vid in self.villages:
                        if vdata.name:
                            self.villages[vid].name = vdata.name
                        if vdata.x and vdata.y:
                            self.villages[vid].x = vdata.x
                            self.villages[vid].y = vdata.y
                        if vdata.points:
                            self.villages[vid].points = vdata.points
                        self.villages[vid].resources = vdata.resources
                    else:
                        self.villages[vid] = vdata
                logger.info(
                    f"[{self.world}] Sincronizadas {len(overview_vills)} aldeias via overview_villages."
                )
        except Exception as e:
            logger.debug(f"[{self.world}] overview_villages indisponível ou suavemente falhada: {e}")
        return self.villages

    async def discover_active_worlds(self) -> List[str]:
        """
        Consulta o portal oficial do jogo para detetar quais mundos
        o utilizador possui conta e aldeias criadas.
        """
        portal_url = f"https://{self.domain}/page/play"
        discovered = [self.world]
        try:
            async with self._lock:
                if self._session is None:
                    await self.init_session()
                resp = await self.session.get(portal_url)
                if resp.status_code == 200:
                    found = extract_player_worlds(resp.text, domain=self.domain)
                    for w in found:
                        if w not in discovered:
                            discovered.append(w)
        except Exception as e:
            logger.debug(f"[{self.world}] Falha suave ao descobrir mundos da conta: {e}")
        return discovered

