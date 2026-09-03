"""
Testes unitários para utilitários de empacotamento, resolução de caminhos, supressão de consola e logging.
"""

import os
import sys
from pathlib import Path
import pytest

from engine.utils.paths import get_base_dir, resource_path, get_app_data_dir, get_app_log_dir
from engine.utils.runtime import suppress_console_and_redirect_streams, SafeStreamWriter
from engine.utils.logging_setup import setup_production_logging


def test_paths_utilities():
    base = get_base_dir()
    assert base.exists()

    frontend = resource_path("frontend")
    assert frontend.exists()
    assert (frontend / "index.html").exists()

    app_data = get_app_data_dir("TribalWarsBotTest")
    assert app_data.exists()

    log_dir = get_app_log_dir("TribalWarsBotTest")
    assert log_dir.exists()


def test_safe_stream_writer():
    logged = []
    writer = SafeStreamWriter(logger_func=lambda msg: logged.append(msg))
    assert writer.writable() is True
    assert writer.readable() is False
    assert writer.isatty() is False

    writer.write("Mensagem de teste\n")
    assert "Mensagem de teste" in logged


def test_suppress_console_and_redirect():
    # Não deve lançar nenhuma exceção
    suppress_console_and_redirect_streams()
    assert sys.stdout is not None
    assert sys.stderr is not None


def test_setup_production_logging():
    log_file = setup_production_logging(app_name="TribalWarsBotTest", silent_console=True)
    assert log_file.parent.exists()
