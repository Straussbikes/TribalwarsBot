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
from engine.utils.timing import get_click_jitter, get_human_delay

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

    def schedule_auto_farm(
        self,
        scheduler: TaskScheduler,
        account: TribalAccount,
        farm_config: Any,
        village_id: Optional[int] = None,
    ) -> None:
        """
        Agenda no TaskScheduler a execução periódica contínua de ondas de Micro-Farming.
        """
        interval_minutes = getattr(farm_config, "interval_minutes", 10.0)
        interval_seconds = interval_minutes * 60.0
        mode = getattr(farm_config, "mode", "am_farm").lower().strip()

        async def auto_farm_task():
            try:
                if mode == "place":
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
