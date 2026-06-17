"""
Autenticação — fluxo único e simples.

  GET /api/auth/login           -> redireciona o browser para o CA (Entra)
  GET /api/auth/entra-callback  -> recebe o code, troca por tokens, lê as
                                   informações do Entra E consulta o CAv4
                                   (alocação/recursos), retornando TUDO num
                                   único JSON.

Sem cookie/sessão: o objetivo é, ao conectar, ver num único response as
informações do usuário (Entra + CA).
"""

from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter
from fastapi.responses import JSONResponse, RedirectResponse

from ca_client import CAUserClient
from config import get_settings
from errors import AppError, ErrorCategory
from oidc import get_oidc_client
from session import PendingLogin, pending_store

logger = logging.getLogger("ca.auth")

router = APIRouter(prefix="/auth", tags=["Autenticação"])


def _extract_user_login(claims: dict) -> str | None:
    """Extrai o 'userLogin' (chave da User API do CA) das claims do Entra."""
    for key in ("preferred_username", "upn", "sub", "login", "samaccountname", "email"):
        value = claims.get(key)
        if value:
            return str(value).split("@")[0] if key in ("upn", "email") else str(value)
    return None


@router.get("/login")
async def login() -> RedirectResponse:
    """Inicia o login: redireciona o browser para o CA (Entra)."""
    settings = get_settings()
    if not settings.is_oidc_configured:
        raise AppError(
            category=ErrorCategory.CONFIG,
            code="OIDC_NOT_CONFIGURED",
            message="OIDC não configurado: faltam variáveis do CA no backend/.env.",
            cause="Uma ou mais variáveis obrigatórias do CA estão ausentes.",
            resolution=(
                "Preencha no backend/.env: "
                + ", ".join(settings.missing_config())
            ),
            detail="missing_config=" + ", ".join(settings.missing_config()),
            http_status=503,
        )

    client = get_oidc_client()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier, code_challenge = client.generate_pkce()

    pending_store.cleanup()
    pending_store.save(PendingLogin(state=state, code_verifier=code_verifier, nonce=nonce))

    # Erros aqui (discovery/rede/TLS) sobem como AppError e são tratados
    # pelo handler global, com categoria e resolução claras.
    url = await client.build_authorization_url(
        state=state, nonce=nonce, code_challenge=code_challenge
    )
    return RedirectResponse(url, status_code=302)


@router.get("/entra-callback")
async def entra_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> JSONResponse:
    """
    Callback do CA. Faz tudo de uma vez e retorna um único JSON:
      - informações do Entra (claims do id_token);
      - informações do CAv4 (alocação/recursos/grupos do usuário).
    """
    if error:
        raise AppError(
            category=ErrorCategory.ENTRA,
            code="ENTRA_AUTH_ERROR",
            message=f"O provedor de identidade retornou um erro: {error}.",
            cause=error_description or "O Entra/CA recusou a autenticação do usuário.",
            resolution="Verifique as credenciais/consentimento do usuário e tente novamente.",
            detail=f"{error}: {error_description}",
            http_status=400,
        )
    if not code or not state:
        raise AppError(
            category=ErrorCategory.ENTRA,
            code="CALLBACK_MISSING_PARAMS",
            message="O callback do CA chegou sem 'code' e/ou 'state'.",
            cause="Chamada ao callback incompleta ou acessada diretamente.",
            resolution="Não acesse o callback manualmente; inicie sempre por /auth/login.",
            http_status=400,
        )

    pending = pending_store.pop(state)
    if pending is None:
        raise AppError(
            category=ErrorCategory.SERVIDOR,
            code="INVALID_OR_EXPIRED_STATE",
            message="O 'state' do login é inválido ou expirou.",
            cause=(
                "O login demorou demais, o servidor reiniciou (store em memória), "
                "ou há suspeita de CSRF."
            ),
            resolution="Refaça o login. Se o backend reinicia muito, considere store persistente.",
            http_status=400,
        )

    client = get_oidc_client()
    # exchange_code e validate_id_token sobem AppError categorizado (ENTRA/rede/TLS).
    tokens = await client.exchange_code(code=code, code_verifier=pending.code_verifier)
    claims = await client.validate_id_token(tokens.get("id_token", ""), nonce=pending.nonce)

    user_login = _extract_user_login(claims)
    logger.info("[v0] login OK: userLogin=%s — consultando CAv4...", user_login)

    # Consulta o CAv4 (User API) com o access_token do usuário.
    ca_info: dict = {"userLogin": user_login}
    access_token = tokens.get("access_token")
    if access_token and user_login:
        ca_info = await _consultar_cav4(access_token, user_login)

    return JSONResponse(
        {
            "status": "ok",
            "entra": {
                "userLogin": user_login,
                "name": claims.get("name"),
                "email": claims.get("email") or claims.get("upn"),
                "claims": claims,
            },
            "ca": ca_info,
        }
    )


async def _consultar_cav4(access_token: str, user_login: str) -> dict:
    """Consulta a alocação/recursos do usuário no CAv4. Resiliente a falhas."""
    ca = CAUserClient(access_token)
    info: dict = {"userLogin": user_login}

    async def _try(label: str, coro):
        try:
            info[label] = await coro
        except AppError as exc:
            # Não derruba a consulta inteira: registra o erro categorizado por campo.
            info[label] = exc.to_dict()["error"]
            logger.warning("[v0] CAv4 %s falhou — %s", label, exc.log_line())

    await _try("resources", ca.resources(user_login))
    await _try("enterprise_groups", ca.enterprise_groups(user_login))
    await _try("user_groups", ca.user_groups(user_login))
    await _try("information_values", ca.information_values(user_login))

    # "alocado" = possui ao menos um recurso autorizado
    resources = info.get("resources")
    info["alocado"] = bool(resources) and not isinstance(resources, dict)
    return info
