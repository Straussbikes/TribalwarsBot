"""
Tribal Wars Mobile Automation Engine - Autenticação Local do Sidecar IPC
Geração de tokens criptográficos efêmeros e proteção do canal de comunicação local.
"""

import json
import logging
import os
from pathlib import Path
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Query, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# Cabeçalhos e esquemas de segurança
AUTH_HEADER_NAME = "X-Engine-Token"
api_key_header = APIKeyHeader(name=AUTH_HEADER_NAME, auto_error=False)
http_bearer = HTTPBearer(auto_error=False)


def generate_auth_token(length: int = 32) -> str:
    """Gera um token criptográfico efêmero de alta entropia."""
    return secrets.token_urlsafe(length)


def write_auth_file(
    file_path: Path,
    host: str,
    port: int,
    token: str,
    pid: Optional[int] = None,
) -> None:
    """
    Grava as credenciais do sidecar num ficheiro JSON local para que
    o processo Tauri descubra dinamicamente a porta e o token de acesso.
    """
    data = {
        "host": host,
        "port": port,
        "url": f"http://{host}:{port}",
        "token": token,
        "pid": pid or os.getpid(),
    }
    try:
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"Ficheiro de autenticação do sidecar gravado em: {file_path.resolve()}")
    except Exception as e:
        logger.error(f"Falha ao gravar ficheiro de autenticação: {e}")


def remove_auth_file(file_path: Path) -> None:
    """Remove o ficheiro de autenticação no encerramento do processo."""
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info("Ficheiro de autenticação do sidecar removido com sucesso.")
    except Exception as e:
        logger.warning(f"Erro ao remover ficheiro de autenticação: {e}")


class TokenVerifier:
    """Dependência injetável do FastAPI para verificar o token efêmero."""

    def __init__(self, valid_token: str):
        self.valid_token = valid_token

    def verify(
        self,
        header_key: Optional[str] = Security(api_key_header),
        bearer_auth: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
        query_token: Optional[str] = Query(None, alias="token"),
    ) -> str:
        """
        Valida o token a partir do header 'X-Engine-Token',
        do header padrão 'Authorization: Bearer <token>'
        ou do parâmetro query '?token=...' (essencial para WebSockets no navegador).
        """
        token_candidate = None
        if header_key:
            token_candidate = header_key
        elif bearer_auth:
            token_candidate = bearer_auth.credentials
        elif query_token:
            token_candidate = query_token

        if not token_candidate or not secrets.compare_digest(token_candidate, self.valid_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de autenticação do sidecar inválido ou em falta.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return token_candidate
