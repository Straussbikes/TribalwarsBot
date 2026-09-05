"""
Tribal Wars Mobile Automation Engine - Main Entrypoint / CLI Runner
Demonstração e orquestração do ciclo de vida da conta e agendador de tarefas.
"""

import asyncio
import logging
import os
import sys
import warnings

# Suprime avisos de depreciação do event loop no Python 3.14/Windows
warnings.filterwarnings("ignore", category=DeprecationWarning)

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception as e:
        logging.debug(f"Aviso ao definir WindowsSelectorEventLoopPolicy: {e}")

import argparse
from pathlib import Path

# Garante que a raiz do projeto está no sys.path mesmo ao invocar 'python engine/main.py'
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.actions import MainBuildingManager, QuestManager, RecruitmentManager
from engine.api import EngineContext, remove_auth_file, start_sidecar_server
from engine.config import load_config
from engine.core.account import TribalAccount
from engine.core.exceptions import BotProtectionError, SessionExpiredError
from engine.core.models import TaskPriority
from engine.core.scheduler import TaskScheduler
from engine.utils.runtime import suppress_console_and_redirect_streams
from engine.utils.logging_setup import setup_production_logging

suppress_console_and_redirect_streams()
setup_production_logging()
logger = logging.getLogger("TribalEngine")


