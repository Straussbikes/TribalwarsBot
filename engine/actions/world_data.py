"""
Tribal Wars Mobile Automation Engine - WorldDataWorker
Módulo de ingestão e sincronização assíncrona de dados públicos oficiais do mundo (Dumps de Mapa).
Descarrega village.txt, player.txt e ally.txt com suporte a ETag/If-Modified-Since e compressão.
"""

import asyncio
from dataclasses import dataclass
import gzip
import logging
import time
from typing import List, Optional, Tuple
import urllib.parse
import httpx

from engine.core.models import TaskPriority
from engine.core.scheduler import TaskScheduler
from engine.storage.world_database import (
    WorldAllyRecord,
    WorldDatabase,
    WorldPlayerRecord,
    WorldVillageRecord,
)

logger = logging.getLogger("TribalWarsBot.WorldDataWorker")


def parse_world_dump_villages(raw_text: str) -> List[WorldVillageRecord]:
    """
    Interpreta o ficheiro público village.txt do Tribal Wars.
    Formato: $id, $name, $x, $y, $player_id, $points, $rank
    Strings vêm URL-encoded (ex.: 'Aldeia+de+B%C3%A1rbaros').
    """
    records: List[WorldVillageRecord] = []
    if not raw_text:
        return records

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 6:
            continue
        try:
            v_id = int(parts[0])
            name = urllib.parse.unquote_plus(parts[1])
            x = int(parts[2])
            y = int(parts[3])
            player_id = int(parts[4])
            points = int(parts[5])
            rank = int(parts[6]) if len(parts) > 6 else 0
            records.append(
                WorldVillageRecord(
                    id=v_id,
                    name=name,
                    x=x,
                    y=y,
                    player_id=player_id,
                    points=points,
                    rank=rank,
                )
            )
        except (ValueError, IndexError):
            continue

    return records


def parse_world_dump_players(raw_text: str) -> List[WorldPlayerRecord]:
    """
    Interpreta o ficheiro público player.txt do Tribal Wars.
    Formato: $id, $name, $ally_id, $villages_count, $points, $rank
    """
    records: List[WorldPlayerRecord] = []
    if not raw_text:
        return records

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 5:
            continue
        try:
            p_id = int(parts[0])
            name = urllib.parse.unquote_plus(parts[1])
            ally_id = int(parts[2])
            villages = int(parts[3])
            points = int(parts[4])
            rank = int(parts[5]) if len(parts) > 5 else 0
            records.append(
                WorldPlayerRecord(
                    id=p_id,
                    name=name,
                    ally_id=ally_id,
                    villages_count=villages,
                    points=points,
                    rank=rank,
                )
            )
        except (ValueError, IndexError):
            continue

    return records


def parse_world_dump_allies(raw_text: str) -> List[WorldAllyRecord]:
    """
    Interpreta o ficheiro público ally.txt do Tribal Wars.
    Formato: $id, $name, $tag, $members_count, $villages_count, $points, $all_points, $rank
    """
    records: List[WorldAllyRecord] = []
    if not raw_text:
        return records

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 7:
            continue
        try:
            a_id = int(parts[0])
            name = urllib.parse.unquote_plus(parts[1])
            tag = urllib.parse.unquote_plus(parts[2])
            members = int(parts[3])
            villages = int(parts[4])
            points = int(parts[5])
            all_points = int(parts[6])
            rank = int(parts[7]) if len(parts) > 7 else 0
            records.append(
                WorldAllyRecord(
                    id=a_id,
                    name=name,
                    tag=tag,
                    members_count=members,
                    villages_count=villages,
                    points=points,
                    all_points=all_points,
                    rank=rank,
                )
            )
        except (ValueError, IndexError):
            continue

    return records


@dataclass
class WorldSyncResult:
    """Resultado da operação de sincronização de dados públicos do mundo."""

    world: str
    snapshot_id: Optional[int] = None
    is_updated: bool = False
    villages_count: int = 0
    players_count: int = 0
    allies_count: int = 0
    elapsed_seconds: float = 0.0
    error: Optional[str] = None

    @property
    def error_message(self) -> Optional[str]:
        return self.error


