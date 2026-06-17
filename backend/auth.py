"""
Autenticação — fluxo único e simples (somente backend).

  GET /auth/login           -> redireciona o browser para o CA (Entra)
  GET /auth/entra-callback  -> recebe o code, troca por tokens, lê as
                               informações do Entra E consulta o CAv4
                               (alocação/recursos), imprimindo TUDO no
                               terminal e retornando também num único JSON.

Sem cookie/sessão e sem frontend: o objetivo é, ao conectar, ver no terminal
(tela preta) todas as informações que o CAv4 conseguiu obter do Entra.
"""

from __future__ import annotations

import json
import logging
import secrets

from fastapi import APIRouter
from fastapi.responses import JSONResponse, RedirectResponse

from ca_client import CAUserClient
from config import get_settings
from errors import AppError, ErrorCategory
from graph_client import GraphClient
from oidc import get_oidc_client
from session import PendingLogin, pending_store

logger = logging.getLogger("ca.auth")

router = APIRouter(prefix="/auth", tags=["Autenticação"])


# Catálogo das consultas feitas ao CAv4. Centraliza, para cada rótulo:
#   - method     : método HTTP usado (GET/POST)
#   - path       : caminho do endpoint (com {userLogin} a ser substituído)
#   - titulo     : nome amigável, fácil de ler na tela
#   - descricao  : o que aquela API retorna, em português
# A ORDEM aqui é a ordem em que as consultas rodam e aparecem na tela.
CAV4_CONSULTAS: list[dict] = [
    {
        "label": "user_groups",
        "method": "GET",
        "path": "/api/users/{userLogin}/user-groups",
        "titulo": "GRUPOS DE USUARIO (User Groups)",
        "descricao": "Grupos de usuário aos quais a pessoa está associada.",
    },
    {
        "label": "information_values",
        "method": "GET",
        "path": "/api/users/{userLogin}/information-values",
        "titulo": "VALORES DE INFORMACAO (Information Values)",
        "descricao": "Valores de informação autorizados ao usuário.",
    },
    {
        "label": "admin_user_details",
        "method": "GET",
        "path": "/api/admin/users/{userLogin}",
        "titulo": "DETALHES DO USUARIO (Admin)",
        "descricao": "Dados cadastrais do usuário (lotação, gerente/supervisor, empresa, etc.).",
    },
    {
        "label": "admin_enterprise_groups",
        "method": "GET",
        "path": "/api/admin/users/{userLogin}/enterprise-groups",
        "titulo": "ENTERPRISE GROUPS (Admin)",
        "descricao": "Grupos corporativos (empresa) do usuário, via Admin API.",
    },
    {
        "label": "admin_roles",
        "method": "GET",
        "path": "/api/admin/users/{userLogin}/roles",
        "titulo": "PAPEIS (Roles via Admin)",
        "descricao": "Lista os papéis/perfis do usuário (GET, sem corpo).",
    },
    {
        "label": "graph_me",
        "method": "GET",
        "path": "https://graph.microsoft.com/v1.0/me",
        "titulo": "PERFIL ENTRA ID (Microsoft Graph /me)",
        "descricao": "Perfil completo do usuário no Entra ID: cargo, departamento, empresa, telefone, etc.",
    },
    {
        "label": "graph_manager",
        "method": "GET",
        "path": "https://graph.microsoft.com/v1.0/me/manager",
        "titulo": "GERENTE/SUPERVISOR (Microsoft Graph /me/manager)",
        "descricao": "Gerente/supervisor direto do usuário, conforme cadastrado no Entra ID.",
    },
]


def _extract_user_login(claims: dict) -> str | None:
    """
    Extrai o 'userLogin' (chave da User API do CA) das claims do Entra.

    IMPORTANTE: o CAv4 identifica o usuário pela CHAVE/matrícula (ex.: "GFZ3"),
    NÃO pelo e-mail. O Entra entrega essa chave na claim 'user_login'. Por isso
    ela é a primeira a ser tentada; o e-mail/upn ficam só como último recurso.
    """
    # Claims que costumam conter a chave do CA (matrícula), em ordem de preferência.
    for key in ("user_login", "login", "samaccountname", "onpremisesamaccountname"):
        value = claims.get(key)
        if value:
            return str(value)

    # Fallback: deriva da parte local do e-mail/upn (pode não bater no CA).
    for key in ("preferred_username", "upn", "email", "sub"):
        value = claims.get(key)
        if value:
            return str(value).split("@")[0]
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

    payload = {
        "status": "ok",
        "entra": {
            "userLogin": user_login,
            "name": claims.get("name"),
            "email": claims.get("email") or claims.get("upn"),
            "claims": claims,
        },
        "ca": ca_info,
    }

    # Imprime TUDO que o CAv4 recebeu do Entra no terminal (tela preta).
    _imprimir_no_terminal(payload)

    return JSONResponse(payload)


