"""
Tribal Wars Mobile Automation Engine - Desktop Launcher
Inicializa o motor Sidecar e abre a janela desktop nativa via Edge WebView2 (pywebview).
Compatível com Windows 10/11 sem necessidade de compilação em Rust.
"""

import argparse
import asyncio
import logging
import os
import sys
import threading
import time
from pathlib import Path

import webview

# Garante que navegações e links no WebView2 abrem dentro da mesma janela e não no browser externo
webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False


# Garante que a raiz do projeto está no sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.config import load_config
from engine.core.account import TribalAccount
from engine.core.scheduler import TaskScheduler
from engine.actions.main_building import MainBuildingManager
from engine.actions.place import PlaceManager
from engine.actions.farm import FarmManager
from engine.actions.recruitment import RecruitmentManager
from engine.api.context import EngineContext
from engine.api.server import start_sidecar_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("TribalDesktop")


class DesktopJsApi:
    """API Python exposta de forma segura ao JavaScript da janela Edge WebView2."""

    def __init__(self, on_finish_callback=None):
        self._on_finish_callback = on_finish_callback

    def finish_login(self):
        """Disparado pelo botão do banner quando o utilizador conclui o login."""
        logger.info("Botão 'Concluir Login' acionado no banner.")
        if self._on_finish_callback:
            self._on_finish_callback()



