"""
Tribal Wars Bot - Runtime Hardening & Console Suppression
Garante a ausência de janelas de terminal/CMD e redireciona stdout/stderr de forma segura.
"""

import io
import os
import sys
from typing import Optional


class SafeStreamWriter(io.TextIOBase):
    """
    Substituto seguro para sys.stdout e sys.stderr quando compilado com --noconsole / GUI pura.
    Evita quebras por 'NoneType has no attribute write' causadas por prints residuais.
    """

    def __init__(self, logger_func=None, encoding: str = "utf-8"):
        super().__init__()
        self._logger_func = logger_func
        self._encoding = encoding
        self._buffer = []

    @property
    def encoding(self) -> str:
        return self._encoding

    def write(self, s: str) -> int:
        if not s:
            return 0
        if self._logger_func:
            cleaned = s.rstrip("\r\n")
            if cleaned:
                self._logger_func(cleaned)
        return len(s)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False

    def readable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True


def suppress_console_and_redirect_streams(logger_func=None) -> None:
    """
    Configura o runtime para execução pura em modo janela.
    Apenas oculta consola e redireciona streams quando em modo standalone (frozen / executável)
    ou quando executado sem consola alocada (sys.stdout is None).
    Em ambiente de desenvolvimento (python ...), mantém o terminal visível e streams intactos.
    """
    is_frozen = getattr(sys, "frozen", False)

    # 1. Redirecionamento seguro de streams apenas se None ou se frozen (executável)
    if sys.stdout is None or is_frozen:
        try:
            devnull = open(os.devnull, "w", encoding="utf-8")
            sys.stdout = devnull
        except Exception:
            sys.stdout = SafeStreamWriter(logger_func=logger_func)

    if sys.stderr is None or is_frozen:
        try:
            devnull = open(os.devnull, "w", encoding="utf-8")
            sys.stderr = devnull
        except Exception:
            sys.stderr = SafeStreamWriter(logger_func=logger_func)

    # 2. Supressão de janela de consola residual no Windows APENAS se for executável (frozen)
    if is_frozen and sys.platform == "win32":
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd != 0:
                # SW_HIDE = 0
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass
