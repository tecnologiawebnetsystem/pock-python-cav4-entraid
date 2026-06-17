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
from typing import Any

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
        "fonte": "cav4",
        "method": "GET",
        "path": "/api/users/{userLogin}/user-groups",
        "titulo": "GRUPOS DE USUARIO (User Groups)",
        "descricao": "Grupos de usuário aos quais a pessoa está associada.",
    },
    {
        "label": "information_values",
        "fonte": "cav4",
        "method": "GET",
        "path": "/api/users/{userLogin}/information-values",
        "titulo": "VALORES DE INFORMACAO (Information Values)",
        "descricao": "Valores de informação autorizados ao usuário.",
    },
    {
        "label": "admin_user_details",
        "fonte": "cav4",
        "method": "GET",
        "path": "/api/admin/users/{userLogin}",
        "titulo": "DETALHES DO USUARIO (Admin)",
        "descricao": "Dados cadastrais do usuário (lotação, gerente/supervisor, empresa, etc.).",
    },
    {
        "label": "admin_enterprise_groups",
        "fonte": "cav4",
        "method": "GET",
        "path": "/api/admin/users/{userLogin}/enterprise-groups",
        "titulo": "ENTERPRISE GROUPS (Admin)",
        "descricao": "Grupos corporativos (empresa) do usuário, via Admin API.",
    },
    {
        "label": "admin_roles",
        "fonte": "cav4",
        "method": "GET",
        "path": "/api/admin/users/{userLogin}/roles",
        "titulo": "PAPEIS (Roles via Admin)",
        "descricao": "Lista os papéis/perfis do usuário (GET, sem corpo).",
    },
    {
        "label": "graph_me",
        "fonte": "graph",
        "method": "GET",
        "path": "https://graph.microsoft.com/v1.0/users/{userPrincipalName}",
        "titulo": "PERFIL ENTRA ID (Graph — /users/{upn})",
        "descricao": "Perfil completo no Entra ID (cargo, depto, empresa...). Chamado com o e-mail vindo do CAv4.",
    },
    {
        "label": "graph_manager",
        "fonte": "graph",
        "method": "GET",
        "path": "https://graph.microsoft.com/v1.0/users/{userPrincipalName}/manager",
        "titulo": "GERENTE/SUPERVISOR (Graph — /users/{upn}/manager)",
        "descricao": "Gerente/supervisor direto no Entra ID. Chamado com o e-mail vindo do CAv4.",
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


def _extract_upn(claims: dict) -> str | None:
    """
    Extrai o e-mail/UPN do usuário das claims do Entra.

    Usado pelo acesso INDEPENDENTE ao Microsoft Graph (app-only), que busca o
    usuário por GET /users/{userPrincipalName}. Aqui queremos o identificador
    COMPLETO (com @dominio), diferente do userLogin (matrícula) do CA.
    """
    for key in ("upn", "preferred_username", "email", "unique_name"):
        value = claims.get(key)
        if value and "@" in str(value):
            return str(value)
    # Último recurso: qualquer um desses, mesmo sem @.
    for key in ("upn", "preferred_username", "email"):
        value = claims.get(key)
        if value:
            return str(value)
    return None


def _upn_do_cav4(detalhes: Any) -> str | None:
    """
    Extrai o e-mail/UPN do usuário a partir da resposta de DETALHES do CAv4
    (admin_user_details). É este e-mail, vindo do CAv4, que será usado para
    chamar o Entra/Graph em seguida — encadeando os dois processos.

    O CA pode nomear o campo de várias formas, então tentamos as mais comuns.
    """
    if not isinstance(detalhes, dict):
        return None
    # Chaves candidatas para o e-mail/login do usuário nos detalhes do CA.
    for key in (
        "email", "mail", "userPrincipalName", "upn", "login",
        "userLogin", "emailAddress", "principalName",
    ):
        value = detalhes.get(key)
        if value and "@" in str(value):
            return str(value)
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
    user_upn = _extract_upn(claims)
    logger.info("[v0] login OK: userLogin=%s — Fase 1 CAv4, depois Fase 2 Entra...", user_login)

    # Consulta encadeada: primeiro CAv4, depois Entra (com o e-mail vindo do CAv4).
    # O upn das claims entra apenas como FALLBACK, caso o CAv4 não traga e-mail.
    ca_info: dict = {"userLogin": user_login}
    access_token = tokens.get("access_token")
    if access_token and user_login:
        ca_info = await _consultar_cav4(access_token, user_login, upn_fallback=user_upn)

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


async def _consultar_cav4(access_token: str, user_login: str, upn_fallback: str | None = None) -> dict:
    """
    Consulta o usuário em DUAS FASES, encadeadas (sem processar duas vezes):

      FASE 1 — CAv4: roda todas as consultas do CA (grupos, valores, detalhes,
               enterprise groups, papéis) com o access_token do usuário.

      FASE 2 — Entra/Graph: usa o e-mail que VEIO do CAv4 (dos Detalhes do
               Usuário) como parâmetro para consultar o perfil e o gerente no
               Microsoft Graph. Só roda depois que a Fase 1 terminou.

    Resiliente a falhas: cada consulta registra OK/erro sem derrubar as demais.
    Cada campo do resultado deixa CLARO de qual API veio (endpoint/titulo/etc.).
    """
    ca = CAUserClient(access_token)
    info: dict = {"userLogin": user_login}

    # Funções do CAv4 por rótulo (Fase 1).
    chamadas_cav4 = {
        "user_groups": ca.user_groups(user_login),
        "information_values": ca.information_values(user_login),
        "admin_user_details": ca.admin_user_details(user_login),
        "admin_enterprise_groups": ca.admin_enterprise_groups(user_login),
        "admin_roles": ca.admin_roles(user_login),
    }

    # ---- FASE 1: CAv4 -----------------------------------------------------
    for consulta in CAV4_CONSULTAS:
        if consulta.get("fonte") != "cav4":
            continue
        label = consulta["label"]
        endpoint = f"{consulta['method']} {consulta['path'].format(userLogin=user_login)}"
        base = {
            "endpoint": endpoint,
            "titulo": consulta["titulo"],
            "descricao": consulta["descricao"],
        }
        try:
            info[label] = {**base, "ok": True, "data": await chamadas_cav4[label]}
        except AppError as exc:
            info[label] = {**base, "ok": False, "error": exc.to_dict()["error"]}
            logger.warning("[v0] CAv4 %s (%s) falhou — %s", label, endpoint, exc.log_line())

    # ---- Ponte: pega o e-mail/UPN a partir do RESULTADO do CAv4 -----------
    detalhes_entry = info.get("admin_user_details", {})
    detalhes_data = detalhes_entry.get("data") if detalhes_entry.get("ok") else None
    user_upn = _upn_do_cav4(detalhes_data) or upn_fallback
    info["userPrincipalName"] = user_upn
    logger.info("[v0] Fase 1 (CAv4) concluida. e-mail p/ Entra=%s — iniciando Fase 2 (Graph)", user_upn)

    # ---- FASE 2: Entra/Graph (usando o e-mail vindo do CAv4) --------------
    graph = GraphClient(user_upn or "")
    chamadas_graph = {
        "graph_me": graph.user,
        "graph_manager": graph.user_manager,
    }
    for consulta in CAV4_CONSULTAS:
        if consulta.get("fonte") != "graph":
            continue
        label = consulta["label"]
        endpoint = f"{consulta['method']} {consulta['path'].format(userPrincipalName=user_upn)}"
        base = {
            "endpoint": endpoint,
            "titulo": consulta["titulo"],
            "descricao": consulta["descricao"],
        }
        # Sem e-mail vindo do CAv4 não há como consultar o Entra: registra falha clara.
        if not user_upn:
            erro = AppError(
                category=ErrorCategory.CONFIG,
                code="GRAPH_SEM_EMAIL_DO_CAV4",
                message="Não foi possível obter o e-mail do usuário no CAv4 para consultar o Entra.",
                cause="A consulta de Detalhes do Usuário (CAv4) não retornou um e-mail/UPN.",
                resolution="Confirme se o CA expõe o e-mail nos Detalhes do Usuário.",
                http_status=424,
            )
            info[label] = {**base, "ok": False, "error": erro.to_dict()["error"]}
            logger.warning("[v0] Graph %s pulado — sem e-mail vindo do CAv4", label)
            continue
        try:
            info[label] = {**base, "ok": True, "data": await chamadas_graph[label]()}
        except AppError as exc:
            info[label] = {**base, "ok": False, "error": exc.to_dict()["error"]}
            logger.warning("[v0] Graph %s (%s) falhou — %s", label, endpoint, exc.log_line())

    return info
