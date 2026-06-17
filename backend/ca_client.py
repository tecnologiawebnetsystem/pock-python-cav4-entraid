"""
Cliente da User API do Controle de Acesso (CAv4).

Todas as chamadas exigem o access_token (Bearer) obtido no fluxo OIDC, que
fica no servidor e NUNCA é exposto ao frontend.

Endpoints usados nesta POC:
  User API:
    GET  /api/users/{userLogin}/user-groups
    GET  /api/users/{userLogin}/information-values
  Admin API (GET, sem corpo):
    GET  /api/admin/users/{userLogin}                    (detalhes do usuário/supervisor)
    GET  /api/admin/users/{userLogin}/enterprise-groups  (enterprise groups)
    GET  /api/admin/users/{userLogin}/roles              (papéis do usuário)
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from config import get_settings
from errors import AppError, ErrorCategory, classify_network_exception


class CAUserClient:
    """Wrapper das chamadas à User API do CA para um usuário autenticado."""

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token
        settings = get_settings()
        self.base_url = (settings.CA_API_BASE_URL or "").rstrip("/")
        self._verify = settings.httpx_verify

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        if not self.base_url:
            raise AppError(
                category=ErrorCategory.CONFIG,
                code="MISSING_CA_API_BASE_URL",
                message="CA_API_BASE_URL não configurado.",
                cause="A variável CA_API_BASE_URL não está definida no backend/.env.",
                resolution="Defina CA_API_BASE_URL (ex.: https://ca-dsv.petrobras.com.br) no .env.",
                http_status=503,
            )
        return f"{self.base_url}{path}"

    @staticmethod
    def _enc(value: str) -> str:
        return quote(value, safe="")

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
                code="CA_TOKEN_INVALID",
                message="O CA recusou o token (HTTP 401).",
                cause="O access_token está inválido/expirado ou não tem permissão para a User API.",
                resolution="Refaça o login. Se persistir, confirme os scopes da app no CA.",
                http_status=401,
            )
        if resp.status_code == 403:
            raise AppError(
                category=ErrorCategory.CA,
                code="CA_ACCESS_DENIED",
                message="O CA negou o acesso (HTTP 403).",
                cause="O usuário/aplicação não tem autorização para este recurso no CA.",
                resolution="Verifique as permissões do usuário e da aplicação no CA.",
                http_status=403,
            )
        if resp.status_code == 404:
            raise AppError(
                category=ErrorCategory.CA,
                code="CA_NOT_FOUND",
                message="Recurso não encontrado no CA (HTTP 404).",
                cause="O userLogin ou o recurso consultado não existe no CA.",
                resolution="Confirme o userLogin extraído do token e o endpoint chamado.",
                detail=resp.text[:300],
                http_status=404,
            )
        if resp.status_code >= 500:
            raise AppError(
                category=ErrorCategory.CA,
                code="CA_SERVER_ERROR",
                message=f"O CA respondeu com erro interno (HTTP {resp.status_code}).",
                cause="Falha no lado do servidor do CA.",
                resolution="Tente novamente mais tarde. Se persistir, acione o time do CA.",
                detail=resp.text[:300],
                http_status=502,
            )
        if resp.status_code >= 400:
            raise AppError(
                category=ErrorCategory.CA,
                code="CA_REQUEST_ERROR",
                message=f"O CA recusou a requisição (HTTP {resp.status_code}).",
                cause="Requisição inválida para a User API do CA.",
                resolution="Verifique os parâmetros enviados ao CA.",
                detail=resp.text[:300],
                http_status=resp.status_code,
            )
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    # -- Grupos ------------------------------------------------------------
    async def user_groups(self, user_login: str) -> Any:
        return await self._get(f"/api/users/{self._enc(user_login)}/user-groups")

    # -- Information Values ------------------------------------------------
    async def information_values(self, user_login: str) -> Any:
        return await self._get(f"/api/users/{self._enc(user_login)}/information-values")

    # -- Admin API (GET, sem corpo) ---------------------------------------
    async def admin_user_details(self, user_login: str) -> Any:
        # GET: "Detalhes de Usuário" — costuma trazer dados cadastrais
        # (lotação, gerente/supervisor, empresa, etc.).
        return await self._get(f"/api/admin/users/{self._enc(user_login)}")

    async def admin_enterprise_groups(self, user_login: str) -> Any:
        # GET: "Listar Enterprise Groups de Usuário" (Admin).
        return await self._get(f"/api/admin/users/{self._enc(user_login)}/enterprise-groups")

    async def admin_roles(self, user_login: str) -> Any:
        # GET: "Listar Papéis de Usuário" (GET, sem corpo).
        return await self._get(f"/api/admin/users/{self._enc(user_login)}/roles")