async def main():
    parser = argparse.ArgumentParser(description="Tribal Wars Mobile Automation Engine")
    parser.add_argument("--api", action="store_true", help="Ativa o servidor Sidecar IPC (FastAPI + WebSockets)")
    parser.add_argument("--desktop", "--gui", action="store_true", help="Abre a aplicação desktop nativa com interface visual Edge WebView2")
    parser.add_argument("--port", type=int, default=8000, help="Porta local do servidor API (padrão: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host local do servidor API (padrão: 127.0.0.1)")
    args, _ = parser.parse_known_args()

    # 0. Bootstrap Gatekeeper: Verificação Obrigatória de Conectividade Cloud SQL
    from engine.storage.cloud_db import get_cloud_db
    from engine.storage.token_storage import token_storage

    cloud_db = get_cloud_db()
    logger.info("[Bootstrap Gatekeeper] A validar conectividade com Cloud SQL (PostgreSQL)...")
    try:
        await cloud_db.init_db()
        logger.info("[Bootstrap Gatekeeper] Conectividade com Cloud SQL estabelecida com sucesso.")
    except Exception as e:
        logger.critical(f"❌ [Bootstrap Gatekeeper] FALHA CRÍTICA AO CONECTAR À CLOUD SQL: {e}")
        logger.critical("A aplicação opera estritamente cloud-native e proíbe qualquer execução offline silenciosa.")
        sys.exit(1)

    # Carrega definições em memória ou a partir de variáveis de ambiente
    config = load_config()
    world = config.world
    sid = config.sid

    if not sid:
        saved_token = token_storage.load_token()
        if not saved_token and not args.api:
            logger.critical("❌ [Bootstrap Gatekeeper] Nenhuma sessão ou token Cloud ativo detetado.")
            logger.critical("Inicie a aplicação com a interface gráfica (--gui) ou autentique-se via API.")
            sys.exit(1)

    # 1. Instanciação do motor de agendamento prioritário
    scheduler = TaskScheduler("MainScheduler")

    # 2. Configuração de Handlers de Segurança (Anti-Bot e Sessão)
    async def on_bot_detected(err: BotProtectionError):
        logger.critical("=" * 60)
        logger.critical("⚠️ ALERTA DE SEGURANÇA: DETETADA PROTEÇÃO ANTI-BOT (CAPTCHA)!")
        logger.critical(f"Detalhes: {err.message}")
        logger.critical("O agendador foi pausado automaticamente.")
        logger.critical("Abra a WebView do Tauri ou o navegador para resolver o captcha.")
        logger.critical("=" * 60)

    async def on_session_expired(err: SessionExpiredError):
        logger.critical("=" * 60)
        logger.critical("⚠️ SESSÃO EXPIRADA: O cookie 'sid' já não é válido.")
        logger.critical("=" * 60)

    scheduler.on_bot_protection(on_bot_detected)
    scheduler.on_session_expired(on_session_expired)

    # 3. Inicialização da Conta (se sid disponível)
    if sid:
        account = TribalAccount(
            world=world,
            sid=sid,
            domain=config.domain,
            proxy=config.proxy,
        )
        await account.init_session()

        # Tarefa periódica de atualização de recursos
        async def poll_resources():
            try:
                village = await account.refresh_state()
                res = village.resources
                logger.info(
                    f"[{world}] Aldeia: '{village.name}' ({village.coordinates}) | "
                    f"Madeira: {res.wood} | Argila: {res.stone} | "
                    f"Ferro: {res.iron} | Armazém: {res.storage_max} | Pop Livre: {res.free_pop}"
                )
            except Exception as e:
                logger.error(f"Falha ao atualizar recursos: {e}")
            finally:
                # Reagenda periodicamente para o próximo ciclo
                if scheduler.is_running and not scheduler.is_paused:
                    scheduler.schedule_human_like(
                        name="Poll Recursos",
                        priority=TaskPriority.REFRESH,
                        action=poll_resources,
                        base_seconds=60.0,
                        std_dev=10.0,
                        min_seconds=45.0,
                        max_seconds=90.0,
                    )

        # 1ª Execução de Recursos logo no arranque (após 2s)
        scheduler.schedule(
            name="Poll Recursos Inicial",
            priority=TaskPriority.REFRESH,
            action=poll_resources,
            delay_seconds=2.0,
        )

        # Obtém o plano de construção ativo do config.json
        build_plan = config.get_active_build_plan()
        main_manager = MainBuildingManager(default_max_queue=config.building.max_queue)
        main_manager.schedule_auto_build(
            scheduler=scheduler,
            account=account,
            plan=build_plan,
            max_queue=config.building.max_queue,
            interval_seconds=config.building.interval_seconds,
            bot_config=config,
        )
        logger.info(
            f"Módulo do Edifício Principal ativado (Template: '{config.building.template}', "
            f"{len(build_plan)} metas, máx fila: {config.building.max_queue})."
        )

        # 3.2. Módulo de Recrutamento Militar (se ativado no config.json)
        if config.recruitment.enabled:
            recruit_manager = RecruitmentManager()
            recruit_manager.schedule_auto_recruit(
                scheduler=scheduler,
                account=account,
                recruit_config=config.recruitment,
                bot_config=config,
            )
            logger.info(
                f"Módulo de Recrutamento Militar ativado ({len(config.recruitment.targets)} metas, "
                f"a cada ~{config.recruitment.interval_minutes:.1f}min, min pop: {config.recruitment.min_free_pop})."
            )
        else:
            logger.info("Módulo de Recrutamento Militar desativado no config.json (enabled=false).")

        # 3.4. Módulo de Missões & Bónus Diário (Item 2.10)
        if config.quest.enabled:
            quest_manager = QuestManager()

            async def quest_cycle_task():
                try:
                    logger.debug(f"[{world}] A executar verificação de missões e bónus diário...")
                    res = await quest_manager.run_cycle(
                        account=account,
                        village_id=account.current_village_id,
                        config=config.quest,
                    )
                    if res.get("quests_claimed", 0) > 0:
                        logger.info(f"[{world}] {res['quests_claimed']} missões resgatadas com sucesso.")
                    if res.get("daily_bonus_opened"):
                        logger.info(f"[{world}] Baú diário gratuito aberto com sucesso.")
                except Exception as e:
                    logger.warning(f"[{world}] Falha no ciclo de missões: {e}")
                finally:
                    scheduler.schedule_human_like(
                        name="QuestCycle",
                        priority=TaskPriority.QUEST,
                        action=quest_cycle_task,
                        base_delay=config.quest.interval_minutes * 60.0,
                        jitter_sigma=30.0,
                    )

            scheduler.schedule(
                name="QuestCycleInicial",
                priority=TaskPriority.QUEST,
                action=quest_cycle_task,
                delay_seconds=15.0,
            )
            logger.info(
                f"Módulo de Missões & Bónus Diário ativado "
                f"(a cada ~{config.quest.interval_minutes:.0f}min, uso de inventário apenas manual)."
            )

        # 3.4. Módulo de Manutenção de Sessão (Keep-Alive)
        if config.auth.keep_alive:
            async def keep_alive_task():
                try:
                    if account and account.sid:
                        await account.refresh_state()
                        logger.debug(f"[{world}] Pulso de Keep-Alive executado com sucesso.")
                except Exception as e:
                    logger.debug(f"[{world}] Aviso no pulso de Keep-Alive: {e}")
                finally:
                    scheduler.schedule_human_like(
                        name="SessionKeepAlive",
                        priority=TaskPriority.BACKGROUND,
                        action=keep_alive_task,
                        base_delay=config.auth.keep_alive_interval_minutes * 60.0,
                        jitter_sigma=30.0,
                    )

            scheduler.schedule(
                name="SessionKeepAlive",
                priority=TaskPriority.BACKGROUND,
                action=keep_alive_task,
                delay_seconds=config.auth.keep_alive_interval_minutes * 60.0,
            )
            logger.info(
                f"Módulo de Manutenção de Sessão (Keep-Alive) ativado "
                f"(a cada ~{config.auth.keep_alive_interval_minutes:.0f}min)."
            )


    # 4. Inicializa o Contexto da API Sidecar
    api_server = None
    server_task = None
    auth_file = Path(".sidecar_auth.json")

    context = EngineContext(
        scheduler=scheduler,
        config=config,
        account=account if sid and "account" in locals() else None,
    )

    # Conecta o evento de verificação anti-bot para broadcast imediato via WebSocket
    async def _on_bot_protect_alert(err: BotProtectionError):
        await context.notify_captcha_detected(world=world, html_snippet=err.html_snippet)

    scheduler.on_bot_protection(_on_bot_protect_alert)

    # Inicia o servidor Sidecar se solicitado por argumento CLI (--api) ou variável de ambiente
    if args.api or os.getenv("TW_API") == "1":
        api_server = await start_sidecar_server(
            context=context,
            host=args.host,
            port=args.port,
            auth_file_path=auth_file,
        )
        server_task = asyncio.create_task(api_server.serve())

    # 5. Inicia o loop de tarefas do agendador
    scheduler.start()
    logger.info("Motor iniciado. Pressione Ctrl+C para encerrar.")

    try:
        while True:
            await asyncio.sleep(1.0)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("A encerrar motor de forma graciosa...")
    finally:
        await scheduler.stop()
        if api_server:
            api_server.should_exit = True
            if server_task:
                server_task.cancel()
        remove_auth_file(auth_file)
        if sid and "account" in locals():
            await account.close()
        logger.info("Motor encerrado com sucesso.")



if __name__ == "__main__":
    _parser = argparse.ArgumentParser(description="Tribal Wars Mobile Automation Engine")
    _parser.add_argument("--api", action="store_true", help="Ativa o servidor Sidecar IPC (FastAPI + WebSockets)")
    _parser.add_argument("--desktop", "--gui", dest="desktop", action="store_true", help="Abre a aplicação desktop nativa com interface visual Edge WebView2")
    _parser.add_argument("--port", type=int, default=8000, help="Porta local do servidor API (padrão: 8000)")
    _parser.add_argument("--host", type=str, default="127.0.0.1", help="Host local do servidor API (padrão: 127.0.0.1)")
    _args, _ = _parser.parse_known_args()

    is_frozen = getattr(sys, "frozen", False)
    launch_desktop = getattr(_args, "desktop", False) or (is_frozen and not _args.api)

    if launch_desktop:
        from engine.desktop_launcher import DesktopApp
        app = DesktopApp(host=_args.host, port=_args.port)
        app.run()
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pass

