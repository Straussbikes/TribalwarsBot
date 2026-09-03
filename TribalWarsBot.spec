# -*- mode: python ; coding: utf-8 -*-
"""
Tribal Wars Bot - PyInstaller Build Specification
Configuração de compilação standalone comercial para Windows (GUI pura, sem consola).
"""

from pathlib import Path
import certifi
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

ROOT_DIR = Path('.').resolve()

# 1. Coleta completa de bibliotecas C-extensions e dinâmicas
curl_datas, curl_binaries, curl_hidden = collect_all('curl_cffi')
webview_datas, webview_binaries, webview_hidden = collect_all('webview')
uvicorn_datas, uvicorn_binaries, uvicorn_hidden = collect_all('uvicorn')
asyncpg_datas, asyncpg_binaries, asyncpg_hidden = collect_all('asyncpg')
crypto_datas, crypto_binaries, crypto_hidden = collect_all('cryptography')

# 2. Inclusão de assets estáticos obrigatórios e certificados CA
datas = [
    (str(ROOT_DIR / 'frontend'), 'frontend'),
    (str(ROOT_DIR / 'assets'), 'assets'),
    (certifi.where(), 'certifi'),
] + curl_datas + webview_datas + uvicorn_datas + asyncpg_datas + crypto_datas

# Metadados de pacotes essenciais
datas += copy_metadata('fastapi')
datas += copy_metadata('starlette')
datas += copy_metadata('pydantic')
datas += copy_metadata('curl_cffi')

binaries = curl_binaries + webview_binaries + uvicorn_binaries + asyncpg_binaries + crypto_binaries

# 3. Submódulos e dependências ocultas obrigatórias
hiddenimports = [
    # Engine Core & Ações
    'engine',
    'engine.main',
    'engine.desktop_launcher',
    'engine.utils',
    'engine.utils.paths',
    'engine.utils.runtime',
    'engine.utils.logging_setup',
    'engine.api.server',
    'engine.api.routes',
    'engine.api.websocket',
    'engine.api.context',
    'engine.core.account',
    'engine.core.scheduler',
    'engine.core.auth_handler',
    'engine.core.account_session_manager',
    'engine.core.world_worker_orchestrator',
    'engine.core.profile_manager',
    'engine.core.exceptions',
    'engine.core.models',
    'engine.storage.cloud_db',
    'engine.storage.token_storage',
    'engine.storage.database',
    'engine.storage.world_database',
    'engine.config.settings',
    'engine.config.templates',
    'engine.platforms',
    'engine.platforms.windows',
    'engine.actions.combat_tactics',
    'engine.actions.recruitment',
    'engine.actions.main_building',
    'engine.actions.farm',
    'engine.actions.scavenge',
    'engine.actions.snob',
    'engine.actions.smith',
    'engine.actions.market',
    'engine.actions.quest',
    'engine.actions.defense',
    'engine.actions.map',
    'engine.actions.place',
    'engine.actions.inventory',
    'engine.actions.village_coordinator',
    # Servidor ASGI & Web
    'uvicorn.logging',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.lifespan.on',
    'fastapi',
    'starlette',
    'pydantic',
    'sqlite3',
    'webview.platforms.winforms',
    # Banco de Dados Assíncrono Cloud SQL
    'sqlalchemy',
    'sqlalchemy.dialects.postgresql',
    'sqlalchemy.dialects.postgresql.asyncpg',
    'sqlalchemy.ext.asyncio',
    'asyncpg',
    'asyncpg.pgproto',
    'asyncpg.pgproto.pgproto',
    # Segurança e Criptografia
    'cryptography',
    'cryptography.hazmat.primitives.ciphers.aead',
    'certifi',
    'dotenv',
] + curl_hidden + webview_hidden + uvicorn_hidden + asyncpg_hidden + crypto_hidden

a = Analysis(
    ['engine/main.py'],
    pathex=[str(ROOT_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['test', 'tests', 'pytest', 'tkinter', 'unittest'],
    noarchive=False,
    optimize=1,  # Otimização bytecode (remove asserts)
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TribalWarsBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Desativado para prevenir falsos-positivos de antivírus
    console=False,  # GUI PURA: Janela de consola totalmente suprimida no Windows
    disable_windowed_traceback=True,  # Suprime popups padrão de erro do Windows
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT_DIR / 'assets' / 'icon.ico'),
    version=str(ROOT_DIR / 'file_version_info.txt'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TribalWarsBot',
)
