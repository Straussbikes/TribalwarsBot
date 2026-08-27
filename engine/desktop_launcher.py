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

    def _monitor_login_success(self):
        """Monitoriza a sessão até que o utilizador entre no jogo e captura o cookie 'sid'."""
        logger.info("Monitor de login ativo. À espera da entrada no mundo...")
        time.sleep(2.5)
        cfg = self.context.config
        if cfg.auth.username and cfg.auth.password:
            js_fill = f"""
            (function() {{
                var u = document.getElementById('user');
                var p = document.getElementById('password');
                if (u && p && !u.value) {{
                    u.value = '{cfg.auth.username}';
                    p.value = '{cfg.auth.password}';
                    var btn = document.querySelector('.btn-login');
                    if (btn) btn.click();
                }}
            }})();
            """
            try:
                self.window.evaluate_js(js_fill)
                logger.info("Credenciais preenchidas automaticamente no formulário de login.")
            except Exception as e:
                logger.debug(f"Preenchimento JS: {e}")

        start_t = time.time()
        while time.time() - start_t < 180 and self.is_logging_in and self.is_running:
            time.sleep(1.0)
            try:
                curr_url = self.window.get_url() or ""
                cookies = self.window.get_cookies()
                from engine.core.auth_manager import extract_sid_from_cookies
                sid = extract_sid_from_cookies(cookies)

                if "game.php" in curr_url or (sid and "page/play" in curr_url):
                    if sid:
                        logger.info(f"✅ Login concluído! Novo SID capturado: {sid[:12]}...")
                        from engine.config.settings import save_config_sid
                        save_config_sid(sid)

                        if self.context.account:
                            self.context.account.sid = sid
                            asyncio.run_coroutine_threadsafe(
                                self.context.account.init_session(), self.loop
                            )

                        self.is_logging_in = False
                        time.sleep(1.0)
                        cockpit_url = f"http://{self.host}:{self.port}/"
                        logger.info(f"A regressar ao Cockpit: {cockpit_url}")
                        self.window.load_url(cockpit_url)
                        break
            except Exception as e:
                logger.debug(f"Erro no monitor de login: {e}")

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

        self.window = webview.create_window(
            title="TribalWars Bot Cockpit - v2.0",
            url=window_url,
            width=1280,
            height=820,
            min_size=(960, 600),
            background_color="#090d16",
            text_select=True,
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
