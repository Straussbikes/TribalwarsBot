"""
Tribal Wars Mobile Automation Engine - Authentication & Session Renewal Manager
Gerencia a autenticação automática e renovação de cookies 'sid' via Edge WebView2 (pywebview).
Suporta extração transparente de cookies, injeção de credenciais e modo interativo com 1-clique.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from urllib.parse import unquote

import webview

if TYPE_CHECKING:
    from engine.config.settings import BotConfig

logger = logging.getLogger(__name__)



def extract_sid_from_cookies(cookies: Union[List[Any], Dict[str, Any]]) -> Optional[str]:
    """
    Extrai com segurança o valor do cookie 'sid' de uma lista de SimpleCookies,
    dicionários ou strings do WebView2.
    """
    if not cookies:
        return None

    # Caso 1: Dicionário simples {"sid": "val", ...}
    if isinstance(cookies, dict):
        val = cookies.get("sid")
        if val:
            return clean_sid_value(str(val))

    # Caso 2: Lista de objetos SimpleCookie ou dicts retornados por window.get_cookies()
    if isinstance(cookies, list):
        for c in cookies:
            # SimpleCookie
            if hasattr(c, "key") and c.key == "sid":
                return clean_sid_value(c.value)
            # Dict
            if isinstance(c, dict) and c.get("name") == "sid":
                return clean_sid_value(c.get("value", ""))
            # String bruta "sid=xxx"
            c_str = str(c)
            if "sid=" in c_str:
                for part in c_str.split(";"):
                    part = part.strip()
                    if part.startswith("sid="):
                        return clean_sid_value(part[4:])
    return None


def clean_sid_value(raw: str) -> str:
    """Normaliza o valor do cookie 'sid', decodificando URLs caso necessário."""
    cleaned = raw.strip().strip("'\"")
    # Trata caso esteja codificado em percentual (ex: 0%3A...)
    if "%3A" in cleaned or "%20" in cleaned:
        try:
            cleaned = unquote(cleaned)
        except Exception as e:
            logger.debug(f"Falha ao decodificar SID percentual: {e}")
    return cleaned


class TribalAuthManager:
    """
    Controlador de autenticação automática e renovação de sessões.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("config.json")
        self._is_authenticating = False

    def perform_webview_login(
        self,
        world: str = "pt117",
        username: str = "",
        password: str = "",
        domain: str = "tribalwars.com.pt",
        timeout_seconds: float = 60.0,
        hidden: bool = False,
    ) -> Optional[str]:
        """
        Abre a WebView nativa do Edge para autenticar no Tribal Wars.
        Se credenciais forem fornecidas, tenta preencher e submeter o formulário automaticamente.
        """
        if self._is_authenticating:
            logger.warning("Já existe um processo de autenticação ativo em curso.")
            return None

        self._is_authenticating = True
        target_url = f"https://www.{domain}/"
        found_sid = None
        start_time = time.time()

        from engine.platforms import get_platform_adapter
        platform = get_platform_adapter()
        platform.configure_webview_settings()

        logger.info(f"A iniciar autenticação via {platform.platform_name}/{platform.gui_backend} ({target_url})...")

        def _monitor_auth(window):
            nonlocal found_sid
            # Script de injeção automática de credenciais (se fornecidas)
            if username and password:
                # Aguarda 1.5s para a página carregar o DOM
                time.sleep(1.5)
                inject_js = f"""
                (function() {{
                    var u = document.getElementById('user');
                    var p = document.getElementById('password');
                    if (u && p) {{
                        u.value = '{username}';
                        p.value = '{password}';
                        var btn = document.querySelector('.btn-login');
                        if (btn) {{
                            btn.click();
                        }}
                    }}
                }})();
                """
                try:
                    window.evaluate_js(inject_js)
                    logger.info("Credenciais injetadas automaticamente no formulário de login.")
                except Exception as e:
                    logger.debug(f"Erro ao injetar credenciais JS: {e}")

            # Loop de monitorização de cookies
            while time.time() - start_time < timeout_seconds:
                time.sleep(1.0)
                try:
                    current_cookies = platform.extract_cookies(window)
                    sid = extract_sid_from_cookies(current_cookies)
                    if sid:
                        logger.info("✅ Cookie 'sid' capturado com sucesso a partir da sessão WebView!")
                        found_sid = sid
                        from engine.config.settings import save_config_sid
                        save_config_sid(sid, self.config_path)
                        # Dá um breve instante para o cookie consolidar e fecha
                        time.sleep(0.8)
                        window.destroy()
                        break
                except Exception as e:
                    logger.debug(f"Erro na leitura periódica de cookies: {e}")

            if not found_sid:
                logger.warning(f"Tempo limite excedido na autenticação via {platform.gui_backend} sem captura de 'sid'.")
                try:
                    window.destroy()
                except Exception as e:
                    logger.debug(f"Aviso ao fechar janela de autenticação: {e}")

        try:
            window = webview.create_window(
                title=f"TribalWars - Autenticação ({world.upper()})",
                url=target_url,
                width=1000,
                height=700,
                min_size=(800, 600),
                background_color="#090d16",
                hidden=hidden and bool(username and password),
            )
            webview.start(_monitor_auth, window)
        finally:
            self._is_authenticating = False

        return found_sid

    async def auto_renew_session(
        self,
        account: Any,
        config: BotConfig,
    ) -> bool:
        """
        Renova de forma assíncrona o cookie 'sid' e atualiza a instância TribalAccount.
        """
        logger.info(f"[{account.world}] A iniciar renovação automática de sessão...")
        # Executa o WebView num thread separado para não bloquear o loop asyncio
        new_sid = await asyncio.to_thread(
            self.perform_webview_login,
            world=account.world,
            username=config.auth.username,
            password=config.auth.password,
            domain=config.domain,
            hidden=False,  # Janela visível para o utilizador poder resolver captchas ou ver o processo
        )

        if new_sid:
            account.sid = new_sid
            # Reinicializa a sessão HTTP com os novos cookies
            await account.init_session()
            logger.info(f"[{account.world}] ✅ Sessão renovada com sucesso! Novo SID: {new_sid[:12]}...")
            return True

        logger.error(f"[{account.world}] ❌ Falha ao renovar sessão automaticamente.")
        return False
