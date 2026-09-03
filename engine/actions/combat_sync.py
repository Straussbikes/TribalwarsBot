"""
Tribal Wars Mobile Automation Engine - ClockSynchronizer (screen=place)
Sincronização de alta precisão com o relógio oficial do servidor do Tribal Wars.
Mede latência de ida e volta (RTT), calcula o desvio temporal (clock offset / drift)
e fornece agendamento sub-milissegundo com técnica híbrida asyncio + spin-wait.
"""

from dataclasses import dataclass, field
import datetime
import email.utils
import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Padrões para extração de carimbos temporais do servidor a partir de scripts e DOM
TIMING_INITIAL_MS_REGEX = re.compile(r'Timing\.initial_server_time\s*=\s*(\d+)', re.IGNORECASE)
TIMING_RESET_TICK_REGEX = re.compile(r'Timing\.resetTick\((\d+)\)', re.IGNORECASE)
SERVER_TIME_HTML_REGEX = re.compile(r'id=["\']serverTime["\'][^>]*>(\d{1,2}):(\d{2}):(\d{2})<', re.IGNORECASE)
SERVER_DATE_HTML_REGEX = re.compile(r'id=["\']serverDate["\'][^>]*>(\d{1,2})[/\.](\d{1,2})[/\.](\d{4})<', re.IGNORECASE)


@dataclass
class ClockSyncStats:
    """Telemetria e estado atual da sincronização de relógio."""
    rtt_ms: float = 50.0
    rtt_min_ms: float = 50.0
    rtt_max_ms: float = 50.0
    clock_offset_seconds: float = 0.0
    samples_count: int = 0
    last_sync_timestamp: float = 0.0
    is_synchronized: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rtt_ms": round(self.rtt_ms, 2),
            "rtt_min_ms": round(self.rtt_min_ms, 2),
            "rtt_max_ms": round(self.rtt_max_ms, 2),
            "clock_offset_seconds": round(self.clock_offset_seconds, 4),
            "samples_count": self.samples_count,
            "last_sync_timestamp": self.last_sync_timestamp,
            "is_synchronized": self.is_synchronized,
        }


