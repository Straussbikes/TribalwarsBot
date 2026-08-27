"""
Tribal Wars Mobile Automation Engine - macOS Platform Adapter
Implementação especializada para macOS (Cocoa / Apple WebKit).
"""

from __future__ import annotations

import logging
from typing import Any, Callable

import webview

from engine.platforms.base import BasePlatformAdapter

logger = logging.getLogger(__name__)


class MacOSPlatformAdapter(BasePlatformAdapter):
    """
    Adaptador de plataforma para sistemas Apple macOS (darwin).
    Utiliza o motor WebKit nativo via Cocoa (pyobjc).
    """

    @property
    def platform_name(self) -> str:
        return "darwin"

    @property
    def gui_backend(self) -> str:
        return "cocoa"

    def configure_webview_settings(self) -> None:
        """
        No macOS, mantemos OPEN_EXTERNAL_LINKS_IN_BROWSER activo (padrão)
        para garantir que cliques em iframes ou termos externos de captchas não
        substituam a janela do jogo por ecrãs brancos de assets isolados.
        """
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        logger.debug("[MacOSPlatform] Definições de WebView configuradas para WebKit/Cocoa.")

    def setup_network_interception(
        self,
        window: Any,
        on_cookie_header: Callable[[str], None],
    ) -> None:
        """
        No macOS WebKit, regista listeners de rede seguros (response_received) para
        capturar o cabeçalho Set-Cookie / Cookie em tempo real sem afetar requisições POST.
        """
        if not hasattr(window, "events"):
            return

        def on_response_received(response):
            try:
                headers = getattr(response, "headers", {}) or {}
                url = str(getattr(response, "url", "") or "")
                for k, v in headers.items():
                    k_str = str(k).lower()
                    if k_str in ("set-cookie", "cookie") and "sid=" in str(v):
                        logger.info(f"[NetworkInterceptor] SID detetado na resposta HTTP de '{url[:60]}'")
                        on_cookie_header(str(v))
            except Exception as e:
                logger.debug(f"[NetworkInterceptor] Erro no listener on_response_received: {e}")

        window.events.response_received += on_response_received
        logger.info("[MacOSPlatform] Intercetor de respostas de rede (response_received) ativado.")

    def extract_cookies(self, window: Any) -> List[Any]:
        """
        No macOS, extrai cookies diretamente da WKHTTPCookieStore nativa do WebKit
        sem o filtro restritivo de domínio do pywebview.
        """
        try:
            from threading import Semaphore
            from PyObjCTools import AppHelper
            from webview.platforms.cocoa import BrowserView

            i = BrowserView.instances.get(window.uid)
            if i:
                # Atualiza i.url para o URL atual do browser para garantir sincronização
                current_url = self.get_safe_url(window)
                if current_url:
                    i.url = current_url

                if hasattr(i, "datastore"):
                    cookies_list = []
                    sem = Semaphore(0)

                    def _handler(cookies):
                        try:
                            for c in cookies:
                                c_domain = str(c.domain()) if c.domain() else ""
                                cookies_list.append({
                                    "name": str(c.name()),
                                    "value": str(c.value()),
                                    "domain": c_domain,
                                    "path": str(c.path()) if c.path() else "/",
                                    "httponly": bool(c.isHTTPOnly()),
                                    "secure": bool(c.isSecure()),
                                })
                        finally:
                            sem.release()

                    cookie_store = i.datastore.httpCookieStore()
                    AppHelper.callAfter(cookie_store.getAllCookies_, _handler)

                    if sem.acquire(timeout=2.5):
                        if cookies_list:
                            logger.info(f"[MacOSPlatform] {len(cookies_list)} cookies extraídos diretamente da WKHTTPCookieStore nativa.")
                            return cookies_list
        except Exception as e:
            logger.debug(f"[MacOSPlatform] Falha na extração direta de cookies: {e}")

        # Fallback padrão
        return super().extract_cookies(window)
