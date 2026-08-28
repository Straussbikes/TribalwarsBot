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
    quest: Optional[Dict[str, Any]] = None
    villages: Optional[Dict[str, Any]] = None


class ActionResponse(BaseModel):
    """Resposta padrão para chamadas de ação."""
    status: str
    message: Optional[str] = None
    task_id: Optional[str] = None
    barbarians_count: Optional[int] = None


class SwitchVillageRequest(BaseModel):
    village_id: int


class SwitchProfileRequest(BaseModel):
    profile_id: str


class AddFarmTargetRequest(BaseModel):
    x: int
    y: int


class ProxyTestRequest(BaseModel):
    proxy: str


class QuickAttackRequest(BaseModel):
    target_x: int
    target_y: int
    spear: int = 0
    sword: int = 0
    axe: int = 0
    spy: int = 0
    light: int = 0


class WorldRegisterRequest(BaseModel):
    world: str
    sid: str
    domain: Optional[str] = "tribalwars.com.pt"
    proxy: Optional[str] = None


class WorldSwitchRequest(BaseModel):
    world: str


class VillageCategoryRequest(BaseModel):
    village_id: int
    category: str


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

    @router.post("/actions/quest/trigger", response_model=ActionResponse)
    async def trigger_quest():
        """Dispara um ciclo imediato de missões e bónus diário (sem uso de inventário)."""
        res = await context.trigger_quest_cycle()
        return ActionResponse(status=res["status"], message=res.get("message"), task_id=res.get("task_id"))

    @router.get("/quest/status")
    async def get_quest_status():
        """Consulta o estado das missões, bónus diário e inventário."""
        if not context.account:
            return {"status": "error", "message": "Conta não inicializada."}
        try:
            q_state = await context.quest_manager.get_quest_state(context.account)
            d_state = await context.quest_manager.get_daily_bonus_state(context.account)
            inv_state = await context.quest_manager.get_inventory_state(context.account)
            return {
                "quests": [
                    {
                        "id": q.id,
                        "title": q.title,
                        "description": q.description,
                        "finishable": q.finishable,
                        "rewards": {
                            "wood": q.rewards.wood,
                            "stone": q.rewards.stone,
                            "iron": q.rewards.iron,
                            "pop": q.rewards.pop,
                        },
                    }
                    for q in q_state.quests
                ],
                "finishable_count": q_state.finishable_count,
                "daily_bonus": {
                    "can_open": d_state.can_open,
                    "is_opened_today": d_state.is_opened_today,
                },
                "inventory": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "count": item.count,
                        "description": item.description,
                        "can_use": item.can_use,
                    }
                    for item in inv_state.items
                ],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @router.post("/quest/claim/{quest_id}", response_model=ActionResponse)
    async def claim_quest_manual(quest_id: str):
        """Resgata manualmente uma missão concluída."""
        if not context.account:
            return ActionResponse(status="error", message="Conta não inicializada.")
        try:
            q_state = await context.quest_manager.get_quest_state(context.account)
            target = next((q for q in q_state.quests if q.id == quest_id), None)
            if not target:
                return ActionResponse(status="error", message=f"Missão '{quest_id}' não encontrada.")
            success = await context.quest_manager.claim_quest(context.account, target, safe_mode=True)
            if success:
                return ActionResponse(status="success", message=f"Recompensa da missão '{target.title}' resgatada.")
            return ActionResponse(status="error", message="Não foi possível resgatar a missão (limite de armazém/população ou erro HTTP).")
        except Exception as e:
            return ActionResponse(status="error", message=str(e))

    @router.post("/quest/claim-all")
    async def claim_all_quests():
        """Resgata todas as missões concluídas respeitando limites de armazém e população."""
        res = await context.claim_all_quests_safe()
        return res

    @router.post("/quest/daily-bonus/open", response_model=ActionResponse)
    async def open_daily_bonus_manual():
        """Abre manualmente o baú de bónus diário."""
        if not context.account:
            return ActionResponse(status="error", message="Conta não inicializada.")
        try:
            success = await context.quest_manager.open_daily_bonus(context.account)
            if success:
                return ActionResponse(status="success", message="Baú diário aberto com sucesso.")
            return ActionResponse(status="error", message="Baú diário não disponível ou já recolhido hoje.")
        except Exception as e:
            return ActionResponse(status="error", message=str(e))

    @router.post("/quest/inventory/use/{item_id}", response_model=ActionResponse)
    async def use_inventory_item_manual(item_id: str):
        """Utiliza manualmente um item do inventário."""
        if not context.account:
            return ActionResponse(status="error", message="Conta não inicializada.")
        try:
            success = await context.quest_manager.use_inventory_item(context.account, item_id)
            if success:
                return ActionResponse(status="success", message=f"Item '{item_id}' utilizado com sucesso.")
            return ActionResponse(status="error", message=f"Falha ao utilizar item '{item_id}'.")
        except Exception as e:
            return ActionResponse(status="error", message=str(e))

    @router.post("/auth/renew", response_model=ActionResponse)
    async def renew_session():
        """Força a renovação do cookie 'sid' via WebView2 nativo."""
        res = await context.trigger_renew_session()
        return ActionResponse(status=res["status"], message=res.get("message"))

    @router.post("/bot-protect/resume", response_model=ActionResponse)
    async def resume_after_captcha():
        """
        Endpoint chamado pelo frontend Tauri quando o utilizador resolve com sucesso
        o captcha na janela pop-up WebView. Retoma o agendamento de tarefas.
        """
        logger.info("Sinal de captcha resolvido recebido do frontend. Retomando agendador...")
        res = context.resume_scheduler()
        return ActionResponse(status="resumed", message="Agendador retomado após resolução de verificação anti-bot.")

    @router.get("/account/villages")
    async def get_villages():
        """Lista todas as aldeias pertencentes à conta."""
        villages = [v.to_dict() for v in context.account.villages.values()] if context.account else []
        curr_id = context.account.current_village_id if context.account else None
        return {"villages": villages, "current_village_id": curr_id}

    @router.post("/account/switch-village")
    async def switch_village(payload: SwitchVillageRequest):
        """Alterna a aldeia ativa no bot."""
        res = await context.switch_village(payload.village_id)
        return res

    @router.post("/account/refresh")
    async def refresh_village():
        """Atualiza ativamente recursos, capacidade de armazém e tropas disponíveis."""
        res = await context.refresh_village_data()
        return res

    @router.get("/profiles")
    async def list_profiles():
        """Lista todos os perfis de conta configurados."""
        return {"profiles": context.list_profiles()}

    @router.post("/profiles/switch")
    async def switch_profile(payload: SwitchProfileRequest):
        """Alterna para outro perfil de conta."""
        res = await context.switch_profile(payload.profile_id)
        return res

    @router.post("/proxy/test")
    async def test_proxy(payload: ProxyTestRequest):
        """Valida a conectividade de um proxy residencial/dedicado."""
        res = await context.test_proxy(payload.proxy)
        return res

    @router.get("/map/grid")
    async def get_map_grid(x: Optional[int] = None, y: Optional[int] = None, radius: float = 15.0, use_cache: bool = True):
        """Consulta as aldeias visíveis na grelha do mapa em torno de (x|y) ou da aldeia ativa."""
        if not context.account:
            return {"status": "error", "message": "Conta não inicializada."}
        curr_v = context.account.current_village
        cx = x if x is not None else (curr_v.x if curr_v else 500)
        cy = y if y is not None else (curr_v.y if curr_v else 500)
        try:
            villages = []
            if use_cache:
                # 1. Tenta carregar da cache local para resposta imediata
                cached_villages, ts = context.map_manager.load_cache(context.account.world)
                if cached_villages:
                    for v in cached_villages:
                        v.distance = context.map_manager.calculate_distance(cx, cy, v.x, v.y)
                    villages = [v for v in cached_villages if v.distance <= radius + 5]

            # 2. Se a cache estiver vazia ou use_cache=False, consulta ativamente a rede
            if not villages:
                villages = await context.map_manager.fetch_map_data(
                    account=context.account,
                    center_x=cx,
                    center_y=cy,
                    radius=radius,
                )
                if villages and use_cache:
                    context.map_manager.save_cache(context.account.world, villages)

            return {
                "center": {"x": cx, "y": cy},
                "radius": radius,
                "count": len(villages),
                "villages": [v.to_dict() for v in villages],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @router.get("/map/barbarians")
    async def get_map_barbarians(radius: float = 15.0, use_cache: bool = True):
        """Lista as aldeias bárbaras mais próximas ordenadas por distância euclidiana."""
        if not context.account:
            return {"status": "error", "message": "Conta não inicializada."}
        curr_v = context.account.current_village
        if not curr_v:
            return {"status": "error", "message": "Nenhuma aldeia ativa selecionada."}
        try:
            barbarians = await context.map_manager.scan_nearby_barbarians(
                account=context.account,
                center_x=curr_v.x,
                center_y=curr_v.y,
                radius=radius,
                use_cache=use_cache,
            )
            return {
                "center": {"x": curr_v.x, "y": curr_v.y},
                "radius": radius,
                "count": len(barbarians),
                "barbarians": [b.to_dict() for b in barbarians],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @router.post("/map/scan", response_model=ActionResponse)
    async def force_map_scan(radius: float = 15.0):
        """Força uma varredura ativa do mapa ignorando a cache local."""
        if not context.account:
            return ActionResponse(status="error", message="Conta não inicializada.")
        curr_v = context.account.current_village
        if not curr_v:
            return ActionResponse(status="error", message="Nenhuma aldeia ativa selecionada.")
        try:
            barbarians = await context.map_manager.scan_nearby_barbarians(
                account=context.account,
                center_x=curr_v.x,
                center_y=curr_v.y,
                radius=radius,
                use_cache=False,
            )
            return ActionResponse(
                status="success",
                message=f"Varredura concluída: {len(barbarians)} bárbaras encontradas.",
                barbarians_count=len(barbarians),
            )
        except Exception as e:
            return ActionResponse(status="error", message=str(e))

    @router.post("/map/farm", response_model=ActionResponse)
    async def trigger_map_farm():
        """Dispara uma onda de farming baseada na varredura das bárbaras mais próximas."""
        res = await context.trigger_map_farm_wave()
        return ActionResponse(status=res["status"], message=res.get("message"), task_id=res.get("task_id"))

    # --- Rotas Multi-Mundo Simultâneo ---

    @router.get("/worlds")
    def get_worlds():
        """Lista todos os mundos sob gestão concorrente do orquestrador."""
        return {"worlds": context.list_worlds()}

    @router.post("/worlds/register", response_model=ActionResponse)
    async def register_world(payload: WorldRegisterRequest):
        """Regista e inicializa um novo mundo em paralelo."""
        res = await context.register_world(
            world=payload.world,
            sid=payload.sid,
            domain=payload.domain or "tribalwars.com.pt",
            proxy=payload.proxy,
        )
        return ActionResponse(status=res["status"], message=res.get("message"))

    @router.post("/worlds/switch", response_model=ActionResponse)
    async def switch_world(payload: WorldSwitchRequest):
        """Alterna o foco do dashboard para outro mundo em execução."""
        res = await context.switch_world(payload.world)
        return ActionResponse(status=res["status"], message=res.get("message"))

    # --- Rotas Multi-Aldeia & Categorização ---

    @router.get("/account/villages")
    async def get_account_villages():
        """Lista detalhada de todas as aldeias com recursos, população e categorias."""
        return await context.sync_and_get_all_villages()

    @router.post("/account/village/category", response_model=ActionResponse)
    def set_village_category(payload: VillageCategoryRequest):
        """Define a categoria tática (Ataque, Defesa, Balanceado) para uma aldeia."""
        res = context.set_village_category(payload.village_id, payload.category)
        return ActionResponse(status=res["status"], message=res.get("message"))

    @router.post("/account/villages/cycle")
    async def run_all_villages_cycle():
        """Dispara um ciclo coordenado para todas as aldeias da conta ativa."""
        return await context.trigger_all_villages_cycle()

    @router.get("/account/villages/balance")
    def get_village_resource_balance():
        """Calcula o balanceamento e desvios de recursos entre todas as aldeias."""
        if not context.account:
            return {"status": "error", "message": "Conta não inicializada."}
        return context.village_coordinator.calculate_resource_balance(context.account)

    @router.get("/map/data")
    async def get_map(
        x: Optional[int] = None,
        y: Optional[int] = None,
        radius: float = 15.0,
        refresh: bool = False,
    ):
        """Retorna dados de aldeias do mapa em torno de (x, y) no raio especificado."""
        return await context.get_map_data(
            center_x=x,
            center_y=y,
            radius=radius,
            force_refresh=refresh,
        )

    @router.post("/map/farm-target")
    async def add_farm_target(payload: AddFarmTargetRequest):
        """Adiciona uma coordenada de aldeia aos alvos regulares de farm."""
        return context.add_custom_farm_target(payload.x, payload.y)

    @router.post("/map/quick-attack")
    async def send_quick_attack(payload: QuickAttackRequest):
        """Envia um comando de ataque direto para uma coordenada a partir do mapa."""
        return await context.send_quick_attack(
            target_x=payload.target_x,
            target_y=payload.target_y,
            spear=payload.spear,
            sword=payload.sword,
            axe=payload.axe,
            spy=payload.spy,
            light=payload.light,
        )

    return router


