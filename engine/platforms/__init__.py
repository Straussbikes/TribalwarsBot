"""
Tribal Wars Mobile Automation Engine - Platform Abstraction Layer
Fábrica modular para resolução e instanciação de adaptadores específicos do sistema operativo.
"""

from __future__ import annotations

import sys
from typing import Optional

from engine.platforms.base import BasePlatformAdapter
from engine.platforms.windows import WindowsPlatformAdapter
from engine.platforms.darwin import MacOSPlatformAdapter
from engine.platforms.linux import LinuxPlatformAdapter

_cached_adapter: Optional[BasePlatformAdapter] = None


def get_platform_adapter(force_platform: Optional[str] = None) -> BasePlatformAdapter:
    """
    Retorna o adaptador de plataforma correspondente ao sistema operativo atual.
    Suporta injeção de plataforma alternativa via 'force_platform' (ex.: para testes unitários).
    """
    global _cached_adapter

    if force_platform is None and _cached_adapter is not None:
        return _cached_adapter

    target_os = (force_platform or sys.platform).lower()

    if target_os.startswith("win"):
        adapter = WindowsPlatformAdapter()
    elif target_os == "darwin":
        adapter = MacOSPlatformAdapter()
    else:
        adapter = LinuxPlatformAdapter()

    if force_platform is None:
        _cached_adapter = adapter

    return adapter


__all__ = [
    "BasePlatformAdapter",
    "WindowsPlatformAdapter",
    "MacOSPlatformAdapter",
    "LinuxPlatformAdapter",
    "get_platform_adapter",
]
