"""
Tribal Wars Bot - Path Resolution Utilities
Resolução segura de caminhos em tempo de execução para binários standalone (PyInstaller) e ambiente de desenvolvimento.
"""

import os
import sys
from pathlib import Path
from typing import Union


def get_base_dir() -> Path:
    """
    Retorna o diretório base da aplicação:
    - Se empacotado pelo PyInstaller (onefile/onedir com _MEIPASS): sys._MEIPASS
    - Se executado via código-fonte: raiz do repositório
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    # Em modo desenvolvimento: raiz do projeto (dois níveis acima de engine/utils)
    return Path(__file__).resolve().parent.parent.parent


def resource_path(relative_path: Union[str, Path]) -> Path:
    """
    Resolve o caminho absoluto para um asset (frontend, templates, ícones, certificados).
    Suporta:
    1. Diretório temporário de extração do PyInstaller (_MEIPASS)
    2. Diretório da distribuição standalone (_internal ou junto ao .exe)
    3. Diretório relativo ao código-fonte em desenvolvimento
    """
    rel = Path(relative_path)
    base = get_base_dir()
    target = base / rel

    if target.exists():
        return target

    # Fallback para execução frozen (PyInstaller onedir: dist/TribalWarsBot/_internal/...)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        internal_target = exe_dir / "_internal" / rel
        if internal_target.exists():
            return internal_target
        direct_target = exe_dir / rel
        if direct_target.exists():
            return direct_target

    # Fallback para o diretório atual de trabalho
    cwd_target = Path.cwd() / rel
    if cwd_target.exists():
        return cwd_target

    return target


def get_app_data_dir(app_name: str = "TribalWarsBot") -> Path:
    """
    Retorna o diretório seguro de dados da aplicação conforme o sistema operativo:
    - Windows: %APPDATA%/<app_name> (ex.: C:\\Users\\user\\AppData\\Roaming\\TribalWarsBot)
    - macOS: ~/Library/Application Support/<app_name>
    - Linux: ~/.config/<app_name>
    Garante a criação do diretório caso não exista.
    """
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        base = Path(app_data) if app_data else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg_config) if xdg_config else Path.home() / ".config"

    target_dir = base / app_name
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def get_app_log_dir(app_name: str = "TribalWarsBot") -> Path:
    """
    Retorna o diretório de logs da aplicação dentro do diretório AppData.
    Garante que a pasta existe.
    """
    log_dir = get_app_data_dir(app_name) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir
