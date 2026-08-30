"""
Tribal Wars Mobile Automation Engine - Base Platform Adapter
Contrato base para suporte multiplataforma (Windows, macOS, Linux).
"""

from __future__ import annotations

import abc
import logging
from typing import Any, Callable, List

logger = logging.getLogger(__name__)


class BasePlatformAdapter(abc.ABC):
    """
    Interface abstrata para adaptadores de sistema operativo e motor gráfico nativo.
    Garante comportamento uniforme independentemente de rodar em Windows, macOS ou Linux.
    """

    @property
    @abc.abstractmethod
    def platform_name(self) -> str:
        """Nome canónico da plataforma ('windows', 'darwin', 'linux')."""
        pass

    @property
    @abc.abstractmethod
    def gui_backend(self) -> str:
        """Motor webview nativo subjacente ('edgechromium', 'cocoa', 'gtk')."""
        pass

    @abc.abstractmethod
    def configure_webview_settings(self) -> None:
        """
        Aplica configurações globais ao pywebview (webview.settings)
        adequadas às particularidades do motor nativo deste SO.
        """
        pass

    @abc.abstractmethod
    def setup_network_interception(
        self,
        window: Any,
        on_cookie_header: Callable[[str], None],
    ) -> None:
        """
        Configura interceptação de tráfego de rede para captura de cookies HTTP,
        caso o backend nativo da plataforma o suporte de forma segura e estável.
        """
        pass

    def extract_cookies(self, window: Any) -> List[Any]:
        """
        Lê os cookies da sessão ativa na janela de forma segura.
        """
        try:
            cookies = window.get_cookies()
            return cookies if cookies else []
        except Exception as e:
            logger.debug(f"[{self.platform_name}] Falha na leitura nativa de cookies: {e}")
            return []

    def is_captcha_or_asset_hijack(self, url: str) -> bool:
        """
        Verifica se a janela foi indevidamente redirecionada para um asset estático
        ou CDN de captcha (ex.: newassets.hcaptcha.com), o que causaria um ecrã branco.
        """
        if not url:
            return False
        url_lower = url.lower()
        blocked_domains = [
            "newassets.hcaptcha.com",
            "assets.hcaptcha.com",
            "challenges.cloudflare.com",
            "recaptcha/api2",
        ]
        return any(d in url_lower for d in blocked_domains)

    def get_safe_url(self, window: Any, default: str = "") -> str:
        """
        Executa 'window.location.href' de forma protegida através de evaluate_js,
        que é thread-safe em todos os motores suportados.
        """
        try:
            res = window.evaluate_js("window.location.href")
            return str(res) if res is not None else default
        except Exception:
            return default

    def reload_url(self, window: Any, target_url: str) -> None:
        """Carrega ou recarrega um URL na janela nativa."""
        try:
            window.load_url(target_url)
        except Exception as e:
            logger.error(f"[{self.platform_name}] Erro ao navegar para {target_url}: {e}")
