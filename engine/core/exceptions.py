"""
Tribal Wars Mobile Automation Engine - Exceções Personalizadas
Define a hierarquia de exceções para controlo de fluxo, segurança e rede.
"""

from typing import Optional


class TribalWarsException(Exception):
    """Exceção base para todos os erros da engine Tribal Wars."""

    def __init__(self, message: str, raw_response: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.raw_response = raw_response

    def __str__(self) -> str:
        return self.message


class BotProtectionError(TribalWarsException):
    """
    Acionada quando o servidor do jogo devolve um ecrã de verificação de bot
    (ex.: id="bot_protect", name="bot_check" ou captcha visual).
    Deve causar a pausa imediata do Scheduler e notificar o utilizador/GUI.
    """

    def __init__(
        self,
        message: str = "Proteção anti-bot (captcha) detetada!",
        captcha_url: Optional[str] = None,
        html_snippet: Optional[str] = None,
    ):
        super().__init__(message, raw_response=html_snippet)
        self.captcha_url = captcha_url
        self.html_snippet = html_snippet


class SessionExpiredError(TribalWarsException):
    """
    Acionada quando a sessão ou cookie 'sid' expirou, ou o jogo redireciona
    para o ecrã de boas-vindas / login.
    """

    def __init__(self, message: str = "A sessão expirou (cookie 'sid' inválido)."):
        super().__init__(message)


class GameMaintenanceError(TribalWarsException):
    """Acionada quando os servidores do Tribal Wars estão em manutenção ou offline."""

    def __init__(self, message: str = "O servidor do jogo está em manutenção."):
        super().__init__(message)


class RateLimitError(TribalWarsException):
    """
    Acionada quando o servidor responde com HTTP 429 ou throttling por requisições
    muito frequentes.
    """

    def __init__(
        self,
        message: str = "Limite de taxa atingido (HTTP 429).",
        retry_after: float = 30.0,
    ):
        super().__init__(message)
        self.retry_after = retry_after


class ActionFailedError(TribalWarsException):
    """
    Acionada quando uma ação específica no jogo foi rejeitada pela lógica do servidor
    (ex.: 'Recursos insuficientes', 'Edifício já em evolução', 'Alvo inválido').
    """

    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(message)
        self.error_code = error_code


class NetworkTimeoutError(TribalWarsException):
    """Acionada quando ocorrem timeouts de rede ou falhas transitórias de conexão."""

    def __init__(self, message: str = "Timeout na comunicação com os servidores."):
        super().__init__(message)
