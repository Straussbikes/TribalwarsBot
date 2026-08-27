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

            mb_mgr = MainBuildingManager()
            place_mgr = PlaceManager()
            farm_mgr = FarmManager()
            recruit_mgr = RecruitmentManager()

            # Agenda rotinas ativas
            if account and cfg.building.template:
                mb_mgr.schedule_auto_build(
                    scheduler=scheduler,
                    account=account,
                    template_name=cfg.building.template,
                    max_queue=cfg.building.max_queue,
                    interval_seconds=cfg.building.interval_seconds,
                    custom_plan=cfg.building.custom_plan,
                )

            if account and cfg.farm.enabled:
                farm_mgr.schedule_auto_farm(
                    scheduler=scheduler,
                    account=account,
                    interval_minutes=cfg.farm.interval_minutes,
                )

            if account and cfg.recruitment.enabled:
                recruit_mgr.schedule_auto_recruit(
                    scheduler=scheduler,
                    account=account,
                    targets=cfg.recruitment.targets,
                    batch_sizes=cfg.recruitment.batch_sizes,
                    interval_minutes=cfg.recruitment.interval_minutes,
                    min_free_pop=cfg.recruitment.min_free_pop,
                )

            # Inicia scheduler
            await scheduler.start()

            # Cria Contexto Sidecar
            self.context = EngineContext(
                scheduler=scheduler,
                account=account,
                building_manager=mb_mgr,
                place_manager=place_mgr,
                farm_manager=farm_mgr,
                recruitment_manager=recruit_mgr,
                config=cfg,
            )

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

    def run(self):
        """Inicia a thread do motor e a janela nativa pywebview."""
        self.engine_thread = threading.Thread(target=self.start_background_engine, daemon=True)
        self.engine_thread.start()

        # Aguarda 1 segundo para o servidor subir
        time.sleep(1.2)

        window_url = f"http://{self.host}:{self.port}/"
        logger.info(f"A abrir janela desktop nativa: {window_url}")

        window = webview.create_window(
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
            auth_file = Path(".sidecar_auth.json")
            if auth_file.exists():
                try:
                    auth_file.unlink()
                except Exception:
                    pass

        window.events.closed += on_closed

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
