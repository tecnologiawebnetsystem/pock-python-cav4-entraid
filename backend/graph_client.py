"""
Cliente do Microsoft Graph (Entra ID) — ACESSO INDEPENDENTE DO CAv4.

Diferente do CAv4 (que usa o token do usuario logado), este cliente tem
CREDENCIAIS PROPRIAS (app registration dedicada no Entra) e obtem seu PROPRIO
token via fluxo client credentials (app-only). Ou seja: NAO reutiliza nada do
CAv4 nem do id_token do login — e um caminho totalmente separado para o Entra.

Fluxo:
  1) POST {authority}/{tenant}/oauth2/v2.0/token   (client_credentials)
     -> obtem um access_token de APLICACAO para o Graph.
  2) GET  {graph}/users/{upn}                         -> perfil completo
  3) GET  {graph}/users/{upn}/manager                 -> gerente/supervisor
  4) GET  {graph}/users/{upn}/photo/$value            -> foto (base64 data URI)
  5) GET  {graph}/users/{upn}/manager?$expand=manager -> cadeia de gestao
  6) GET  {graph}/users/{upn}/directReports           -> subordinados diretos
  7) GET  {graph}/users/{upn}/memberOf                -> grupos/equipes

Como e app-only (sem usuario no token), NAO existe /me: buscamos o usuario
pelo e-mail/UPN que veio nas claims do login.

Permissoes necessarias no Entra (tipo APLICACAO, com admin consent):
  - User.Read.All        (perfil, manager, directReports, foto)
  - GroupMember.Read.All  (memberOf / grupos)
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from config import get_settings
from errors import AppError, ErrorCategory, classify_network_exception

# Campos do perfil pedidos explicitamente ($select garante jobTitle/department etc.).
# Lista ESTENDIDA: alem do basico, traz endereco, datas e identificadores on-premises.
_USER_SELECT = (
    "id,displayName,givenName,surname,userPrincipalName,mail,jobTitle,"
    "department,companyName,officeLocation,mobilePhone,businessPhones,"
    "employeeId,employeeType,preferredLanguage,usageLocation,accountEnabled,"
    "streetAddress,city,state,country,postalCode,faxNumber,ageGroup,"
    "createdDateTime,employeeHireDate,onPremisesSamAccountName,"
    "onPremisesDistinguishedName,otherMails,proxyAddresses,imAddresses"
)
_MANAGER_SELECT = "id,displayName,userPrincipalName,mail,jobTitle,department"
# Campos enxutos para listas (subordinados, grupos) e cada no da cadeia de gestao.
_PERSON_SELECT = "id,displayName,userPrincipalName,mail,jobTitle,department"
_GROUP_SELECT = "id,displayName,description,mail,groupTypes,securityEnabled"


class GraphClient:
    """Cliente app-only do Microsoft Graph (token proprio, independente do CAv4)."""

    def __init__(self, user_principal_name: str) -> None:
        # Identificador do usuario a consultar (e-mail/UPN vindo das claims).
        self.upn = user_principal_name
        settings = get_settings()
        self.base_url = (settings.GRAPH_API_BASE_URL or "").rstrip("/")
        self.authority = (settings.GRAPH_AUTHORITY or "").rstrip("/")
        self.tenant_id = settings.GRAPH_TENANT_ID
        self.client_id = settings.GRAPH_CLIENT_ID
        self.client_secret = settings.GRAPH_CLIENT_SECRET
        self.scope = settings.GRAPH_SCOPE
        self._verify = settings.httpx_verify
        self._token: str | None = None

    # -- Token (client credentials) ---------------------------------------
    async def _ensure_token(self) -> str:
        """Obtem (e memoiza) o token de aplicacao para o Graph."""
        if self._token:
            return self._token

        if not (self.tenant_id and self.client_id and self.client_secret):
            raise AppError(
                category=ErrorCategory.CONFIG,
                code="GRAPH_NOT_CONFIGURED",
                message="Acesso independente ao Graph nao configurado.",
                cause="Faltam GRAPH_TENANT_ID, GRAPH_CLIENT_ID e/ou GRAPH_CLIENT_SECRET no .env.",
                resolution="Preencha as 3 variaveis GRAPH_* com os dados da app registration do Entra.",
                detail="missing_graph_credentials",
                http_status=503,
            )

        url = f"{self.authority}/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scope,
        }
        try:
            async with httpx.AsyncClient(timeout=15, verify=self._verify) as client:
                resp = await client.post(url, data=data)
        except Exception as exc:  # noqa: BLE001
            raise classify_network_exception(exc, url=url, who=ErrorCategory.ENTRA) from exc

        if resp.status_code >= 400:
            raise AppError(
                category=ErrorCategory.ENTRA,
                code="GRAPH_TOKEN_REQUEST_FAILED",
                message=f"Falha ao obter token de aplicacao no Entra (HTTP {resp.status_code}).",
                cause="O Entra recusou o client_credentials (tenant/client_id/secret/scope invalidos ou sem consentimento).",
                resolution="Confira GRAPH_TENANT_ID/CLIENT_ID/CLIENT_SECRET e o admin consent de User.Read.All.",
                detail=resp.text[:300],
                http_status=502,
            )

        self._token = resp.json().get("access_token")
        if not self._token:
            raise AppError(
                category=ErrorCategory.ENTRA,
                code="GRAPH_TOKEN_EMPTY",
                message="O Entra respondeu sem access_token.",
                cause="Resposta do token sem o campo access_token.",
                resolution="Verifique a configuracao da app registration no Entra.",
                detail=resp.text[:300],
                http_status=502,
            )
        return self._token

    def _headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async def _get(self, path: str) -> Any:
        token = await self._ensure_token()
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=15, verify=self._verify) as client:
                resp = await client.get(url, headers=self._headers(token))
        except Exception as exc:  # noqa: BLE001
            raise classify_network_exception(exc, url=url, who=ErrorCategory.ENTRA) from exc
        return self._handle(resp)

    async def _get_photo_data_uri(self, path: str) -> Any:
        """
        Busca a foto (binario) e devolve um data URI base64 pronto para exibir
        em <img src="...">. Retorna None se o usuario nao tiver foto (404).
        """
        token = await self._ensure_token()
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=15, verify=self._verify) as client:
                resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        except Exception as exc:  # noqa: BLE001
            raise classify_network_exception(exc, url=url, who=ErrorCategory.ENTRA) from exc
        # Sem foto cadastrada e cenario normal: nao tratamos como erro.
        if resp.status_code == 404:
            return None
        # Demais erros: reaproveita o tratamento padrao (lanca AppError).
        if resp.status_code >= 400:
            return self._handle(resp)
        if not resp.content:
            return None
        content_type = resp.headers.get("Content-Type", "image/jpeg")
        b64 = base64.b64encode(resp.content).decode("ascii")
        return {
            "contentType": content_type,
            "sizeBytes": len(resp.content),
            "dataUri": f"data:{content_type};base64,{b64}",
        }

    @staticmethod
    def _handle(resp: httpx.Response) -> Any:
        if resp.status_code == 401:
            raise AppError(
                category=ErrorCategory.ENTRA,
                code="GRAPH_TOKEN_INVALID",
                message="O Microsoft Graph recusou o token (HTTP 401).",
                cause="O token de aplicacao e invalido/expirado para o Graph.",
                resolution="Verifique as credenciais GRAPH_* e o admin consent das permissoes.",
                detail=resp.text[:300],
                http_status=401,
            )
        if resp.status_code == 403:
            raise AppError(
                category=ErrorCategory.ENTRA,
                code="GRAPH_ACCESS_DENIED",
                message="O Microsoft Graph negou o acesso (HTTP 403).",
                cause="A app nao tem permissao de aplicacao para este recurso.",
                resolution="Conceda User.Read.All (tipo Aplicacao) com admin consent no Entra.",
                detail=resp.text[:300],
                http_status=403,
            )
        if resp.status_code == 404:
            raise AppError(
                category=ErrorCategory.ENTRA,
                code="GRAPH_NOT_FOUND",
                message="Recurso nao encontrado no Graph (HTTP 404).",
                cause="Usuario nao encontrado pelo UPN, ou usuario sem gerente definido.",
                resolution="Confirme o e-mail/UPN do usuario; ausencia de gerente e normal.",
                detail=resp.text[:300],
                http_status=404,
            )
        if resp.status_code >= 500:
            raise AppError(
                category=ErrorCategory.ENTRA,
                code="GRAPH_SERVER_ERROR",
                message=f"O Microsoft Graph respondeu com erro interno (HTTP {resp.status_code}).",
                cause="Falha no lado do servidor do Graph.",
                resolution="Tente novamente mais tarde.",
                detail=resp.text[:300],
                http_status=502,
            )
        if resp.status_code >= 400:
            raise AppError(
                category=ErrorCategory.ENTRA,
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

    @staticmethod
    def _enc(value: str) -> str:
        from urllib.parse import quote
        return quote(value, safe="@.")

    # -- Consultas (app-only: busca o usuario pelo UPN) --------------------
    async def user(self) -> Any:
        """Perfil completo do usuario no Entra ID (GET /users/{upn})."""
        return await self._get(f"/users/{self._enc(self.upn)}?$select={_USER_SELECT}")

    async def user_manager(self) -> Any:
        """Gerente/supervisor do usuario (GET /users/{upn}/manager)."""
        return await self._get(f"/users/{self._enc(self.upn)}/manager?$select={_MANAGER_SELECT}")

    async def user_photo(self) -> Any:
        """Foto do usuario como data URI base64 (GET /users/{upn}/photo/$value)."""
        return await self._get_photo_data_uri(f"/users/{self._enc(self.upn)}/photo/$value")

    async def user_management_chain(self) -> Any:
        """
        Cadeia de gestao: o gerente e, recursivamente, o gerente do gerente
        (GET /users/{upn}/manager?$expand=manager). O Graph aninha em 'manager'.
        """
        return await self._get(
            f"/users/{self._enc(self.upn)}/manager?$expand=manager($select={_PERSON_SELECT})"
            f"&$select={_PERSON_SELECT}"
        )

    async def user_direct_reports(self) -> Any:
        """Subordinados diretos (GET /users/{upn}/directReports)."""
        return await self._get(
            f"/users/{self._enc(self.upn)}/directReports?$select={_PERSON_SELECT}"
        )

    async def user_member_of(self) -> Any:
        """Grupos/equipes aos quais o usuario pertence (GET /users/{upn}/memberOf)."""
        return await self._get(
            f"/users/{self._enc(self.upn)}/memberOf?$select={_GROUP_SELECT}"
        )
