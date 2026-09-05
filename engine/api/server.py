"""
Tribal Wars Mobile Automation Engine - Servidor FastAPI & Sidecar IPC
Fábrica de aplicação FastAPI, configuração de CORS e ciclo de vida assíncrono.
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from engine.api.auth import TokenVerifier, generate_auth_token, write_auth_file
from engine.api.context import EngineContext
from engine.api.routes import create_api_router
from engine.api.websocket import WebSocketLogHandler, create_websocket_router

logger = logging.getLogger(__name__)


def create_app(
    context: EngineContext,
    token: str,
    attach_log_handler: bool = True,
) -> FastAPI:
    """
    Constrói a instância da aplicação FastAPI com todas as rotas REST e WebSocket,
    middleware de CORS para comunicação segura com Tauri v2 e registo do log handler.
    """
    app = FastAPI(
        title="Tribal Wars Automation Engine API",
        version="1.2.0",
        description="Sidecar IPC local para automação e integração com interface gráfica nativa Tauri v2.",
        docs_url="/docs",
        redoc_url=None,
    )

    # 1. Configuração de CORS para permitir acesso exclusivo da shell Tauri e localhost
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1",
            "http://localhost",
            "tauri://localhost",
            "https://tauri.localhost",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Verificador de Token
    token_verifier = TokenVerifier(valid_token=token)


    @app.get("/api/auth-info")
    async def get_auth_info():
        """Fornece o token de autenticação exclusivamente para clientes na interface local."""
        return {
            "token": token,
            "status": "ok",
        }

    # 3. Regista rotas REST e WebSockets
    app.include_router(create_api_router(context, token_verifier))
    app.include_router(create_websocket_router(context, token_verifier))

    # 4. Anexa o handler de logging ao logger principal 'engine'
    if attach_log_handler:
        ws_handler = WebSocketLogHandler(context)
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] (%(name)s) %(message)s")
        ws_handler.setFormatter(formatter)
        ws_handler.setLevel(logging.INFO)

        # Regista no logger raiz do engine
        engine_logger = logging.getLogger("engine")
        engine_logger.addHandler(ws_handler)

        main_logger = logging.getLogger("TribalEngine")
        main_logger.addHandler(ws_handler)

        desktop_logger = logging.getLogger("TribalDesktop")
        desktop_logger.addHandler(ws_handler)

    # 5. Monta a interface estática do Frontend se a pasta existir
    from engine.utils.paths import resource_path
    frontend_dir = resource_path("frontend")

    if frontend_dir.exists() and (frontend_dir / "index.html").exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
        logger.info(f"Interface Web montada com sucesso a partir de: {frontend_dir}")

    return app



async def start_sidecar_server(
    context: EngineContext,
    host: str = "127.0.0.1",
    port: int = 8000,
    token: Optional[str] = None,
    auth_file_path: Optional[Path] = None,
) -> uvicorn.Server:
    """
    Inicia o servidor Uvicorn em segundo plano no event loop assíncrono atual.
    Grava as credenciais em .sidecar_auth.json para o cliente desktop Tauri.
    """
    auth_token = token or generate_auth_token()
    auth_file = auth_file_path or Path(".sidecar_auth.json")

    app = create_app(context, token=auth_token)

    # Grava ficheiro de autenticação local
    write_auth_file(
        file_path=auth_file,
        host=host,
        port=port,
        token=auth_token,
    )

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="warning",  # Silencia logs repetitivos de polling HTTP do uvicorn
        access_log=False,
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    logger.info(f"Servidor Sidecar IPC pronto em http://{host}:{port} (Token: {auth_token[:8]}...)")
    return server
