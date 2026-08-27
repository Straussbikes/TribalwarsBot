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
    except Exception:
        pass

from engine.actions import FarmManager, MainBuildingManager
from engine.config import load_config
from engine.core.account import TribalAccount
from engine.core.exceptions import BotProtectionError, SessionExpiredError
from engine.core.models import TaskPriority
from engine.core.scheduler import TaskScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("TribalEngine")


async def main():
    # Carrega definições do config.json e variáveis de ambiente
    config = load_config()
    world = config.world
    sid = config.sid

    if not sid:
        logger.warning(
            "Cookie 'sid' não configurado (nem em config.json nem via TW_SID). "
            "A executar em modo de demonstração com componentes isolados."
        )

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
        )
        logger.info(
            f"Módulo do Edifício Principal ativado (Template: '{config.building.template}', "
            f"{len(build_plan)} metas, máx fila: {config.building.max_queue})."
        )

        # 3.2. Módulo de Micro-Farming (se ativado no config.json)
        if config.farm.enabled:
            farm_manager = FarmManager()
            farm_manager.schedule_auto_farm(
                scheduler=scheduler,
                account=account,
                farm_config=config.farm,
            )
            logger.info(
                f"Módulo de Micro-Farming ativado (Modo: {config.farm.mode.upper()}, "
                f"Template: {config.farm.template}, a cada ~{config.farm.interval_minutes:.1f}min)."
            )
        else:
            logger.info("Módulo de Micro-Farming desativado no config.json (enabled=false).")

    # 4. Inicia o loop de tarefas do agendador

    scheduler.start()
    logger.info("Motor iniciado. Pressione Ctrl+C para encerrar.")

    try:
        while True:
            await asyncio.sleep(1.0)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("A encerrar motor de forma graciosa...")
    finally:
        await scheduler.stop()
        if sid and "account" in locals():
            await account.close()
        logger.info("Motor encerrado com sucesso.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