class WorldDataWorker:
    """
    Serviço assíncrono para ingestão periódica dos dumps oficiais de mundo.
    """

    def __init__(self, db: Optional[WorldDatabase] = None):
        self.db = db or WorldDatabase()

    def _build_base_url(self, world: str, domain: str = "tribalwars.com.pt") -> str:
        """Constrói o URL base para os ficheiros de mapa públicos."""
        clean_w = world.lower().strip()
        clean_d = domain.lower().strip()
        if clean_d.startswith("http://") or clean_d.startswith("https://"):
            clean_d = clean_d.split("://")[1]

        # Se o world já estiver embutido no domínio (ex: pt117.tribalwars.com.pt)
        if clean_d.startswith(f"{clean_w}."):
            return f"https://{clean_d}/map"
        return f"https://{clean_w}.{clean_d}/map"

    async def _fetch_dump_file(
        self,
        client: httpx.AsyncClient,
        url: str,
        cached_etag: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Descarrega um ficheiro de dump com suporte a ETag e descompressão gzip.
        Retorna (conteudo_texto, novo_etag, modificado).
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TribalWarsAssistant/2.0",
            "Accept-Encoding": "gzip, deflate",
        }
        if cached_etag:
            headers["If-None-Match"] = cached_etag

        try:
            resp = await client.get(url, headers=headers, timeout=25.0)
            if resp.status_code == 304:
                return None, cached_etag, False

            if resp.status_code != 200:
                logger.warning(f"Resposta inesperada ao transferir {url}: HTTP {resp.status_code}")
                return None, None, False

            new_etag = resp.headers.get("ETag") or resp.headers.get("etag")
            content_bytes = resp.content

            # Se veio comprimido em gzip sem descompressão automática
            if content_bytes.startswith(b"\x1f\x8b"):
                try:
                    content_bytes = gzip.decompress(content_bytes)
                except Exception as e:
                    logger.debug(f"Aviso ao descompactar stream gzip: {e}")

            text = content_bytes.decode("utf-8", errors="replace")
            return text, new_etag, True

        except Exception as e:
            logger.warning(f"Erro ao descarregar dump de {url}: {e}")
            return None, None, False

    async def sync_world_data(
        self,
        world: str,
        domain: str = "tribalwars.com.pt",
        force: bool = False,
        custom_timestamp: Optional[float] = None,
    ) -> WorldSyncResult:
        """
        Sincroniza os dumps públicos oficiais (`village.txt`, `player.txt`, `ally.txt`)
        e persiste um novo snapshot atómico na base de dados SQLite.
        """
        start_time = time.time()
        base_url = self._build_base_url(world, domain)
        latest_snap = self.db.get_latest_snapshot(world)

        cached_etags = {
            "village": latest_snap.get("etag_village") if latest_snap and not force else None,
            "player": latest_snap.get("etag_player") if latest_snap and not force else None,
            "ally": latest_snap.get("etag_ally") if latest_snap and not force else None,
        }

        logger.info(f"[{world}] A sincronizar dumps de dados públicos de {base_url}...")

        async with httpx.AsyncClient(follow_redirects=True) as client:
            v_task = self._fetch_dump_file(client, f"{base_url}/village.txt", cached_etags["village"])
            p_task = self._fetch_dump_file(client, f"{base_url}/player.txt", cached_etags["player"])
            a_task = self._fetch_dump_file(client, f"{base_url}/ally.txt", cached_etags["ally"])

            (v_text, v_etag, v_mod), (p_text, p_etag, p_mod), (a_text, a_etag, a_mod) = await asyncio.gather(
                v_task, p_task, a_task
            )

        # Se nenhum ficheiro foi modificado (HTTP 304), não necessita de gravar novo snapshot
        if not (v_mod or p_mod or a_mod) and not force and latest_snap is not None:
            elapsed = time.time() - start_time
            logger.info(f"[{world}] Dados públicos atualizados (HTTP 304 Not Modified). Snapshot #{latest_snap['id']} mantido.")
            return WorldSyncResult(
                world=world,
                snapshot_id=latest_snap["id"],
                is_updated=False,
                villages_count=latest_snap.get("villages_count", 0),
                players_count=latest_snap.get("players_count", 0),
                allies_count=latest_snap.get("allies_count", 0),
                elapsed_seconds=elapsed,
            )

        if not v_text and not p_text and not a_text and not force:
            elapsed = time.time() - start_time
            return WorldSyncResult(
                world=world,
                error="Falha na transferência dos ficheiros de mapa públicos.",
                elapsed_seconds=elapsed,
            )

        # Parsing estruturado
        villages = parse_world_dump_villages(v_text or "")
        players = parse_world_dump_players(p_text or "")
        allies = parse_world_dump_allies(a_text or "")

        new_etags = {
            "village": v_etag or cached_etags["village"] or "",
            "player": p_etag or cached_etags["player"] or "",
            "ally": a_etag or cached_etags["ally"] or "",
        }

        snap_id = self.db.save_world_snapshot(
            world=world,
            villages=villages,
            players=players,
            allies=allies,
            etags=new_etags,
            custom_timestamp=custom_timestamp,
        )

        elapsed = time.time() - start_time
        return WorldSyncResult(
            world=world,
            snapshot_id=snap_id,
            is_updated=True,
            villages_count=len(villages),
            players_count=len(players),
            allies_count=len(allies),
            elapsed_seconds=elapsed,
        )

    def schedule_periodic_sync(
        self,
        scheduler: TaskScheduler,
        world: str,
        domain: str = "tribalwars.com.pt",
        interval_hours: float = 4.0,
    ) -> None:
        """
        Agenda no TaskScheduler a sincronização periódica não-bloqueante dos dados públicos.
        """
        interval_seconds = max(3600.0, interval_hours * 3600.0)

        async def sync_task():
            try:
                await self.sync_world_data(world=world, domain=domain)
            except Exception as e:
                logger.warning(f"Erro na sincronização periódica de dados de mundo ({world}): {e}")
            finally:
                if scheduler.is_running and not scheduler.is_paused:
                    scheduler.schedule_human_like(
                        name=f"WorldDataSync-{world}",
                        priority=TaskPriority.BACKGROUND,
                        action=sync_task,
                        base_seconds=interval_seconds,
                        std_dev=300.0,
                        min_seconds=interval_seconds * 0.8,
                        max_seconds=interval_seconds * 1.2,
                    )

        scheduler.schedule(
            name=f"WorldDataSync-{world}",
            priority=TaskPriority.BACKGROUND,
            action=sync_task,
            delay_seconds=30.0,
        )
        logger.info(f"[{world}] Sincronização periódica de dados do mundo agendada a cada ~{interval_hours:.1f} horas.")
