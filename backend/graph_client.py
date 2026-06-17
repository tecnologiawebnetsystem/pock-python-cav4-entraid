"""
Cliente do Microsoft Graph (Entra ID).

Busca o PERFIL COMPLETO do usuário no Entra ID — dados que normalmente NÃO
vêm dentro do id_token, como cargo, departamento, telefone e o gerente/supervisor.

Requisitos:
  - O access_token (Bearer) precisa ter sido emitido para a audiência do
    Microsoft Graph e conter o scope "User.Read".
  - Se o token foi emitido apenas para o CA (fwca-authz), o Graph responde 401.
    Nesse caso, a consulta é resiliente: o erro é registrado por campo e o
    restante do login continua funcionando normalmente.

Endpoints usados nesta POC:
  GET /me           -> perfil do usuário autenticado (todos os campos padrão)
  GET /me/manager   -> gerente/supervisor do usuário
"""

from __future__ import annotations

from typing import Any

import httpx

from config import get_settings
from errors import AppError, ErrorCategory, classify_network_exception

# Campos do perfil que pedimos explicitamente ao Graph. $select garante que
# campos como jobTitle/department/officeLocation venham mesmo que nao sejam
# retornados por padrao.
_ME_SELECT = (
    "id,displayName,givenName,surname,userPrincipalName,mail,jobTitle,"
    "department,companyName,officeLocation,mobilePhone,businessPhones,"
    "employeeId,employeeType,preferredLanguage,usageLocation,accountEnabled"
)
_MANAGER_SELECT = "id,displayName,userPrincipalName,mail,jobTitle,department"


class GraphClient:
    """Wrapper das chamadas ao Microsoft Graph para o usuário autenticado."""

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token
        settings = get_settings()
        self.base_url = (settings.GRAPH_API_BASE_URL or "").rstrip("/")
        self._verify = settings.httpx_verify

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    async def _get(self, path: str) -> Any:
        url = self._url(path)
        try:
            async with httpx.AsyncClient(timeout=15, verify=self._verify) as client:
                resp = await client.get(url, headers=self._headers())
        except Exception as exc:  # noqa: BLE001
            raise classify_network_exception(exc, url=url, who=ErrorCategory.CA) from exc
        return self._handle(resp)

    @staticmethod
    def _handle(resp: httpx.Response) -> Any:
        if resp.status_code == 401:
            raise AppError(
                category=ErrorCategory.CA,
                code="GRAPH_TOKEN_INVALID",
                message="O Microsoft Graph recusou o token (HTTP 401).",
                cause="O access_token nao foi emitido para o Graph ou nao tem o scope User.Read.",
                resolution="Confirme se a app pode emitir token para o Graph e se 'User.Read' esta nos scopes.",
                detail=resp.text[:300],
                http_status=401,
            )
        if resp.status_code == 403:
            raise AppError(
                category=ErrorCategory.CA,
                code="GRAPH_ACCESS_DENIED",
                message="O Microsoft Graph negou o acesso (HTTP 403).",
                cause="A app/usuario nao tem permissao para este recurso do Graph.",
                resolution="Verifique as permissoes (User.Read) concedidas a aplicacao no Entra.",
                detail=resp.text[:300],
                http_status=403,
            )
        if resp.status_code == 404:
            raise AppError(
                category=ErrorCategory.CA,
                code="GRAPH_NOT_FOUND",
                message="Recurso nao encontrado no Graph (HTTP 404).",
                cause="O recurso consultado nao existe (ex.: usuario sem gerente definido).",
                resolution="Normal quando o usuario nao possui gerente cadastrado no Entra.",
                detail=resp.text[:300],
                http_status=404,
            )
        if resp.status_code >= 500:
            raise AppError(
                category=ErrorCategory.CA,
                code="GRAPH_SERVER_ERROR",
                message=f"O Microsoft Graph respondeu com erro interno (HTTP {resp.status_code}).",
                cause="Falha no lado do servidor do Graph.",
                resolution="Tente novamente mais tarde.",
                detail=resp.text[:300],
                http_status=502,
            )
        if resp.status_code >= 400:
            raise AppError(
                category=ErrorCategory.CA,
                code="GRAPH_REQUEST_ERROR",
                message=f"O Microsoft Graph recusou a requisicao (HTTP {resp.status_code}).",
                cause="Requisicao invalida para o Graph.",
                resolution="Verifique os parametros enviados ao Graph.",
                detail=resp.text[:300],
                http_status=resp.status_code,
            )
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    async def me(self) -> Any:
        """Perfil completo do usuario autenticado no Entra ID."""
        return await self._get(f"/me?$select={_ME_SELECT}")

    async def me_manager(self) -> Any:
        """Gerente/supervisor do usuario autenticado."""
        return await self._get(f"/me/manager?$select={_MANAGER_SELECT}")
