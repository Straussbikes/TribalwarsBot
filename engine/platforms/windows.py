"""
Tribal Wars Mobile Automation Engine - Windows Platform Adapter
Implementação especializada para Windows 10/11 com motor Microsoft Edge WebView2.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

import webview

from engine.platforms.base import BasePlatformAdapter

logger = logging.getLogger(__name__)


class WindowsPlatformAdapter(BasePlatformAdapter):
    """
    Adaptador de plataforma para sistemas Microsoft Windows (win32).
    Aproveita o motor Edge WebView2 (Chromium) e suporte a interceptação de eventos de rede.
    """

    @property
    def platform_name(self) -> str:
        return "windows"

    @property
    def gui_backend(self) -> str:
        return "edgechromium"

    def configure_webview_settings(self) -> None:
        """
        No Windows, as janelas e links podem ser mantidos dentro da mesma janela Edge WebView2.
        """
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
        logger.debug("[WindowsPlatform] Definições de WebView configuradas para Edge WebView2.")

    def setup_network_interception(
        self,
        window: Any,
        on_cookie_header: Callable[[str], None],
    ) -> None:
        """
        No Windows Edge WebView2, registra listeners de requisição/resposta HTTP
        para interceptar cookies 'sid' (incluindo HttpOnly) diretamente dos cabeçalhos.
        """
        if not hasattr(window, "events"):
            return

        def on_request_sent(request):
            headers = getattr(request, "headers", {}) or {}
            for k, v in headers.items():
                if str(k).lower() == "cookie" and "sid=" in str(v):
                    on_cookie_header(str(v))

        def on_response_received(response):
            headers = getattr(response, "headers", {}) or {}
            for k, v in headers.items():
                if str(k).lower() == "set-cookie" and "sid=" in str(v):
                    on_cookie_header(str(v))

        try:
            window.events.request_sent += on_request_sent
            window.events.response_received += on_response_received
            logger.debug("[WindowsPlatform] Interceptores de cabeçalhos de rede registados com sucesso.")
        except Exception as e:
            logger.warning(f"[WindowsPlatform] Não foi possível registar interceptores de rede: {e}")
