"""
Tribal Wars Mobile Automation Engine - FarmManager (screen=am_farm & screen=place)
Automação de Micro-Farming: envio de saques em massa com o Assistente de Farm (Modelos A/B)
e fallback direto via Praça de Reunião com filtros de segurança e temporização humana.
"""

import asyncio
from dataclasses import dataclass, field
import logging
import random
from typing import Any, Dict, List, Optional, Tuple

from engine.actions.place import PlaceManager, UnitsCount
from engine.core.account import TribalAccount
from engine.core.models import TaskPriority
from engine.core.scheduler import TaskScheduler
from engine.utils.parsers import (
    parse_am_farm_targets,
    parse_am_farm_templates,
)
from engine.utils.timing import get_human_delay

logger = logging.getLogger(__name__)


@dataclass
class FarmTarget:
    """Dados de uma aldeia bárbara elegível para farm."""
    target_id: str
    target_name: str
    target_coords: str
    distance: float = 0.0
    report_color: str = "none"  # 'green', 'yellow', 'red', 'blue', 'none'
    wall_level: int = 0
    template_a_id: Optional[str] = None
    template_b_id: Optional[str] = None
    template_a_available: bool = False
    template_b_available: bool = False


@dataclass
class FarmAssistantState:
    """Estado consolidado do Assistente de Farm (screen=am_farm)."""
    village_id: int
    targets: List[FarmTarget] = field(default_factory=list)
    template_a_troops: Dict[str, int] = field(default_factory=dict)
    template_b_troops: Dict[str, int] = field(default_factory=dict)

    @property
    def total_targets_count(self) -> int:
        return len(self.targets)


@dataclass
class RadarFarmPlan:
    """Plano dinâmico de alocação de micro-esquadrões para aldeias bárbaras mapeadas."""
    village_id: int
    total_barbarians_found: int
    eligible_targets: List[Tuple[int, int]] = field(default_factory=list)
    squads_assigned: List[Tuple[Tuple[int, int], UnitsCount]] = field(default_factory=list)
    total_carrying_capacity: int = 0


def allocate_dynamic_squads(
    available_units: UnitsCount,
    squad_template: UnitsCount,
    targets: List[Tuple[int, int]],
    max_squads: Optional[int] = None,
) -> List[Tuple[Tuple[int, int], UnitsCount]]:
    """
    Divide de forma balanceada as tropas disponíveis na aldeia em micro-esquadrões de saque
    de acordo com o modelo de esquadrão fornecido (ex.: 5 lanceiros + 1 explorador ou 2 cavalarias leves).
    Distribui os esquadrões pelos alvos especificados (ordenados por proximidade).
    """
    if not targets:
        return []

    # Determinar unidades mínimas por esquadrão requeridas
    template_dict = {u: cnt for u, cnt in squad_template.to_dict().items() if cnt > 0}
    if not template_dict:
        template_dict = {"spear": 5}
        squad_template = UnitsCount(spear=5)

    avail_dict = available_units.to_dict()

    # Quantos esquadrões completos conseguimos formar com as tropas atualmente disponíveis?
    max_possible_squads = min(
        avail_dict.get(u, 0) // req_cnt
        for u, req_cnt in template_dict.items()
    )

    if max_possible_squads <= 0:
        return []

    num_squads = min(max_possible_squads, len(targets))
    if max_squads is not None and max_squads > 0:
        num_squads = min(num_squads, max_squads)

    allocations: List[Tuple[Tuple[int, int], UnitsCount]] = []
    for i in range(num_squads):
        target = targets[i]
        allocations.append((target, squad_template))

    return allocations


