# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

ROOT_DIR = Path('.').resolve()

# Coleta completa de bibliotecas dinâmicas e C-extensions
curl_datas, curl_binaries, curl_hidden = collect_all('curl_cffi')
webview_datas, webview_binaries, webview_hidden = collect_all('webview')
uvicorn_datas, uvicorn_binaries, uvicorn_hidden = collect_all('uvicorn')

datas = [
    (str(ROOT_DIR / 'frontend'), 'frontend'),
] + curl_datas + webview_datas + uvicorn_datas

binaries = curl_binaries + webview_binaries + uvicorn_binaries

hiddenimports = [
    'engine',
    'engine.main',
    'engine.desktop_launcher',
    'engine.api.server',
    'engine.api.routes',
    'engine.api.websocket',
    'engine.storage.database',
    'engine.storage.world_database',
    'engine.core.account',
    'engine.core.scheduler',
    'engine.core.profile_manager',
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
] + curl_hidden + webview_hidden + uvicorn_hidden

a = Analysis(
    ['engine/main.py'],
    pathex=[str(ROOT_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['test', 'tests', 'pytest'],
    noarchive=False,
    optimize=0,
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
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