class ClockSynchronizer:
    """
    Sincronizador de relógio com o servidor do Tribal Wars.
    Utiliza algoritmo de suavização EWMA para RTT e desvio de relógio.
    """

    def __init__(self, ewma_alpha: float = 0.25):
        self.alpha: float = ewma_alpha
        self.rtt_ms: float = 50.0
        self.rtt_min_ms: float = 9999.0
        self.rtt_max_ms: float = 0.0
        self.clock_offset: float = 0.0
        self.samples: List[float] = []
        self.samples_count: int = 0
        self.last_sync_time: float = 0.0
        self.is_synchronized: bool = False

    def record_sample(
        self,
        t_send: float,
        t_recv: float,
        server_ts: Optional[float] = None,
    ) -> None:
        """
        Regista uma amostra de medição HTTP.
        t_send: timestamp local no momento do envio (time.time())
        t_recv: timestamp local no momento da receção (time.time())
        server_ts: timestamp do servidor em segundos (extraído do header ou HTML)
        """
        rtt = max(0.001, t_recv - t_send)
        rtt_ms = rtt * 1000.0

        # Atualiza métricas de RTT
        if self.samples_count == 0:
            self.rtt_ms = rtt_ms
            self.rtt_min_ms = rtt_ms
            self.rtt_max_ms = rtt_ms
        else:
            self.rtt_ms = self.alpha * rtt_ms + (1.0 - self.alpha) * self.rtt_ms
            self.rtt_min_ms = min(self.rtt_min_ms, rtt_ms)
            self.rtt_max_ms = max(self.rtt_max_ms, rtt_ms)

        self.samples.append(rtt_ms)
        if len(self.samples) > 50:
            self.samples.pop(0)

        # Atualiza desvio temporal do relógio se houver timestamp do servidor
        if server_ts is not None and server_ts > 0:
            # O ponto médio da requisição em tempo local
            t_mid = t_send + (rtt / 2.0)
            measured_offset = server_ts - t_mid

            if not self.is_synchronized:
                self.clock_offset = measured_offset
                self.is_synchronized = True
            else:
                self.clock_offset = self.alpha * measured_offset + (1.0 - self.alpha) * self.clock_offset

            self.last_sync_time = time.time()
            logger.debug(
                f"[ClockSync] Amostra: RTT={rtt_ms:.1f}ms | Offset={self.clock_offset:+.3f}s | "
                f"Servidor={server_ts:.3f} | LocalMid={t_mid:.3f}"
            )

        self.samples_count += 1

    def parse_server_time_from_headers_or_html(
        self,
        headers: Optional[Dict[str, Any]] = None,
        html: Optional[str] = None,
        game_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[float]:
        """
        Extrai o timestamp do servidor a partir dos headers HTTP ou do HTML/game_data.
        Retorna o timestamp em segundos (float com precisão de milissegundos se disponível).
        """
        # 1. Scripts JavaScript de Timing no HTML (resolução de milissegundos)
        if html:
            m_init = TIMING_INITIAL_MS_REGEX.search(html)
            if m_init:
                try:
                    return int(m_init.group(1)) / 1000.0
                except (ValueError, TypeError):
                    pass

            m_tick = TIMING_RESET_TICK_REGEX.search(html)
            if m_tick:
                try:
                    return int(m_tick.group(1)) / 1000.0
                except (ValueError, TypeError):
                    pass

        # 2. game_data["time_generated"] se disponível
        if game_data and isinstance(game_data, dict):
            tg = game_data.get("time_generated") or game_data.get("time")
            if tg is not None:
                try:
                    val = float(tg)
                    # Se valor em milissegundos (> 10^11)
                    if val > 1e11:
                        return val / 1000.0
                    return val
                except (ValueError, TypeError):
                    pass

        # 3. Header HTTP 'Date'
        if headers:
            date_val = headers.get("Date") or headers.get("date")
            if date_val:
                try:
                    parsed_dt = email.utils.parsedate_to_datetime(str(date_val))
                    return parsed_dt.timestamp()
                except Exception:
                    pass

        # 4. Elementos HTML serverTime / serverDate
        if html:
            m_time = SERVER_TIME_HTML_REGEX.search(html)
            m_date = SERVER_DATE_HTML_REGEX.search(html)
            if m_time and m_date:
                try:
                    h, m, s = int(m_time.group(1)), int(m_time.group(2)), int(m_time.group(3))
                    day, month, year = int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3))
                    dt = datetime.datetime(year, month, day, h, m, s)
                    return dt.timestamp()
                except Exception:
                    pass

        return None

    def get_server_time(self) -> float:
        """Calcula o tempo estimado atual do servidor em segundos."""
        return time.time() + self.clock_offset

    def server_to_local_time(self, server_timestamp: float) -> float:
        """Converte um timestamp do servidor no timestamp local equivalente."""
        return server_timestamp - self.clock_offset

    def local_to_server_time(self, local_timestamp: float) -> float:
        """Converte um timestamp local no timestamp do servidor equivalente."""
        return local_timestamp + self.clock_offset

    def calculate_launch_time(
        self,
        target_impact_server_ts: float,
        travel_duration_seconds: float,
    ) -> float:
        """
        Calcula o instante em tempo local exato para despachar a requisição de confirmação,
        compensando a metade da latência RTT estimada (tempo de ida do pacote até ao servidor).
        Fórmula: launch_local = target_server_ts - travel_duration - offset - (rtt / 2)
        """
        departure_server_ts = target_impact_server_ts - travel_duration_seconds
        departure_local_ts = self.server_to_local_time(departure_server_ts)
        one_way_latency = (self.rtt_ms / 1000.0) / 2.0
        return departure_local_ts - one_way_latency

    async def spin_wait_until(self, target_timestamp: float) -> float:
        """
        Aguarda com precisão milimétrica até ao target_timestamp em tempo local.
        Usa asyncio.sleep para o grosso da espera e spin-wait de CPU nos últimos 15ms.
        Retorna a diferença em segundos entre o tempo real de saída e o target (jitter real).
        """
        import asyncio

        while True:
            remaining = target_timestamp - time.time()
            if remaining <= 0.015:
                # Menos de 15ms: entra em spin-wait
                break
            # Dorme conservadoramente deixando margem de 10ms
            sleep_chunk = remaining - 0.010
            await asyncio.sleep(sleep_chunk)

        # Spin-wait de precisão máxima usando time.perf_counter
        while time.time() < target_timestamp:
            pass

        now = time.time()
        drift = now - target_timestamp
        return drift

    def get_stats(self) -> ClockSyncStats:
        """Retorna o estado e estatísticas do sincronizador."""
        return ClockSyncStats(
            rtt_ms=self.rtt_ms,
            rtt_min_ms=self.rtt_min_ms if self.samples_count > 0 else 50.0,
            rtt_max_ms=self.rtt_max_ms if self.samples_count > 0 else 50.0,
            clock_offset_seconds=self.clock_offset,
            samples_count=self.samples_count,
            last_sync_timestamp=self.last_sync_time,
            is_synchronized=self.is_synchronized,
        )
