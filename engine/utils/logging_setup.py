"""
Tribal Wars Bot - Production Logging Setup
Configuração silenciosa de logging com rotação em AppData e remoção de handlers de consola.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from engine.utils.paths import get_app_log_dir


def setup_production_logging(
    app_name: str = "TribalWarsBot",
    level: int = logging.INFO,
    silent_console: Optional[bool] = None,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 3,
) -> Path:
    """
    Configura o sistema de logging para produção:
    - Armazena logs num RotatingFileHandler em %APPDATA%/<app_name>/logs/tribalwars_bot.log
    - Remove StreamHandlers (saída de ecrã/consola) se em modo standalone (frozen) ou silent_console=True
    - Retorna o caminho do ficheiro de log ativo
    """
    is_frozen = getattr(sys, "frozen", False)
    if silent_console is None:
        silent_console = is_frozen

    log_dir = get_app_log_dir(app_name)
    log_file = log_dir / "tribalwars_bot.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 1. Se estiver em modo executável (silent_console=True), remove handlers de consola
    if silent_console:
        for handler in list(root_logger.handlers):
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler):
                root_logger.removeHandler(handler)
    else:
        # Em modo desenvolvimento, assegura que existe um StreamHandler na consola
        has_console_handler = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
            for h in root_logger.handlers
        )
        if not has_console_handler:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_formatter = logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
                datefmt="%H:%M:%S",
            )
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)

    # 2. Verifica se já existe um RotatingFileHandler para este ficheiro
    has_file_handler = False
    for handler in root_logger.handlers:
        if isinstance(handler, RotatingFileHandler) and getattr(handler, "baseFilename", None) == str(log_file):
            has_file_handler = True
            break

    if not has_file_handler:
        try:
            file_handler = RotatingFileHandler(
                filename=str(log_file),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            formatter = logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level)
            root_logger.addHandler(file_handler)
        except Exception as e:
            # Fallback caso haja restrição de escrita
            pass

    return log_file
