"""
Tribal Wars Mobile Automation Engine - Linux Platform Adapter
Implementação para distribuições Linux (WebKit2GTK / Qt).
"""

from __future__ import annotations

import logging
from typing import Any, Callable

import webview

from engine.platforms.base import BasePlatformAdapter

logger = logging.getLogger(__name__)


class LinuxPlatformAdapter(BasePlatformAdapter):
    """
    Adaptador de plataforma para sistemas Linux (WebKit2GTK).
    """

    @property
    def platform_name(self) -> str:
        return "linux"

    @property
    def gui_backend(self) -> str:
        return "gtk"

    def configure_webview_settings(self) -> None:
        """Configurações recomendadas para GTK/WebKit2GTK."""
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        logger.debug("[LinuxPlatform] Definições de WebView configuradas para WebKit2GTK.")

    def setup_network_interception(
        self,
        window: Any,
        on_cookie_header: Callable[[str], None],
    ) -> None:
        """No Linux, a leitura de cookies padrão é feita de forma síncrona via get_cookies()."""
        logger.debug("[LinuxPlatform] Gestão de sessão configurada para ambiente Linux.")
