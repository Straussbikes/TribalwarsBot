"""
Tribal Wars Mobile Automation Engine - Main Entrypoint / CLI Runner
Demonstração e orquestração do ciclo de vida da conta e agendador de tarefas.
"""

import asyncio
import logging
import os
import sys

# Configuração do Event Loop específico para Windows e curl_cffi
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

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
    world = os.getenv("TW_WORLD", "pt117")
    sid = os.getenv("TW_SID", "")

    if not sid:
        logger.warning(
            "Cookie 'sid' não fornecido via variável de ambiente TW_SID. "
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
        account = TribalAccount(world=world, sid=sid)
        await account.init_session()

        # Tarefa periódica de atualização de recursos
        async def poll_resources():
            try:
                village = await account.refresh_state()
                res = village.resources
                logger.info(
                    f"[{world}] Recursos atualizados: Madeira: {res.wood} | Argila: {res.stone} | "
                    f"Ferro: {res.iron} | Armazém: {res.storage_max} | Pop Livre: {res.free_pop}"
                )
            except Exception as e:
                logger.error(f"Falha ao atualizar recursos: {e}")

        # Agenda a cada ~60s com delay gaussiano humano
        scheduler.schedule_human_like(
            name="Poll Recursos",
            priority=TaskPriority.REFRESH,
            action=poll_resources,
            base_seconds=60.0,
            std_dev=10.0,
            min_seconds=45.0,
            max_seconds=90.0,
        )

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
