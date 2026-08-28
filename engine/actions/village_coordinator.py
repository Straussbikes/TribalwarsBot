"""
Tribal Wars Mobile Automation Engine - Multi-Village Coordinator
Orquestrador assíncrono para gestão simultânea e categorizada de múltiplas aldeias
da mesma conta, vinculação de templates (Ataque/Defesa/Balanceado) e balanceamento de recursos.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from engine.actions.farm import FarmManager
from engine.actions.main_building import MainBuildingManager
from engine.actions.recruitment import RecruitmentManager
from engine.config.settings import BotConfig
from engine.core.account import TribalAccount
from engine.core.models import (
    CATEGORY_BUILDING_TEMPLATES,
    CATEGORY_RECRUITMENT_TARGETS,
    TaskPriority,
    VillageCategory,
    VillageData,
)

logger = logging.getLogger(__name__)


class MultiVillageCoordinator:
    """
    Coordena as rotinas de construção, recrutamento e recolha de recursos
    em todas as aldeias da mesma conta, respeitando a categoria de cada aldeia.
    """

    def __init__(
        self,
        main_building_manager: Optional[MainBuildingManager] = None,
        recruitment_manager: Optional[RecruitmentManager] = None,
        farm_manager: Optional[FarmManager] = None,
    ):
        self.main_building_manager = main_building_manager or MainBuildingManager()
        self.recruitment_manager = recruitment_manager or RecruitmentManager()
        self.farm_manager = farm_manager or FarmManager()
        self.last_sync_time: float = 0.0

    def set_village_category(
        self,
        account: TribalAccount,
        config: BotConfig,
        village_id: int,
        category: str,
    ) -> bool:
        """
        Define a categoria de uma aldeia (attack, defense, balanced)
        e atualiza a configuração ativa.
        """
        normalized_cat = category.lower().strip()
        if normalized_cat not in ("attack", "defense", "balanced"):
            normalized_cat = "balanced"

        # 1. Atualiza no modelo de aldeia em memória
        if village_id in account.villages:
            account.villages[village_id].category = VillageCategory(normalized_cat)

        # 2. Atualiza no BotConfig
        from engine.config.settings import VillageConfig
        if str(village_id) not in config.villages:
            config.villages[str(village_id)] = VillageConfig(category=normalized_cat)
        else:
            config.villages[str(village_id)].category = normalized_cat

        logger.info(f"[{account.world}] Aldeia {village_id} categorizada como '{normalized_cat}'.")
        return True

    def get_village_category(self, account: TribalAccount, config: BotConfig, village_id: int) -> VillageCategory:
        """Retorna a categoria atribuída à aldeia (ou BALANCED por defeito)."""
        if str(village_id) in config.villages:
            cat_str = config.villages[str(village_id)].category
            try:
                return VillageCategory(cat_str)
            except ValueError:
                pass

        if village_id in account.villages:
            return account.villages[village_id].category

        return VillageCategory.BALANCED

    async def sync_all_villages(self, account: TribalAccount) -> List[VillageData]:
        """
        Sincroniza o estado e recursos de todas as aldeias da conta sem bloquear a execução.
        """
        if not account or not account.sid:
            return []

        villages_list = list(account.villages.values())
        if not villages_list and account.current_village:
            villages_list = [account.current_village]

        for v in villages_list:
            try:
                # Se for a aldeia ativa, atualiza diretamente
                if account.current_village_id == v.id:
                    await account.refresh_village_details()
                else:
                    # Consulta dados via tela principal passando o village_id
                    await account.get_screen("main", village_id=v.id)
            except Exception as e:
                logger.debug(f"[{account.world}] Erro suave ao sincronizar aldeia {v.id}: {e}")

        self.last_sync_time = time.time()
        return list(account.villages.values())

    async def run_coordinated_cycle(
        self,
        account: TribalAccount,
        config: BotConfig,
    ) -> Dict[str, Any]:
        """
        Executa um ciclo completo coordenado para todas as aldeias da conta:
        - Para cada aldeia, executa construção com o template da sua categoria.
        - Executa recrutamento com as metas da sua categoria.
        """
        if not account or not account.sid:
            return {"status": "error", "message": "Conta não conectada."}

        villages = list(account.villages.values())
        if not villages and account.current_village:
            villages = [account.current_village]

        results = {
            "villages_processed": len(villages),
            "building_actions": 0,
            "recruitment_actions": 0,
            "details": [],
        }

        orig_village_id = account.current_village_id

        for v in villages:
            v_id = v.id
            cat = self.get_village_category(account, config, v_id)
            v_detail = {
                "village_id": v_id,
                "name": v.name,
                "category": cat.value,
                "building": None,
                "recruitment": None,
            }

            try:
                # 1. Avaliação de Construção baseada na categoria
                build_plan = config.get_active_build_plan(village_id=str(v_id))
                b_res = await self.main_building_manager.run_build_cycle(
                    account=account,
                    plan=build_plan,
                    max_queue=config.building.max_queue,
                    village_id=v_id,
                )
                if b_res and b_res.get("upgraded"):
                    results["building_actions"] += 1
                    v_detail["building"] = b_res

                # 2. Avaliação de Recrutamento baseada na categoria (se ativado)
                if config.recruitment.enabled:
                    r_targets = config.get_village_recruitment_targets(village_id=str(v_id))
                    r_res = await self.recruitment_manager.run_recruitment_cycle(
                        account=account,
                        targets=r_targets,
                        batch_sizes=config.recruitment.batch_sizes,
                        min_free_pop=config.recruitment.min_free_pop,
                        village_id=v_id,
                    )
                    if r_res:
                        results["recruitment_actions"] += 1
                        v_detail["recruitment"] = r_res

            except Exception as v_err:
                logger.warning(f"[{account.world}] Erro ao processar aldeia {v_id}: {v_err}")
                v_detail["error"] = str(v_err)

            results["details"].append(v_detail)

        # Restaura aldeia ativa se tiver sido alternada
        if orig_village_id and account.current_village_id != orig_village_id:
            try:
                await account.switch_village(orig_village_id)
            except Exception:
                pass

        return results

    def calculate_resource_balance(self, account: TribalAccount) -> Dict[str, Any]:
        """
        Analisa o balanceamento de recursos entre todas as aldeias da conta.
        Identifica aldeias doadoras (excedente) e aldeias recetoras (défice).
        """
        villages = list(account.villages.values())
        if not villages:
            return {"status": "empty", "message": "Nenhuma aldeia para balancear."}

        total_wood = sum(v.resources.wood for v in villages)
        total_stone = sum(v.resources.stone for v in villages)
        total_iron = sum(v.resources.iron for v in villages)
        n = len(villages)

        avg_wood = total_wood / n
        avg_stone = total_stone / n
        avg_iron = total_iron / n

        donors = []
        receivers = []

        for v in villages:
            res = v.resources
            diff_wood = res.wood - avg_wood
            diff_stone = res.stone - avg_stone
            diff_iron = res.iron - avg_iron
            score = diff_wood + diff_stone + diff_iron

            is_full = res.storage_max > 0 and (
                res.wood >= res.storage_max * 0.95
                or res.stone >= res.storage_max * 0.95
                or res.iron >= res.storage_max * 0.95
            )

            v_info = {
                "village_id": v.id,
                "name": v.name,
                "coordinates": v.coordinates,
                "wood": res.wood,
                "stone": res.stone,
                "iron": res.iron,
                "storage_max": res.storage_max,
                "diff_wood": round(diff_wood),
                "diff_stone": round(diff_stone),
                "diff_iron": round(diff_iron),
            }

            if score > 500 or is_full:
                donors.append(v_info)
            elif score < -500:
                receivers.append(v_info)

        return {
            "total_villages": n,
            "averages": {
                "wood": round(avg_wood),
                "stone": round(avg_stone),
                "iron": round(avg_iron),
            },
            "donors": donors,
            "receivers": receivers,
        }