class DesktopApp:
    """Orquestrador do motor em background e da janela nativa WebView2."""


    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self.host = host
        self.port = port
        self.loop: asyncio.AbstractEventLoop = None
        self.engine_thread: threading.Thread = None
        self.server = None
        self.context = None
        self.window = None
        self.is_logging_in = False
        self.is_running = True


    def start_background_engine(self):
        """Executa o event loop assíncrono do motor numa thread dedicada."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def _run():
            cfg = load_config()
            scheduler = TaskScheduler()
            account = None

            if cfg.sid and cfg.sid.strip():
                account = TribalAccount(
                    world=cfg.world,
                    sid=cfg.sid,
                    domain=cfg.domain,
                    proxy=cfg.proxy,
                )
                try:
                    await account.init_session()
                except Exception as e:
                    logger.warning(f"Sessão não pôde ser inicializada no arranque: {e}")

            mb_mgr = MainBuildingManager(default_max_queue=cfg.building.max_queue)
            place_mgr = PlaceManager()
            farm_mgr = FarmManager()
            recruit_mgr = RecruitmentManager()

            # Agenda rotinas ativas
            if account and cfg.building.template:
                build_plan = cfg.get_active_build_plan()
                mb_mgr.schedule_auto_build(
                    scheduler=scheduler,
                    account=account,
                    plan=build_plan,
                    max_queue=cfg.building.max_queue,
                    interval_seconds=cfg.building.interval_seconds,
                )

            if account and cfg.farm.enabled:
                farm_mgr.schedule_auto_farm(
                    scheduler=scheduler,
                    account=account,
                    farm_config=cfg.farm,
                )

            if account and cfg.recruitment.enabled:
                recruit_mgr.schedule_auto_recruit(
                    scheduler=scheduler,
                    account=account,
                    recruit_config=cfg.recruitment,
                )

            # Agendamento do Keep-Alive para manter a sessão sempre ativa
            if account and cfg.auth.keep_alive:
                from engine.core.models import TaskPriority

                async def keep_alive_task():
                    try:
                        if account and account.sid:
                            await account.refresh_state()
                            logger.debug(f"[{cfg.world}] Pulso de Keep-Alive executado com sucesso.")
                    except Exception as e:
                        logger.debug(f"[{cfg.world}] Aviso no pulso de Keep-Alive: {e}")
                    finally:
                        scheduler.schedule_human_like(
                            name="SessionKeepAlive",
                            priority=TaskPriority.BACKGROUND,
                            action=keep_alive_task,
                            base_delay=cfg.auth.keep_alive_interval_minutes * 60.0,
                            jitter_sigma=30.0,
                        )

                scheduler.schedule(
                    name="SessionKeepAlive",
                    priority=TaskPriority.BACKGROUND,
                    action=keep_alive_task,
                    delay_seconds=cfg.auth.keep_alive_interval_minutes * 60.0,
                )
                logger.info(f"Keep-Alive de sessão ativado a cada ~{cfg.auth.keep_alive_interval_minutes:.0f}min.")

            # Inicia scheduler
            scheduler.start()


            # Cria Contexto Sidecar
            self.context = EngineContext(
                scheduler=scheduler,
                config=cfg,
                account=account,
            )
            self.context.on_renew_session = self.navigate_to_login

            # Inicia Servidor FastAPI
            self.server = await start_sidecar_server(
                context=self.context,
                host=self.host,
                port=self.port,
            )

            logger.info("Motor Sidecar a correr em segundo plano.")
            await self.server.serve()

        try:
            self.loop.run_until_complete(_run())
        except Exception as e:
            logger.error(f"Exceção no motor em background: {e}")

    def navigate_to_login(self):
        """Redireciona a janela atual para a página de login do Tribal Wars."""
        if not self.window:
            logger.warning("Janela desktop ainda não inicializada.")
            return
        target_url = f"https://www.{self.context.config.domain}/"
        logger.info(f"A navegar janela desktop para login: {target_url}")
        self.is_logging_in = True
        try:
            self.window.load_url(target_url)
        except Exception as e:
            logger.error(f"Erro ao carregar URL de login: {e}")
        threading.Thread(target=self._monitor_login_success, daemon=True).start()

    def _js_safe(self, script: str, default=""):
        """
        Executa JavaScript de forma segura a partir de qualquer thread.
        evaluate_js() é o único método WebView2 thread-safe em pywebview.
        """
        try:
            result = self.window.evaluate_js(script)
            return result if result is not None else default
        except Exception:
            return default

    def _inject_login_banner(self):
        """Injeta um banner flutuante no topo do ecrã de login com instruções para o utilizador."""
        banner_js = """
        (function() {
            if (document.getElementById('tw-bot-banner')) return;
            var d = document.createElement('div');
            d.id = 'tw-bot-banner';
            d.style.cssText = 'position:fixed;top:0;left:0;right:0;background:linear-gradient(135deg,#0d1117,#161b22);color:#58a6ff;padding:10px 20px;z-index:2147483647;text-align:center;font-family:Arial,sans-serif;font-size:14px;box-shadow:0 2px 12px rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;gap:15px;border-bottom:2px solid #58a6ff;';
            d.innerHTML = '<span>\uD83D\uDD11 <b>TribalWars Bot:</b> Fa\u00E7a login e entre no mundo.</span> <button id="tw-bot-finish-btn" style="background:#238636;color:#fff;border:none;border-radius:4px;padding:4px 12px;font-weight:bold;cursor:pointer;">Entrei no Jogo \u2192</button>';
            document.body.prepend(d);
            var btn = document.getElementById('tw-bot-finish-btn');
            if (btn) {
                btn.onclick = function() {
                    if (window.pywebview && window.pywebview.api && window.pywebview.api.finish_login) {
                        window.pywebview.api.finish_login();
                    }
                };
            }
        })();
        """
        self._js_safe(banner_js)

    def _monitor_login_success(self):
        """
        Monitoriza a sessão enquanto o utilizador efetua o login manualmente no ecrã.
        Assim que a entrada no jogo (game.php) é detetada, captura o cookie 'sid' e regressa ao Cockpit.
        """
        logger.info("Aguardando login manual do utilizador no ecrã do Tribal Wars...")

        # Aguarda a página de login carregar antes de injetar o banner
        time.sleep(3.0)
        self._inject_login_banner()

        start_t = time.time()
        last_url = ""
        while time.time() - start_t < 300 and self.is_logging_in and self.is_running:
            time.sleep(1.5)

            # evaluate_js() é o ÚNICO método WebView2 seguro de chamar fora da UI thread.
            # get_current_url() e get_cookies() causam crash (E_NOINTERFACE / UI thread only).
            curr_url = self._js_safe("window.location.href")

            # Loga mudanças de URL para diagnóstico
            if curr_url and curr_url != last_url:
                logger.info(f"[Login] Navegação detetada: {curr_url[:80]}")
                last_url = curr_url
                time.sleep(0.5)
                self._inject_login_banner()

            # Deteção: o utilizador entrou no jogo
            is_in_game = (
                "game.php" in curr_url
                or "page/play" in curr_url
                or ("/game" in curr_url and "screen=" in curr_url)
            )

            if not is_in_game:
                continue

            logger.info(f"[Login] Entrada no jogo detetada! URL: {curr_url[:80]}")

            # Aguarda estabilização dos cookies
            time.sleep(2.0)

            # Captura o SID via document.cookie (via JS, thread-safe)
            sid = self._extract_sid_via_js()

            if not sid:
                logger.warning("[Login] Entrada no jogo detetada mas SID não encontrado. A tentar novamente em 3s...")
                time.sleep(3.0)
                continue

            # SID capturado com sucesso!
            self._finalize_login(sid)
            break

        if self.is_logging_in:
            logger.warning("[Login] Tempo limite de 5 minutos atingido sem detetar login.")
            self.is_logging_in = False

    def _extract_sid_via_js(self) -> str:
        """
        Lê o SID dos cookies via JavaScript (thread-safe).
        Nota: document.cookie não expõe cookies HttpOnly — mas o Tribal Wars
        também guarda o sid em localStorage/sessionStorage ou como cookie acessível.
        Tenta múltiplas fontes.
        """
        # Tenta localStorage (algumas versões do Tribal Wars)
        sid = self._js_safe("window.localStorage ? (window.localStorage.getItem('sid') || '') : ''")
        if sid and len(sid) > 5:
            logger.info(f"[Login] SID capturado via localStorage: {sid[:12]}...")
            return sid

        # Tenta document.cookie
        raw_cookie = self._js_safe("document.cookie")
        if raw_cookie:
            for part in raw_cookie.split(";"):
                kv = part.strip()
                if kv.startswith("sid="):
                    sid = kv[4:].strip()
                    if sid:
                        logger.info(f"[Login] SID capturado via document.cookie: {sid[:12]}...")
                        return sid

        # Tenta extrair da URL (alguns servidores passam sid como query param)
        curr_url = self._js_safe("window.location.href")
        if "sid=" in curr_url:
            for part in curr_url.split("&"):
                if part.startswith("sid=") or "?sid=" in part:
                    sid = part.split("sid=")[-1].split("&")[0].strip()
                    if sid:
                        logger.info(f"[Login] SID capturado via URL param: {sid[:12]}...")
                        return sid

        logger.warning("[Login] SID não encontrado (HttpOnly — não acessível via JS). A tentar reler config...")
        # Último recurso: reler o config.json que pode já ter o SID (e.g. se o utilizador o colocou manualmente)
        try:
            from engine.config import load_config
            cfg = load_config()
            if cfg.sid and len(cfg.sid) > 5:
                logger.info(f"[Login] SID lido do config: {cfg.sid[:12]}...")
                return cfg.sid
        except Exception:
            pass
        return ""

    def _finalize_login(self, sid: str):
        """Grava o SID capturado, re-inicializa a conta e regressa ao Cockpit."""
        logger.info(f"✅ Login manual concluído com sucesso! SID: {sid[:12]}...")

        from engine.config.settings import save_config_sid
        save_config_sid(sid)

        if self.context.account:
            self.context.account.sid = sid
            asyncio.run_coroutine_threadsafe(
                self.context.account.init_session(), self.loop
            )
            asyncio.run_coroutine_threadsafe(
                self.context.account.refresh_state(), self.loop
            )
        else:
            # Cria a conta pela primeira vez se ainda não existia
            cfg = self.context.config
            account = TribalAccount(
                world=cfg.world,
                sid=sid,
                domain=cfg.domain,
                proxy=cfg.proxy,
            )
            self.context.account = account
            asyncio.run_coroutine_threadsafe(
                account.init_session(), self.loop
            )

        self.is_logging_in = False
        time.sleep(1.5)
        cockpit_url = f"http://{self.host}:{self.port}/"
        logger.info(f"A regressar ao Cockpit: {cockpit_url}")
        self.window.load_url(cockpit_url)

    def on_login_finished(self):
        """Chamado pela DesktopJsApi quando o utilizador clica no botão do banner."""
        if not self.is_logging_in:
            return
        threading.Thread(target=self._manual_capture_and_finalize, daemon=True).start()

    def _manual_capture_and_finalize(self):
        """Captura o SID e finaliza o login quando disparado manualmente pelo botão do banner."""
        sid = self._extract_sid_via_js()
        if sid:
            self._finalize_login(sid)
        else:
            logger.warning("[Login] Botão acionado mas SID não encontrado.")



    def run(self):
        """Inicia a thread do motor e a janela nativa pywebview."""
        self.engine_thread = threading.Thread(target=self.start_background_engine, daemon=True)
        self.engine_thread.start()

        # Aguarda ativamente até que o servidor local esteja a responder
        import urllib.request
        logger.info(f"A aguardar inicialização do servidor em http://{self.host}:{self.port}...")
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"http://{self.host}:{self.port}/api/health", timeout=1) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                time.sleep(0.15)

        window_url = f"http://{self.host}:{self.port}/"
        logger.info(f"A abrir janela desktop nativa: {window_url}")

        self.js_api = DesktopJsApi(on_finish_callback=self.on_login_finished)
        self.window = webview.create_window(
            title="TribalWars Bot Cockpit - v2.0",
            url=window_url,
            width=1280,
            height=820,
            min_size=(960, 600),
            background_color="#090d16",
            text_select=True,
            js_api=self.js_api,
        )


        def on_closed():
            logger.info("Janela desktop fechada. A encerrar motor...")
            self.is_running = False
            self.is_logging_in = False
            auth_file = Path(".sidecar_auth.json")
            if auth_file.exists():
                try:
                    auth_file.unlink()
                except Exception:
                    pass

        self.window.events.closed += on_closed

        # Inicia o loop de interface gráfica nativa Edge WebView2
        webview.start(debug=False)



def main():
    parser = argparse.ArgumentParser(description="TribalWars Bot Desktop Application")
    parser.add_argument("--port", type=int, default=8000, help="Porta do Sidecar (padrão: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host do Sidecar")
    args = parser.parse_args()

    app = DesktopApp(host=args.host, port=args.port)
    app.run()


if __name__ == "__main__":
    main()