class FarmManager:
    """
    Controlador de automação de Micro-Farming.
    Fornece rotinas de saque em massa via Assistente de Farm ou Praça de Reunião.
    """

    def __init__(
        self,
        place_manager: Optional[PlaceManager] = None,
        map_manager: Optional[Any] = None,
    ):
        self.place_manager = place_manager or PlaceManager()
        self.map_manager = map_manager

    async def get_am_farm_state(
        self, account: TribalAccount, village_id: Optional[int] = None
    ) -> FarmAssistantState:
        """
        Carrega o ecrã 'screen=am_farm' e extrai a lista de aldeias bárbaras e modelos A/B.
        """
        html = await account.get_screen("am_farm", village_id=village_id)
        v_id = village_id or account.current_village_id or 0

        raw_targets = parse_am_farm_targets(html)
        raw_templates = parse_am_farm_templates(html)

        targets: List[FarmTarget] = [
            FarmTarget(
                target_id=str(t["target_id"]),
                target_name=str(t["target_name"]),
                target_coords=str(t["target_coords"]),
                distance=float(t["distance"]),
                report_color=str(t["report_color"]),
                wall_level=int(t["wall_level"]),
                template_a_id=t["template_a_id"],
                template_b_id=t["template_b_id"],
                template_a_available=bool(t["template_a_available"]),
                template_b_available=bool(t["template_b_available"]),
            )
            for t in raw_targets
        ]

        logger.info(
            f"[{account.world}] Assistente de Farm carregado: {len(targets)} alvos detetados na aldeia {v_id}."
        )
        return FarmAssistantState(
            village_id=v_id,
            targets=targets,
            template_a_troops=raw_templates.get("a", {}),
            template_b_troops=raw_templates.get("b", {}),
        )

    async def send_am_farm_attack(
        self,
        account: TribalAccount,
        target_id: str,
        template_id: str,
        village_id: Optional[int] = None,
    ) -> bool:
        """
        Envia um comando de farm rápido via Assistente de Farm (GET action=farm).
        Injeta token CSRF e micro-jitter mecânico de toque em ecrã.
        """
        try:
            extra_params = {
                "action": "farm",
                "target": target_id,
                "template_id": template_id,
                "h": account.csrf_token or "",
            }
            # Aplica micro-jitter de toque (150ms a 380ms)
            await account.get_screen(
                screen="am_farm",
                village_id=village_id,
                extra_params=extra_params,
                apply_jitter=True,
            )
            return True
        except Exception as e:
            logger.warning(f"[{account.world}] Falha ao enviar farm para alvo {target_id}: {e}")
            return False

    async def run_am_farm_wave(
        self,
        account: TribalAccount,
        template: str = "A",
        max_distance: float = 15.0,
        skip_losses: bool = True,
        skip_wall: bool = True,
        max_attacks: int = 30,
        village_id: Optional[int] = None,
    ) -> int:
        """
        Executa uma onda de saques pelo Assistente de Farm:
        1. Inspeciona a lista de bárbaras.
        2. Aplica filtros de distância, cor de relatório e nível de muralha.
        3. Dispara os ataques em série com jitter humano entre cada clique.
        Retorna a quantidade de saques enviados com sucesso.
        """
        tmpl_key = template.upper().strip()
        state = await self.get_am_farm_state(account, village_id=village_id)
        if not state.targets:
            logger.info(f"[{account.world}] Nenhuma aldeia bárbara listada no Assistente de Farm.")
            return 0

        sent_count = 0
        logger.info(
            f"[{account.world}] A iniciar onda de Farm (Modelo {tmpl_key}) para até {max_attacks} alvos..."
        )

        for target in state.targets:
            if sent_count >= max_attacks:
                break

            # 1. Filtro de distância máxima
            if target.distance > max_distance:
                continue

            # 2. Filtro de segurança: ignorar aldeias com perdas
            if skip_losses and target.report_color in ("yellow", "red"):
                logger.debug(
                    f"Alvo {target.target_coords} ignorado (relatório {target.report_color})."
                )
                continue

            # 3. Filtro de segurança: ignorar aldeias com muralha detectada
            if skip_wall and target.wall_level > 0:
                logger.debug(
                    f"Alvo {target.target_coords} ignorado (muralha nível {target.wall_level})."
                )
                continue

            # 4. Verifica se o botão do modelo escolhido está disponível
            if tmpl_key == "A":
                t_id = target.template_a_id
                t_avail = target.template_a_available
            else:
                t_id = target.template_b_id
                t_avail = target.template_b_available

            if not t_avail or not t_id:
                # Tropas esgotadas para este modelo ou botão disabled
                continue

            # Envia o saque com micro-jitter
            success = await self.send_am_farm_attack(
                account=account,
                target_id=target.target_id,
                template_id=t_id,
                village_id=village_id,
            )
            if success:
                sent_count += 1
                logger.info(
                    f"[{account.world}] Saque #{sent_count} enviado -> {target.target_name} "
                    f"({target.target_coords}) [Dist: {target.distance:.1f} campos]"
                )
                # Jitter humano realista entre cliques sucessivos de farm (200ms a 550ms)
                inter_click_delay = random.uniform(0.20, 0.55)
                await asyncio.sleep(inter_click_delay)

        logger.info(
            f"[{account.world}] Onda de Farm concluída: {sent_count} saques enviados."
        )
        return sent_count

    async def run_place_farm_wave(
        self,
        account: TribalAccount,
        targets: List[Tuple[int, int]],
        troops: UnitsCount,
        max_attacks: int = 30,
        village_id: Optional[int] = None,
    ) -> int:
        """
        Modo de Fallback: executa uma onda de saques diretamente pela Praça de Reunião
        para uma lista de coordenadas de aldeias bárbaras.
        """
        if not targets:
            logger.info("Nenhum alvo de farm configurado na lista de coordenadas.")
            return 0

        sent_count = 0
        logger.info(
            f"[{account.world}] A iniciar onda de Farm via Praça para {len(targets)} alvos..."
        )

        for coords in targets:
            if sent_count >= max_attacks:
                break

            # Envia o comando em 2 etapas
            success = await self.place_manager.send_command(
                account=account,
                target_coords=coords,
                units=troops,
                is_attack=True,
                village_id=village_id,
                allow_partial=False,
            )

            if success:
                sent_count += 1
                logger.info(f"[{account.world}] Saque #{sent_count} via Praça enviado -> ({coords[0]}|{coords[1]})")
                # Intervalo realista entre saques via praça (1.5s a 3.5s)
                delay = get_human_delay(2.5, 0.5, 1.5, 4.0)
                await asyncio.sleep(delay)
            else:
                # Tropas insuficientes para continuar a onda
                logger.info(f"[{account.world}] Tropas esgotadas para farming via Praça. Onda interrompida.")
                break

        return sent_count

    async def get_radar_farm_plan(
        self,
        account: TribalAccount,
        radius: float = 15.0,
        squad_template: Optional[UnitsCount] = None,
        max_attacks: int = 30,
        skip_active_targets: bool = True,
        village_id: Optional[int] = None,
        use_cache: bool = True,
    ) -> RadarFarmPlan:
        """
        Calcula o plano de alocação de micro-esquadrões para as bárbaras mais próximas,
        sem enviar comandos de ataque.
        """
        v_id = village_id or account.current_village_id
        curr_v = account.villages.get(v_id) if account.villages else None
        cx = curr_v.x if curr_v else 500
        cy = curr_v.y if curr_v else 500

        if not self.map_manager:
            from engine.actions.map import MapManager
            self.map_manager = MapManager()

        # 1. Scanner de aldeias bárbaras ordenadas por proximidade
        barbarians = await self.map_manager.scan_nearby_barbarians(
            account=account,
            center_x=cx,
            center_y=cy,
            radius=radius,
            village_id=v_id,
            use_cache=use_cache,
        )

        # 2. Leitura do estado da Praça de Reunião
        place_state = await self.place_manager.get_state(account, village_id=v_id)

        # 3. Extrair coordenadas com ataques atualmente a caminho para evitar repetições
        active_target_coords = set()
        if skip_active_targets:
            for cmd in place_state.commands:
                if cmd.movement_type in ("attack", "command"):
                    clean_coords = cmd.target_coords.strip("() ")
                    if clean_coords:
                        active_target_coords.add(clean_coords)

        # 4. Filtrar bárbaras elegíveis (não atacadas atualmente se skip_active_targets)
        eligible_targets: List[Tuple[int, int]] = []
        for b in barbarians:
            b_coord_str = f"{b.x}|{b.y}"
            if skip_active_targets and b_coord_str in active_target_coords:
                continue
            eligible_targets.append(b.coords_tuple)

        # Se todas as bárbaras já tiverem ataques e ainda houver bárbaras, usa todas
        if not eligible_targets and barbarians:
            eligible_targets = [b.coords_tuple for b in barbarians]

        # 5. Alocação dinâmica de esquadrões
        squad = squad_template or UnitsCount(spear=5, spy=1)
        squads_assigned = allocate_dynamic_squads(
            available_units=place_state.units,
            squad_template=squad,
            targets=eligible_targets,
            max_squads=max_attacks,
        )

        total_cap = sum(sq.carrying_capacity() for _, sq in squads_assigned)

        return RadarFarmPlan(
            village_id=v_id or 0,
            total_barbarians_found=len(barbarians),
            eligible_targets=eligible_targets,
            squads_assigned=squads_assigned,
            total_carrying_capacity=total_cap,
        )

    async def run_radar_farm_cycle(
        self,
        account: TribalAccount,
        radius: float = 15.0,
        squad_template: Optional[UnitsCount] = None,
        max_attacks: int = 30,
        skip_active_targets: bool = True,
        village_id: Optional[int] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Executa um ciclo completo de Radar de Bárbaras com alocação dinâmica de tropas:
        Calcula o plano de alocação e despacha os ataques sequencialmente.
        """
        plan = await self.get_radar_farm_plan(
            account=account,
            radius=radius,
            squad_template=squad_template,
            max_attacks=max_attacks,
            skip_active_targets=skip_active_targets,
            village_id=village_id,
            use_cache=use_cache,
        )

        if not plan.squads_assigned:
            logger.info(
                f"[{account.world}] Radar de Bárbaras (Aldeia {plan.village_id}): "
                f"{plan.total_barbarians_found} bárbaras mapeadas, mas sem tropas suficientes para novos esquadrões."
            )
            return {
                "sent_attacks": 0,
                "total_targets": len(plan.eligible_targets),
                "total_barbarians_found": plan.total_barbarians_found,
                "total_carrying_capacity": 0,
            }

        sent_count = 0
        total_loot_capacity = 0
        logger.info(
            f"[{account.world}] 🚀 A despachar {len(plan.squads_assigned)} micro-ataques pelo Radar de Bárbaras..."
        )

        for target_coords, squad in plan.squads_assigned:
            success = await self.place_manager.send_command(
                account=account,
                target_coords=target_coords,
                units=squad,
                is_attack=True,
                village_id=plan.village_id,
                allow_partial=False,
            )
            if success:
                sent_count += 1
                total_loot_capacity += squad.carrying_capacity()
                logger.info(
                    f"[{account.world}] Saque #{sent_count} via Radar -> ({target_coords[0]}|{target_coords[1]}) "
                    f"[{squad.to_summary_str()} | Cap: {squad.carrying_capacity()}]"
                )
                delay = get_human_delay(2.2, 0.4, 1.2, 3.5)
                await asyncio.sleep(delay)
            else:
                logger.warning(
                    f"[{account.world}] Interrupção no despacho de farm via Radar para ({target_coords[0]}|{target_coords[1]})."
                )
                break

        logger.info(
            f"[{account.world}] ✅ Ciclo de Radar de Bárbaras concluído: "
            f"{sent_count} ataques despachados (Capacidade de saque total: {total_loot_capacity})."
        )
        return {
            "sent_attacks": sent_count,
            "total_targets": len(plan.eligible_targets),
            "total_barbarians_found": plan.total_barbarians_found,
            "total_carrying_capacity": total_loot_capacity,
        }

    def schedule_continuous_radar_farm(
        self,
        scheduler: TaskScheduler,
        account: TribalAccount,
        radius: float = 15.0,
        squad_template: Optional[UnitsCount] = None,
        interval_minutes: float = 5.0,
        max_attacks: int = 30,
        skip_active_targets: bool = True,
        village_id: Optional[int] = None,
    ) -> None:
        """
        Agenda no TaskScheduler o loop contínuo e recorrente de Radar Farming.
        Mantém as micro-tropas sempre em rotação permanente de saques.
        """
        interval_seconds = max(60.0, interval_minutes * 60.0)
        squad = squad_template or UnitsCount(spear=5, spy=1)

        async def continuous_radar_task():
            try:
                await self.run_radar_farm_cycle(
                    account=account,
                    radius=radius,
                    squad_template=squad,
                    max_attacks=max_attacks,
                    skip_active_targets=skip_active_targets,
                    village_id=village_id,
                )
            except Exception as e:
                logger.warning(f"Erro no ciclo contínuo de Radar Farming: {e}")
            finally:
                if scheduler.is_running and not scheduler.is_paused:
                    scheduler.schedule_human_like(
                        name=f"ContinuousRadarFarm-Village-{village_id or 'active'}",
                        priority=TaskPriority.FARM,
                        action=continuous_radar_task,
                        base_seconds=interval_seconds,
                        std_dev=interval_seconds * 0.15,
                        min_seconds=max(30.0, interval_seconds * 0.5),
                        max_seconds=interval_seconds * 1.5,
                    )

        scheduler.schedule(
            name=f"ContinuousRadarFarm-Village-{village_id or 'active'}",
            priority=TaskPriority.FARM,
            action=continuous_radar_task,
            delay_seconds=10.0,
        )
        logger.info(
            f"Radar de Bárbaras contínuo agendado a cada ~{interval_minutes:.1f} minutos (Raio: {radius:.1f} campos)."
        )

    def schedule_auto_farm(
        self,
        scheduler: TaskScheduler,
        account: TribalAccount,
        farm_config: Any,
        village_id: Optional[int] = None,
    ) -> None:
        """
        Agenda no TaskScheduler a execução periódica contínua de ondas de Micro-Farming.
        Suporta 'am_farm', 'place' e 'radar' (saque recorrente dinâmico).
        """
        interval_minutes = getattr(farm_config, "interval_minutes", 10.0)
        interval_seconds = interval_minutes * 60.0
        mode = getattr(farm_config, "mode", "am_farm").lower().strip()

        async def auto_farm_task():
            try:
                if mode == "radar":
                    raw_troops = getattr(farm_config, "custom_troops", {})
                    troops = UnitsCount.from_dict(raw_troops) if isinstance(raw_troops, dict) else UnitsCount(spear=5, spy=1)
                    scan_radius = getattr(farm_config, "map_scan_radius", 15.0)
                    skip_active = getattr(farm_config, "skip_active_targets", True)
                    await self.run_radar_farm_cycle(
                        account=account,
                        radius=scan_radius,
                        squad_template=troops,
                        skip_active_targets=skip_active,
                        village_id=village_id,
                    )
                elif mode == "place":
                    targets = getattr(farm_config, "custom_targets", [])
                    raw_troops = getattr(farm_config, "custom_troops", {})
                    troops = UnitsCount.from_dict(raw_troops) if isinstance(raw_troops, dict) else UnitsCount(spear=5, spy=1)

                    # Se não houver alvos manuais, usa o Scanner de Bárbaras do mapa
                    if not targets and getattr(farm_config, "use_map_scanner", True):
                        if not self.map_manager:
                            from engine.actions.map import MapManager
                            self.map_manager = MapManager()

                        scan_radius = getattr(farm_config, "map_scan_radius", 15.0)
                        await self.map_manager.run_map_farm_wave(
                            account=account,
                            farm_manager=self,
                            troops=troops,
                            radius=scan_radius,
                            village_id=village_id,
                        )
                    else:
                        await self.run_place_farm_wave(
                            account=account,
                            targets=targets,
                            troops=troops,
                            village_id=village_id,
                        )
                else:
                    template = getattr(farm_config, "template", "A")
                    max_dist = getattr(farm_config, "max_distance", 15.0)
                    skip_losses = getattr(farm_config, "skip_losses", True)
                    skip_wall = getattr(farm_config, "skip_wall", True)
                    await self.run_am_farm_wave(
                        account=account,
                        template=template,
                        max_distance=max_dist,
                        skip_losses=skip_losses,
                        skip_wall=skip_wall,
                        village_id=village_id,
                    )
            except Exception as e:
                logger.warning(f"Erro na execução da onda de farm: {e}")
            finally:
                # Reagenda para o próximo ciclo de farm com delay gaussiano
                if scheduler.is_running and not scheduler.is_paused:
                    scheduler.schedule_human_like(
                        name=f"AutoFarm-Village-{village_id or 'active'}",
                        priority=TaskPriority.FARM,
                        action=auto_farm_task,
                        base_seconds=interval_seconds,
                        std_dev=interval_seconds * 0.15,
                        min_seconds=max(30.0, interval_seconds * 0.5),
                        max_seconds=interval_seconds * 1.5,
                    )

        # Agenda a primeira onda de farm após um delay inicial humano (ex.: 15 segundos)
        scheduler.schedule(
            name=f"AutoFarm-Village-{village_id or 'active'}",
            priority=TaskPriority.FARM,
            action=auto_farm_task,
            delay_seconds=15.0,
        )
        logger.info(f"Micro-Farming agendado a cada ~{interval_minutes:.1f} minutos (Modo: {mode.upper()}).")
