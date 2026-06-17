"""
Cliente OIDC do fwca-authz (Authorization Code Flow + PKCE S256).

Responsável por:
- descobrir os endpoints via .well-known/openid-configuration (se configurado);
- montar a URL de autorização (com state, nonce e PKCE);
- trocar o authorization code por tokens;
- validar o id_token (assinatura via JWKS, issuer, audience, nonce).
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import ssl
import time
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from config import Settings, get_settings
from errors import AppError, ErrorCategory, classify_network_exception, is_tls_cert_error

logger = logging.getLogger("ca.oidc")


class OIDCClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._metadata: dict[str, Any] | None = None
        self._metadata_fetched_at: float = 0.0
        self._jwks_client: PyJWKClient | None = None

    # -- Descoberta de endpoints ------------------------------------------
    async def metadata(self) -> dict[str, Any]:
        """Retorna os endpoints OIDC, via discovery ou via env vars."""
        s = self.settings
        # cache simples por 1h
        if self._metadata and (time.time() - self._metadata_fetched_at) < 3600:
            return self._metadata

        if s.OIDC_DISCOVERY_URL:
            logger.info("[v0] OIDC discovery: buscando %s", s.OIDC_DISCOVERY_URL)
            try:
                async with httpx.AsyncClient(timeout=15, verify=s.httpx_verify) as client:
                    resp = await client.get(s.OIDC_DISCOVERY_URL)
                    resp.raise_for_status()
                    self._metadata = resp.json()
            except httpx.HTTPStatusError as exc:
                err = AppError(
                    category=ErrorCategory.CA,
                    code="OIDC_DISCOVERY_HTTP_ERROR",
                    message=(
                        f"O provedor OIDC respondeu HTTP {exc.response.status_code} "
                        f"no discovery ({s.OIDC_DISCOVERY_URL})."
                    ),
                    cause="A URL de discovery pode estar errada ou o serviço do CA com problema.",
                    resolution="Confirme a OIDC_DISCOVERY_URL com o time do CA.",
                    detail=f"HTTP {exc.response.status_code}: {exc.response.text[:300]}",
                    http_status=502,
                )
                logger.error("[v0] %s", err.log_line())
                raise err from exc
            except Exception as exc:  # noqa: BLE001
                err = classify_network_exception(
                    exc, url=s.OIDC_DISCOVERY_URL, who=ErrorCategory.CA
                )
                # discovery é o passo onde o erro de TLS aparece primeiro
                logger.error("[v0] OIDC discovery FALHOU — %s", err.log_line())
                raise err from exc
            logger.info("[v0] OIDC discovery OK: %d endpoints", len(self._metadata or {}))
        else:
            # monta a partir das env vars individuais
            self._metadata = {
                "issuer": s.OIDC_ISSUER,
                "authorization_endpoint": s.OIDC_AUTHORIZATION_ENDPOINT,
                "token_endpoint": s.OIDC_TOKEN_ENDPOINT,
                "jwks_uri": s.OIDC_JWKS_URI,
            }
        self._metadata_fetched_at = time.time()
        return self._metadata

    # -- PKCE --------------------------------------------------------------
    @staticmethod
    def generate_pkce() -> tuple[str, str]:
        """Retorna (code_verifier, code_challenge) usando S256."""
        verifier = secrets.token_urlsafe(64)[:128]
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return verifier, challenge

    # -- URL de autorização ------------------------------------------------
    async def build_authorization_url(
        self, *, state: str, nonce: str, code_challenge: str
    ) -> str:
        meta = await self.metadata()
        endpoint = meta.get("authorization_endpoint")
        if not endpoint:
            raise AppError(
                category=ErrorCategory.CONFIG,
                code="MISSING_AUTHORIZATION_ENDPOINT",
                message="authorization_endpoint não encontrado.",
                cause="Sem OIDC_DISCOVERY_URL válido e sem OIDC_AUTHORIZATION_ENDPOINT no .env.",
                resolution="Defina OIDC_DISCOVERY_URL ou OIDC_AUTHORIZATION_ENDPOINT no backend/.env.",
                http_status=503,
            )
        s = self.settings
        params = {
            "response_type": "code",
            "client_id": s.CA_CLIENT_ID or "",
            "redirect_uri": s.CA_REDIRECT_URI or "",
            "scope": s.CA_SCOPES,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        query = httpx.QueryParams(params)
        return f"{endpoint}?{query}"

    # -- Troca code -> tokens ---------------------------------------------
    async def exchange_code(self, *, code: str, code_verifier: str) -> dict[str, Any]:
        meta = await self.metadata()
        endpoint = meta.get("token_endpoint")
        if not endpoint:
            raise AppError(
                category=ErrorCategory.CONFIG,
                code="MISSING_TOKEN_ENDPOINT",
                message="token_endpoint não encontrado.",
                cause="Sem OIDC_DISCOVERY_URL válido e sem OIDC_TOKEN_ENDPOINT no .env.",
                resolution="Defina OIDC_DISCOVERY_URL ou OIDC_TOKEN_ENDPOINT no backend/.env.",
                http_status=503,
            )
        s = self.settings
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": s.CA_REDIRECT_URI or "",
            "client_id": s.CA_CLIENT_ID or "",
            "code_verifier": code_verifier,
        }
        # client_secret enviado no corpo (a app é confidential)
        if s.CA_CLIENT_SECRET:
            data["client_secret"] = s.CA_CLIENT_SECRET

        try:
            async with httpx.AsyncClient(timeout=15, verify=s.httpx_verify) as client:
                resp = await client.post(
                    endpoint,
                    data=data,
                    headers={"Accept": "application/json"},
                )
        except Exception as exc:  # noqa: BLE001
            err = classify_network_exception(exc, url=endpoint, who=ErrorCategory.ENTRA)
            logger.error("[v0] exchange_code FALHOU — %s", err.log_line())
            raise err from exc

        if resp.status_code != 200:
            raise AppError(
                category=ErrorCategory.ENTRA,
                code="TOKEN_EXCHANGE_REJECTED",
                message=f"O provedor recusou a troca do code por tokens (HTTP {resp.status_code}).",
                cause=(
                    "Possíveis causas: code expirado/já usado, redirect_uri diferente do "
                    "registrado, client_id/secret incorretos, ou PKCE inválido."
                ),
                resolution=(
                    "Refaça o login (code é de uso único e expira rápido) e confirme "
                    "CA_REDIRECT_URI/CA_CLIENT_ID/CA_CLIENT_SECRET no .env."
                ),
                detail=f"HTTP {resp.status_code}: {resp.text[:300]}",
                http_status=401,
            )
        return resp.json()

    # -- Validação do id_token --------------------------------------------
    async def validate_id_token(self, id_token: str, *, nonce: str | None = None) -> dict[str, Any]:
        meta = await self.metadata()
        s = self.settings

        if not id_token:
            raise AppError(
                category=ErrorCategory.ENTRA,
                code="MISSING_ID_TOKEN",
                message="O provedor não retornou id_token na troca de tokens.",
                cause="A resposta do token endpoint veio sem id_token (escopo 'openid' ausente?).",
                resolution="Confirme que CA_SCOPES inclui 'openid' e que a app pede id_token.",
                http_status=502,
            )

        if not s.OIDC_VERIFY_SIGNATURE:
            # DSV / debug: decodifica sem verificar assinatura (NÃO usar em prod)
            claims = jwt.decode(id_token, options={"verify_signature": False})
        else:
            jwks_uri = meta.get("jwks_uri")
            if not jwks_uri:
                raise AppError(
                    category=ErrorCategory.CONFIG,
                    code="MISSING_JWKS_URI",
                    message="jwks_uri não encontrado — não é possível validar a assinatura.",
                    cause="Sem discovery e sem OIDC_JWKS_URI no .env.",
                    resolution=(
                        "Defina OIDC_DISCOVERY_URL/OIDC_JWKS_URI, ou (só DSV) "
                        "OIDC_VERIFY_SIGNATURE=false para pular a verificação."
                    ),
                    http_status=503,
                )
            try:
                if self._jwks_client is None:
                    ssl_ctx = None
                    if s.CA_SSL_CERT_FILE:
                        ssl_ctx = ssl.create_default_context(cafile=s.CA_SSL_CERT_FILE)
                    elif s.CA_SSL_VERIFY is False:
                        ssl_ctx = ssl.create_default_context()
                        ssl_ctx.check_hostname = False
                        ssl_ctx.verify_mode = ssl.CERT_NONE
                    self._jwks_client = PyJWKClient(jwks_uri, ssl_context=ssl_ctx)
                signing_key = self._jwks_client.get_signing_key_from_jwt(id_token)
            except Exception as exc:  # noqa: BLE001
                if is_tls_cert_error(exc):
                    err = classify_network_exception(exc, url=jwks_uri, who=ErrorCategory.ENTRA)
                else:
                    err = AppError(
                        category=ErrorCategory.ENTRA,
                        code="JWKS_FETCH_FAILED",
                        message=f"Não foi possível obter as chaves de assinatura (JWKS) em {jwks_uri}.",
                        cause="Falha ao baixar o JWKS ou a chave do token não foi encontrada.",
                        resolution="Confirme o jwks_uri e a conectividade. Em DSV pode usar OIDC_VERIFY_SIGNATURE=false.",
                        detail=f"{type(exc).__name__}: {exc}",
                        http_status=502,
                    )
                logger.error("[v0] validate_id_token/JWKS FALHOU — %s", err.log_line())
                raise err from exc

            try:
                claims = jwt.decode(
                    id_token,
                    signing_key.key,
                    algorithms=["RS256", "ES256"],
                    audience=s.CA_CLIENT_ID,
                    issuer=meta.get("issuer"),
                    options={"verify_aud": bool(s.CA_CLIENT_ID), "verify_iss": bool(meta.get("issuer"))},
                )
            except jwt.ExpiredSignatureError as exc:
                raise AppError(
                    category=ErrorCategory.ENTRA,
                    code="ID_TOKEN_EXPIRED",
                    message="O id_token retornado pelo Entra já está expirado.",
                    cause="Relógio do servidor fora de sincronia ou token muito antigo.",
                    resolution="Refaça o login e verifique o relógio (NTP) da máquina.",
                    detail=str(exc),
                    http_status=401,
                ) from exc
            except jwt.InvalidAudienceError as exc:
                raise AppError(
                    category=ErrorCategory.ENTRA,
                    code="ID_TOKEN_INVALID_AUDIENCE",
                    message="O 'audience' do id_token não bate com o CA_CLIENT_ID.",
                    cause="O token foi emitido para outro client_id.",
                    resolution="Confirme que CA_CLIENT_ID é o mesmo registrado no CA/Entra.",
                    detail=str(exc),
                    http_status=401,
                ) from exc
            except jwt.InvalidIssuerError as exc:
                raise AppError(
                    category=ErrorCategory.ENTRA,
                    code="ID_TOKEN_INVALID_ISSUER",
                    message="O 'issuer' do id_token não confere com o esperado.",
                    cause="O issuer do discovery difere do issuer do token.",
                    resolution="Confirme OIDC_ISSUER/OIDC_DISCOVERY_URL com o time do CA.",
                    detail=str(exc),
                    http_status=401,
                ) from exc
            except jwt.PyJWTError as exc:
                raise AppError(
                    category=ErrorCategory.ENTRA,
                    code="ID_TOKEN_INVALID",
                    message="Falha ao validar a assinatura/claims do id_token.",
                    cause="Token malformado, assinatura inválida ou algoritmo não suportado.",
                    resolution="Refaça o login. Em DSV pode usar OIDC_VERIFY_SIGNATURE=false para diagnosticar.",
                    detail=f"{type(exc).__name__}: {exc}",
                    http_status=401,
                ) from exc

        if nonce is not None and claims.get("nonce") != nonce:
            raise AppError(
                category=ErrorCategory.ENTRA,
                code="ID_TOKEN_NONCE_MISMATCH",
                message="O 'nonce' do id_token não confere com o enviado no login.",
                cause="Possível replay/CSRF ou login iniciado em outra sessão/servidor.",
                resolution="Refaça o login a partir do mesmo backend e tente novamente.",
                http_status=401,
            )
        return claims


def get_oidc_client() -> OIDCClient:
    return OIDCClient()
