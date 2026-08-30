"""
Tribal Wars Mobile Automation Engine - WebSocket Handler & Log Streaming
Streaming em tempo real de logs, telemetria de aldeia e alertas de captcha para o Tauri v2.
"""

import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from engine.api.auth import TokenVerifier
from engine.api.context import EngineContext

logger = logging.getLogger(__name__)


class WebSocketLogHandler(logging.Handler):
    """
    Handler de logging customizado que interceta mensagens emitidas
    pelos módulos do bot e as transmite instantaneamente via WebSocket para o frontend.
    """

    def __init__(self, context: EngineContext):
        super().__init__()
        self.context = context

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            log_data = {
                "level": record.levelname,
                "logger": record.name,
                "message": msg,
                "timestamp": record.created,
            }
            # Dispara broadcast assíncrono para os clientes WebSocket
            self.context.broadcast_sync("LOG", log_data)
        except Exception:
            self.handleError(record)


def create_websocket_router(context: EngineContext, token_verifier: TokenVerifier) -> APIRouter:
    """Cria o router FastAPI com o endpoint WebSocket '/ws' autenticado."""
    router = APIRouter()

    @router.websocket("/ws")
    async def websocket_endpoint(
        websocket: WebSocket,
        token: Optional[str] = Query(None),
    ):
        # Validação do token de segurança na query string
        if not token or token != token_verifier.valid_token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token inválido")
            return

        await websocket.accept()
        await context.register_websocket(websocket)

        try:
            while True:
                # Ouve mensagens enviadas pelo cliente Tauri (ex.: ping, comandos rápidos)
                data_text = await websocket.receive_text()
                try:
                    msg = json.loads(data_text)
                    action = msg.get("action", "").lower()

                    if action == "ping":
                        await websocket.send_json({"type": "PONG", "timestamp": time.time()})
                    elif action == "pause":
                        context.pause_scheduler()
                    elif action == "resume":
                        context.resume_scheduler()
                    elif action == "refresh_status":
                        await websocket.send_json({
                            "type": "STATUS_UPDATE",
                            "data": context.get_status_dict(),
                        })
                    else:
                        logger.debug(f"Ação WebSocket não reconhecida: {action}")
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            context.unregister_websocket(websocket)
        except Exception as e:
            logger.warning(f"Exceção no loop do WebSocket: {e}")
            context.unregister_websocket(websocket)

    return router
