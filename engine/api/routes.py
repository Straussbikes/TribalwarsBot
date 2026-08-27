"""
Tribal Wars Mobile Automation Engine - Rotas REST da API Sidecar
Endpoints para controlo de tarefas, consulta de estado, ações manuais e configuração dinâmica.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from engine.api.auth import TokenVerifier
from engine.api.context import EngineContext

logger = logging.getLogger(__name__)


# --- Modelos Pydantic para Validação de Entrada ---

class ConfigUpdateRequest(BaseModel):
    """Payload de atualização de configurações do bot."""
    world: Optional[str] = None
    sid: Optional[str] = None
    domain: Optional[str] = None
    building: Optional[Dict[str, Any]] = None
    farm: Optional[Dict[str, Any]] = None
    recruitment: Optional[Dict[str, Any]] = None


class ActionResponse(BaseModel):
    """Resposta padrão para chamadas de ação."""
    status: str
    message: Optional[str] = None
    task_id: Optional[str] = None


def create_api_router(context: EngineContext, token_verifier: TokenVerifier) -> APIRouter:
    """Cria e configura o router da API REST protegido por autenticação."""
    router = APIRouter(prefix="/api", dependencies=[Depends(token_verifier.verify)])

    @router.get("/health")
    async def health_check():
        """Verificação básica de vitalidade do processo."""
        return {"status": "ok", "uptime": round(context.uptime_seconds, 1)}

    @router.get("/status")
    async def get_status():
        """Retorna o estado consolidado da conta, agendador, recursos e módulos."""
        return context.get_status_dict()

    @router.get("/config")
    async def get_config():
        """Retorna as configurações atualmente carregadas."""
        return context.get_config_dict()

    @router.post("/config", response_model=ActionResponse)
    async def update_config(payload: ConfigUpdateRequest):
        """Atualiza dinamicamente as opções do bot e persiste no config.json."""
        update_data = payload.model_dump(exclude_unset=True)
        res = context.update_config_and_save(update_data)
        return ActionResponse(status=res["status"], message=res.get("message"))

    @router.post("/scheduler/pause", response_model=ActionResponse)
    async def pause_scheduler():
        """Pausa o agendador de tarefas."""
        res = context.pause_scheduler()
        return ActionResponse(status=res["status"], message=res.get("message"))

    @router.post("/scheduler/resume", response_model=ActionResponse)
    async def resume_scheduler():
        """Retoma o agendador de tarefas."""
        res = context.resume_scheduler()
        return ActionResponse(status=res["status"], message=res.get("message"))

    @router.post("/actions/build/trigger", response_model=ActionResponse)
    async def trigger_build():
        """Dispara um ciclo imediato de evolução de edifícios."""
        res = await context.trigger_build_cycle()
        return ActionResponse(status=res["status"], message=res.get("message"), task_id=res.get("task_id"))

    @router.post("/actions/farm/trigger", response_model=ActionResponse)
    async def trigger_farm():
        """Dispara uma onda imediata de micro-farming."""
        res = await context.trigger_farm_wave()
        return ActionResponse(status=res["status"], message=res.get("message"), task_id=res.get("task_id"))

    @router.post("/actions/recruit/trigger", response_model=ActionResponse)
    async def trigger_recruit():
        """Dispara um ciclo imediato de recrutamento militar."""
        res = await context.trigger_recruit_cycle()
        return ActionResponse(status=res["status"], message=res.get("message"), task_id=res.get("task_id"))

    @router.post("/bot-protect/resume", response_model=ActionResponse)
    async def resume_after_captcha():
        """
        Endpoint chamado pelo frontend Tauri quando o utilizador resolve com sucesso
        o captcha na janela pop-up WebView. Retoma o agendamento de tarefas.
        """
        logger.info("Sinal de captcha resolvido recebido do frontend. Retomando agendador...")
        res = context.resume_scheduler()
        return ActionResponse(status="resumed", message="Agendador retomado após resolução de verificação anti-bot.")

    return router
