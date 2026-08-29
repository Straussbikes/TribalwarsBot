"""
Tribal Wars Mobile Automation Engine - Rotas REST da API Sidecar
Endpoints para controlo de tarefas, consulta de estado, ações manuais e configuração dinâmica.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from engine.api.auth import TokenVerifier
from engine.api.context import EngineContext

logger = logging.getLogger(__name__)


# --- Modelos Pydantic para Validação de Entrada ---

class BuildingTemplateCreateRequest(BaseModel):
    id: Optional[str] = None
    account_id: Optional[str] = None
    name: str
    target_levels: Optional[Dict[str, int]] = None
    priority_list: Optional[List[Any]] = None
    is_default: Optional[bool] = False


class BuildingTemplateUpdateRequest(BaseModel):
    account_id: Optional[str] = None
    name: Optional[str] = None
    target_levels: Optional[Dict[str, int]] = None
    priority_list: Optional[List[Any]] = None
    is_default: Optional[bool] = None


class RecruitmentModelCreateRequest(BaseModel):
    id: Optional[str] = None
    account_id: Optional[str] = None
    name: str
    units: Optional[Dict[str, int]] = None
    batch_sizes: Optional[Dict[str, int]] = None
    is_default: Optional[bool] = False


class RecruitmentModelUpdateRequest(BaseModel):
    account_id: Optional[str] = None
    name: Optional[str] = None
    units: Optional[Dict[str, int]] = None
    batch_sizes: Optional[Dict[str, int]] = None
    is_default: Optional[bool] = None


class CloneTemplateRequest(BaseModel):
    new_name: Optional[str] = None
    account_id: Optional[str] = None

class ConfigUpdateRequest(BaseModel):
    """Payload de atualização de configurações do bot."""
    world: Optional[str] = None
    sid: Optional[str] = None
    domain: Optional[str] = None
    building: Optional[Dict[str, Any]] = None
    farm: Optional[Dict[str, Any]] = None
    recruitment: Optional[Dict[str, Any]] = None
    quest: Optional[Dict[str, Any]] = None
    market: Optional[Dict[str, Any]] = None
    villages: Optional[Dict[str, Any]] = None


class MarketToggleRequest(BaseModel):
    enabled: Optional[bool] = None
    auto_balance_enabled: Optional[bool] = None


class BuildingToggleRequest(BaseModel):
    enabled: Optional[bool] = None
    interval_seconds: Optional[float] = None
    max_queue: Optional[int] = None


class RecruitmentToggleRequest(BaseModel):
    enabled: Optional[bool] = None
    interval_minutes: Optional[float] = None
    min_free_pop: Optional[int] = None


class RecruitmentModelsRequest(BaseModel):
    attack: Optional[Dict[str, int]] = None
    defense: Optional[Dict[str, int]] = None
    models: Optional[Dict[str, Dict[str, int]]] = None


class ArbitrageToggleRequest(BaseModel):
    enabled: Optional[bool] = None
    interval_seconds: Optional[float] = None
    emergency_queue_seconds: Optional[float] = None


class RadarFarmRequest(BaseModel):
    radius: Optional[float] = None
    squad_troops: Optional[Dict[str, int]] = None
    village_id: Optional[int] = None


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


class AccountCreateRequest(BaseModel):
    name: str
    world_domain: Optional[str] = None
    world: Optional[str] = "pt117"
    domain: Optional[str] = "tribalwars.com.pt"
    village_id: Optional[int] = None
    session_cookie: Optional[str] = ""
    sid: Optional[str] = None
    build_order_strategy: Optional[str] = "rush_resources"
    building_template: Optional[str] = None
    farm_presets: Optional[Dict[str, Any]] = None
    recruitment_models: Optional[Dict[str, Any]] = None
    proxy: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class AccountUpdateRequest(BaseModel):
    name: Optional[str] = None
    world_domain: Optional[str] = None
    world: Optional[str] = None
    domain: Optional[str] = None
    village_id: Optional[int] = None
    session_cookie: Optional[str] = None
    sid: Optional[str] = None
    build_order_strategy: Optional[str] = None
    building_template: Optional[str] = None
    farm_presets: Optional[Dict[str, Any]] = None
    recruitment_models: Optional[Dict[str, Any]] = None
    proxy: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


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


class MarketSendRequest(BaseModel):
    source_village_id: int
    target_village_id: int
    wood: int = 0
    stone: int = 0
    iron: int = 0


class MarketOfferRequest(BaseModel):
    village_id: int
    sell_res: str
    sell_amount: int
    buy_res: str
    buy_amount: int
    max_time: int = 10
    multi: int = 1


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

    # --- Gestão de Perfis de Conta & Bloqueio Monousuário (Single-Active Profile Lock) ---

    @router.get("/accounts")
    def get_accounts():
        """Lista todas as contas registadas no sistema."""
        return {"accounts": context.list_accounts()}

    @router.post("/accounts")
    def create_account(payload: AccountCreateRequest):
        """Cria um novo perfil de conta."""
        return context.create_account(payload.model_dump(exclude_unset=True))

    @router.get("/accounts/{account_id}")
    def get_account(account_id: str):
        """Obtém detalhes de uma conta específica."""
        acc = context.get_account(account_id)
        if not acc:
            raise HTTPException(status_code=404, detail="Conta não encontrada.")
        return acc

    @router.put("/accounts/{account_id}")
    def update_account(account_id: str, payload: AccountUpdateRequest):
        """Atualiza configurações de uma conta existente."""
        return context.update_account(account_id, payload.model_dump(exclude_unset=True))

    @router.delete("/accounts/{account_id}")
    def delete_account(account_id: str):
        """Remove o perfil da conta."""
        return context.delete_account(account_id)

    @router.post("/accounts/{account_id}/activate")
    async def activate_account(account_id: str):
        """Para a conta em execução, carrega o perfil selecionado e inicia o motor."""
        return await context.activate_account(account_id)

    @router.post("/accounts/disconnect")
    async def disconnect_account():
        """Para o scheduler e liberta a sessão ativa, regressando ao Hub de Contas."""
        return await context.disconnect_account()

    # Aliases de compatibilidade legada
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

    @router.get("/map/data")
    async def get_map_data(x: Optional[int] = None, y: Optional[int] = None, radius: float = 15.0, refresh: bool = False):
        """Compatibilidade para MapViewer / Cockpit map queries."""
        if not context.account:
            return {"status": "error", "message": "Conta não inicializada."}
        curr_v = context.account.current_village
        cx = x if x is not None else (curr_v.x if curr_v else 500)
        cy = y if y is not None else (curr_v.y if curr_v else 500)
        try:
            villages = []
            is_cached = False
            if not refresh:
                cached_villages, _ = context.map_manager.load_cache(context.account.world)
                if cached_villages:
                    for v in cached_villages:
                        v.distance = context.map_manager.calculate_distance(cx, cy, v.x, v.y)
                    villages = [v for v in cached_villages if v.distance <= radius + 5]
                    if villages:
                        is_cached = True

            if not villages:
                villages = await context.map_manager.fetch_map_data(
                    account=context.account,
                    center_x=cx,
                    center_y=cy,
                    radius=radius,
                )
                if villages:
                    context.map_manager.save_cache(context.account.world, villages)

            # Filtra aldeias no raio pedido
            filtered = [v for v in villages if v.distance <= radius]
            total_barbs = sum(1 for v in filtered if v.is_barbarian)
            total_players = len(filtered) - total_barbs
            return {
                "status": "success",
                "center": {"x": cx, "y": cy},
                "radius": radius,
                "count": len(filtered),
                "total_barbarians": total_barbs,
                "total_players": total_players,
                "cached": is_cached,
                "villages": [v.to_dict() for v in filtered],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @router.post("/map/farm-target")
    async def add_farm_target(payload: AddFarmTargetRequest):
        """Adiciona coordenadas aos alvos customizados de micro-farming."""
        coords = f"{payload.x}|{payload.y}"
        custom_targets = context.config.farm.custom_targets
        target_pair = [payload.x, payload.y]
        if target_pair not in custom_targets and (payload.x, payload.y) not in custom_targets:
            custom_targets.append(target_pair)
            context.update_config_and_save({"farm": {"custom_targets": custom_targets}})
        return {
            "status": "success",
            "message": f"Alvo {coords} adicionado à lista de farming.",
            "custom_targets": custom_targets,
        }

    @router.post("/map/quick-attack")
    async def send_quick_attack(payload: QuickAttackRequest):
        """Envia um ataque rápido manual para as coordenadas indicadas."""
        if not context.account:
            return {"status": "error", "message": "Conta não inicializada."}
        try:
            from engine.actions.place import UnitsCount
            troops = UnitsCount(
                spear=payload.spear,
                sword=payload.sword,
                axe=payload.axe,
                spy=payload.spy,
                light=payload.light,
            )
            v_id = context.account.current_village_id
            target_coords = f"{payload.target_x}|{payload.target_y}"
            res = await context.place_manager.send_attack(
                account=context.account,
                target_coords=target_coords,
                units=troops,
                village_id=v_id,
            )
            if res:
                cmd_id = getattr(res, "command_id", "cmd_ok")
                return {
                    "status": "success",
                    "message": f"Ataque enviado para {target_coords}!",
                    "command_id": cmd_id,
                }
            return {"status": "error", "message": f"Não foi possível enviar ataque para {target_coords}."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # --- Rotas Multi-Mundo Simultâneo ---

    @router.get("/worlds")
    def get_worlds():
        """Lista todos os mundos sob gestão concorrente do orquestrador."""
        return {"worlds": context.list_worlds()}

    @router.get("/worlds/discover")
    async def discover_worlds():
        """Descobre todos os mundos onde o utilizador tem aldeia criada."""
        return await context.discover_player_worlds()

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

    @router.post("/account/switch-village", response_model=ActionResponse)
    async def switch_active_village(payload: SwitchVillageRequest):
        """Alterna a aldeia ativa da conta no mundo atual."""
        if not context.account:
            return ActionResponse(status="error", message="Conta não inicializada.")
        try:
            v_data = await context.account.switch_village(payload.village_id)
            status = context.get_status_dict()
            context.broadcast_sync("STATUS_UPDATE", status)
            context.broadcast_sync("VILLAGE_UPDATED", status)
            return ActionResponse(status="success", message=f"Contexto alternado para a aldeia '{v_data.name}' ({v_data.coordinates}).")
        except Exception as e:
            return ActionResponse(status="error", message=str(e))

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

    # --- Endpoints do Mercado & Balanceamento de Recursos ---

    @router.get("/market/state")
    async def get_market_state(village_id: Optional[int] = None):
        """Retorna o estado do mercado (mercadores, movimentos e ofertas) da aldeia."""
        return await context.get_market_state(village_id=village_id)

    @router.post("/market/send", response_model=ActionResponse)
    async def send_market_resources(payload: MarketSendRequest):
        """Envia recursos entre duas aldeias via mercadores."""
        res = await context.send_market_resources(
            source_village_id=payload.source_village_id,
            target_village_id=payload.target_village_id,
            wood=payload.wood,
            stone=payload.stone,
            iron=payload.iron,
        )
        return ActionResponse(status=res["status"], message=res.get("message"))

    @router.get("/market/balance/plan")
    def get_resource_balancing_plan():
        """Retorna a análise de médias e as transferências planeadas para balancear a conta."""
        return context.get_resource_balancing_plan()

    @router.post("/market/balance/trigger")
    async def trigger_resource_balancing():
        """Dispara a execução imediata de um ciclo de balanceamento de recursos entre aldeias."""
        return await context.trigger_resource_balancing()

    @router.post("/market/offer", response_model=ActionResponse)
    async def create_market_offer(payload: MarketOfferRequest):
        """Cria uma oferta de troca de recursos no mercado da aldeia."""
        res = await context.create_market_offer(
            village_id=payload.village_id,
            sell_res=payload.sell_res,
            sell_amount=payload.sell_amount,
            buy_res=payload.buy_res,
            buy_amount=payload.buy_amount,
            max_time=payload.max_time,
            multi=payload.multi,
        )
        return ActionResponse(status=res["status"], message=res.get("message"))

    @router.post("/market/toggle", response_model=ActionResponse)
    async def toggle_market(payload: MarketToggleRequest):
        """Ativa ou desativa as funcionalidades e auto-balanceamento do mercado."""
        update_data = {}
        if payload.enabled is not None:
            update_data["enabled"] = payload.enabled
        if payload.auto_balance_enabled is not None:
            update_data["auto_balance_enabled"] = payload.auto_balance_enabled
            update_data["auto_balance"] = payload.auto_balance_enabled
        res = context.update_config_and_save({"market": update_data})
        return ActionResponse(status=res["status"], message=res.get("message"))

    @router.get("/building/state")
    async def get_building_state(village_id: Optional[int] = None):
        """Retorna o estado da fila de construção e a lista de próximos edifícios a serem upados."""
        return await context.get_building_state(village_id=village_id)

    @router.post("/building/cancel/{order_id}", response_model=ActionResponse)
    async def cancel_building_order(order_id: str, village_id: Optional[int] = None):
        """Cancela uma ordem de construção em andamento."""
        res = await context.cancel_building_order(order_id, village_id=village_id)
        return ActionResponse(status=res["status"], message=res.get("message"))

    @router.post("/building/toggle", response_model=ActionResponse)
    async def toggle_building(payload: BuildingToggleRequest):
        """Ativa/desativa a construção automática e ajusta parâmetros de fila."""
        res = context.toggle_building_module(
            enabled=payload.enabled,
            interval_seconds=payload.interval_seconds,
            max_queue=payload.max_queue,
        )
        return ActionResponse(status=res["status"], message=res.get("message"))

    @router.get("/recruitment/state")
    async def get_recruitment_state(village_id: Optional[int] = None):
        """Retorna o estado do recrutamento militar, tropas em treino e unidades disponíveis."""
        return await context.get_recruitment_state(village_id=village_id)

    @router.post("/recruitment/toggle", response_model=ActionResponse)
    async def toggle_recruitment(payload: RecruitmentToggleRequest):
        """Ativa/desativa o recrutamento automático contínuo."""
        res = context.toggle_recruitment_module(
            enabled=payload.enabled,
            interval_minutes=payload.interval_minutes,
            min_free_pop=payload.min_free_pop,
        )
        return ActionResponse(status=res["status"], message=res.get("message"))

    # --- Gestão de Modelos de Construção (Building Templates - SQLite) ---

    @router.get("/templates/building")
    def list_building_templates(account_id: Optional[str] = None):
        """Lista todos os modelos de construção disponíveis no SQLite."""
        return {"templates": context.list_building_templates(account_id=account_id)}

    @router.post("/templates/building")
    def create_building_template(payload: BuildingTemplateCreateRequest):
        """Cria um novo modelo de evolução de edifícios no SQLite."""
        return context.save_building_template(payload.model_dump(exclude_unset=True))

    @router.get("/templates/building/{template_id}")
    def get_building_template(template_id: str):
        """Obtém os detalhes de um modelo de construção específico."""
        tmpl = context.get_building_template(template_id)
        if not tmpl:
            raise HTTPException(status_code=404, detail=f"Modelo de construção '{template_id}' não encontrado.")
        return tmpl

    @router.put("/templates/building/{template_id}")
    def update_building_template(template_id: str, payload: BuildingTemplateUpdateRequest):
        """Atualiza a configuração ou lista de prioridades de um modelo de construção."""
        data = payload.model_dump(exclude_unset=True)
        data["id"] = template_id
        return context.save_building_template(data)

    @router.post("/templates/building/{template_id}/clone")
    def clone_building_template(template_id: str, payload: Optional[CloneTemplateRequest] = None):
        """Clona um modelo de construção existente para permitir customização."""
        new_name = payload.new_name if payload else None
        account_id = payload.account_id if payload else None
        res = context.clone_building_template(template_id, new_name=new_name, account_id=account_id)
        if res.get("status") == "error":
            raise HTTPException(status_code=404, detail=res.get("message"))
        return res

    @router.delete("/templates/building/{template_id}")
    def delete_building_template(template_id: str):
        """Remove um modelo de construção personalizado do SQLite."""
        res = context.delete_building_template(template_id)
        if res.get("status") == "error":
            raise HTTPException(status_code=400, detail=res.get("message"))
        return res

    # --- Gestão de Modelos de Recrutamento (Recruitment Models - SQLite) ---

    @router.get("/templates/recruitment")
    def list_recruitment_models_db(account_id: Optional[str] = None):
        """Lista todos os modelos de recrutamento de tropas disponíveis no SQLite."""
        return {"models": context.list_recruitment_models(account_id=account_id)}

    @router.post("/templates/recruitment")
    def create_recruitment_model_db(payload: RecruitmentModelCreateRequest):
        """Cria um novo modelo de tropas no SQLite."""
        return context.save_recruitment_model(payload.model_dump(exclude_unset=True))

    @router.get("/templates/recruitment/{model_id}")
    def get_recruitment_model_db(model_id: str):
        """Obtém detalhes de um modelo de tropas de recrutamento."""
        m = context.get_recruitment_model(model_id)
        if not m:
            raise HTTPException(status_code=404, detail=f"Modelo de recrutamento '{model_id}' não encontrado.")
        return m

    @router.put("/templates/recruitment/{model_id}")
    def update_recruitment_model_db(model_id: str, payload: RecruitmentModelUpdateRequest):
        """Atualiza quantidades de tropas e tamanhos de lote de um modelo no SQLite."""
        data = payload.model_dump(exclude_unset=True)
        data["id"] = model_id
        return context.save_recruitment_model(data)

    @router.post("/templates/recruitment/{model_id}/clone")
    def clone_recruitment_model_db(model_id: str, payload: Optional[CloneTemplateRequest] = None):
        """Clona um modelo de tropas para gerar uma variante customizada."""
        new_name = payload.new_name if payload else None
        account_id = payload.account_id if payload else None
        res = context.clone_recruitment_model(model_id, new_name=new_name, account_id=account_id)
        if res.get("status") == "error":
            raise HTTPException(status_code=404, detail=res.get("message"))
        return res

    @router.delete("/templates/recruitment/{model_id}")
    def delete_recruitment_model_db_route(model_id: str):
        """Remove um modelo de tropas personalizado do SQLite."""
        res = context.delete_recruitment_model_db(model_id)
        if res.get("status") == "error":
            raise HTTPException(status_code=400, detail=res.get("message"))
        return res

    # Aliases e compatibilidade legada para recrutamento
    @router.get("/recruitment/models")
    async def get_recruitment_models():
        """Retorna todos os modelos de tropas configurados (Ataque, Defesa e Customizados)."""
        return context.get_recruitment_models()

    @router.post("/recruitment/models", response_model=ActionResponse)
    async def save_recruitment_models(payload: RecruitmentModelsRequest):
        """Salva os modelos de tropas (Ataque, Defesa e Customizados) no SQLite e config.json."""
        res = context.save_recruitment_models(
            attack=payload.attack,
            defense=payload.defense,
            models=payload.models,
        )
        return ActionResponse(status=res["status"], message=res.get("message"))

    @router.delete("/recruitment/models/{name}", response_model=ActionResponse)
    async def delete_recruitment_model(name: str):
        """Remove um modelo de tropas customizado do SQLite e config.json."""
        res = context.delete_recruitment_model(name)
        return ActionResponse(status=res["status"], message=res.get("message"))

    # --- Endpoints de Arbitragem Económica & Fila Sempre Ativa (Item 2.12) ---

    @router.get("/arbitrage/state")
    async def get_arbitrage_state(village_id: Optional[int] = None):
        """Retorna a avaliação de arbitragem económica, diagnóstico das 4 filas e fluxo de caixa."""
        return await context.get_arbitrage_state(village_id=village_id)

    @router.post("/arbitrage/evaluate")
    async def trigger_arbitrage_evaluation(village_id: Optional[int] = None):
        """Dispara a execução imediata de um ciclo de arbitragem económica para a aldeia."""
        return await context.trigger_arbitrage_cycle(village_id=village_id)

    @router.post("/arbitrage/toggle", response_model=ActionResponse)
    async def toggle_arbitrage(payload: ArbitrageToggleRequest):
        """Ativa/desativa a rotina de arbitragem económica contínua."""
        res = context.toggle_arbitrage_module(
            enabled=payload.enabled,
            interval_seconds=payload.interval_seconds,
            emergency_queue_seconds=payload.emergency_queue_seconds,
        )
        return ActionResponse(status=res["status"], message=res.get("message"))

    # --- Endpoints de Radar de Bárbaras & Saque Recorrente (Item 2.3) ---

    @router.post("/farm/radar/plan")
    async def get_radar_farm_plan(payload: RadarFarmRequest):
        """Calcula o plano de alocação de micro-esquadrões de saque para as bárbaras mais próximas."""
        return await context.get_radar_farm_plan(
            radius=payload.radius,
            squad_troops=payload.squad_troops,
            village_id=payload.village_id,
        )

    @router.post("/farm/radar/run")
    async def run_radar_farm(payload: RadarFarmRequest):
        """Dispara uma onda imediata de Radar Farming com alocação dinâmica de tropas."""
        return await context.trigger_radar_farm_cycle(
            radius=payload.radius,
            squad_troops=payload.squad_troops,
            village_id=payload.village_id,
        )

    # --- Endpoints de Estatísticas & Rendimento ---

    @router.get("/stats/summary")
    def get_stats_summary(world: Optional[str] = None):
        """Retorna resumo consolidado de estatísticas e KPIs de eficiência."""
        return context.get_stats_summary(world=world)

    @router.get("/stats/history")
    def get_stats_history(
        hours: int = 24, days: int = 7, world: Optional[str] = None
    ):
        """Retorna séries temporais para gráficos e histórico de comandos/saques."""
        return context.get_stats_history(hours=hours, days=days, world=world)

    @router.post("/stats/reset", response_model=ActionResponse)
    def reset_stats(world: Optional[str] = None):
        """Reinicia as métricas e histórico de estatísticas do mundo."""
        res = context.reset_stats(world=world)
        return ActionResponse(status=res["status"], message=res.get("message"))

    # --- Endpoints de Rede & Diagnóstico de Requisições ---

    @router.get("/network/requests")
    def get_network_requests(limit: int = 50):
        """Retorna histórico de requisições HTTP efetuadas pelo bot com telemetria."""
        return context.get_network_requests(limit=limit)

    @router.post("/village/refresh")
    async def refresh_village_details():
        """Atualiza ativamente os dados da aldeia ativa, recursos e tropas."""
        return await context.refresh_village_data()

    return router