def _imprimir_no_terminal(payload: dict) -> None:
    """
    Despeja no terminal (stdout), de forma legível, TODAS as informações que o
    CAv4 conseguiu obter do Entra e da própria User API do CA. Como este projeto
    é só backend, o terminal é a "tela" onde o resultado do login é exibido.
    """
    entra = payload.get("entra", {})
    ca = payload.get("ca", {})
    claims = entra.get("claims", {}) or {}

    linha = "=" * 78
    print("\n" + linha, flush=True)
    print("  LOGIN CONCLUIDO — INFORMACOES RECEBIDAS DO ENTRA (via CAv4)", flush=True)
    print(linha, flush=True)

    # --- Identificacao basica do usuario (Entra) -------------------------
    print("\n[ ENTRA — IDENTIDADE ]", flush=True)
    print(f"  userLogin : {entra.get('userLogin')}", flush=True)
    print(f"  nome      : {entra.get('name')}", flush=True)
    print(f"  email     : {entra.get('email')}", flush=True)

    # --- Todas as claims do id_token (cru, completo) ---------------------
    print("\n[ ENTRA — CLAIMS COMPLETAS DO id_token ]", flush=True)
    if claims:
        for chave in sorted(claims.keys()):
            print(f"  {chave:24} = {claims[chave]}", flush=True)
    else:
        print("  (nenhuma claim retornada)", flush=True)

    # --- Resultado da consulta CAv4 (uma secao bem clara por API) --------
    print("\n" + linha, flush=True)
    print("  CAv4 — RESULTADO POR API", flush=True)
    print(linha, flush=True)

    sub = "-" * 78
    for indice, consulta in enumerate(CAV4_CONSULTAS, start=1):
        entry = ca.get(consulta["label"]) or {}
        endpoint = entry.get("endpoint", f"{consulta['method']} {consulta['path']}")
        status = "OK" if entry.get("ok") else "FALHA"
        # Cabecalho destacado: numero, titulo amigavel, status, endpoint e descricao.
        print("\n" + sub, flush=True)
        print(f"  API #{indice}: {consulta['titulo']}   [{status}]", flush=True)
        print(f"  Endpoint : {endpoint}", flush=True)
        print(f"  O que e  : {consulta['descricao']}", flush=True)
        print(sub, flush=True)
        valor = entry.get("data") if entry.get("ok") else entry.get("error")
        print(_indentar(json.dumps(valor, indent=2, ensure_ascii=False, default=str)), flush=True)

    # --- JSON completo (igual ao retornado na resposta HTTP) -------------
    print("\n[ JSON COMPLETO DA RESPOSTA ]", flush=True)
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str), flush=True)
    print("\n" + linha + "\n", flush=True)


def _indentar(texto: str, espacos: int = 5) -> str:
    """Aplica indentacao a cada linha de um bloco de texto (para alinhar no log)."""
    prefixo = " " * espacos
    return "\n".join(prefixo + linha for linha in texto.splitlines())


async def _consultar_cav4(access_token: str, user_login: str) -> dict:
    """
    Consulta a alocação/recursos do usuário no CAv4. Resiliente a falhas.

    Cada campo do resultado deixa CLARO de qual API veio, no formato:
        { "endpoint": "GET /api/users/{userLogin}/...",
          "titulo": "RECURSOS (Resources)",
          "descricao": "...",
          "ok": true|false,
          "data": <resposta> }   # ou "error": <erro categorizado> se falhar
    """
    ca = CAUserClient(access_token)
    graph = GraphClient(access_token)
    info: dict = {"userLogin": user_login}

    # Rótulo -> função do client que faz a chamada (segue a ordem do catálogo).
    chamadas = {
        "user_groups": ca.user_groups(user_login),
        "information_values": ca.information_values(user_login),
        "admin_user_details": ca.admin_user_details(user_login),
        "admin_enterprise_groups": ca.admin_enterprise_groups(user_login),
        "admin_roles": ca.admin_roles(user_login),
        "graph_me": graph.me(),
        "graph_manager": graph.me_manager(),
    }

    for consulta in CAV4_CONSULTAS:
        label = consulta["label"]
        # Endpoint legível: método + caminho real (com o userLogin resolvido).
        endpoint = f"{consulta['method']} {consulta['path'].format(userLogin=user_login)}"
        base = {
            "endpoint": endpoint,
            "titulo": consulta["titulo"],
            "descricao": consulta["descricao"],
        }
        try:
            info[label] = {**base, "ok": True, "data": await chamadas[label]}
        except AppError as exc:
            # Não derruba a consulta inteira: registra o erro categorizado por campo.
            info[label] = {**base, "ok": False, "error": exc.to_dict()["error"]}
            logger.warning("[v0] CAv4 %s (%s) falhou — %s", label, endpoint, exc.log_line())

    return info
