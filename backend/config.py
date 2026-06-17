"""
Configuração centralizada do BFF (Backend For Frontend).

Todos os valores sensíveis e específicos de ambiente vêm de variáveis de
ambiente. Os valores que ainda dependem da documentação interna do CA
(URLs do fwca-authz e host da User API) estão marcados como REQUIRED e
devem ser preenchidos via env vars antes de o login funcionar.

NUNCA coloque o client_secret diretamente aqui — ele vem de CA_CLIENT_SECRET.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Carrega backend/.env (se existir) para o ambiente do processo.
# override=False: variáveis já definidas no sistema têm prioridade (Vercel/PROD).
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)


def _get(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is not None:
        value = value.strip()
    return value or default


class Settings:
    """Configurações do BFF carregadas do ambiente."""

    # -- Identidade da aplicação no CA (do registro da aplicação) ----------
    # clientId público da aplicação (ex.: f1f4d0d4-...)
    CA_CLIENT_ID: str | None = _get("CA_CLIENT_ID")
    # clientSecret — DEVE vir do ambiente / Secrets Manager. Nunca hardcode.
    CA_CLIENT_SECRET: str | None = _get("CA_CLIENT_SECRET")
    # URI de callback registrada no CA (ex.: https://app.../auth/entra-callback)
    CA_REDIRECT_URI: str | None = _get("CA_REDIRECT_URI")
    # Scopes do OIDC. A app registrou "openid" e "profile".
    CA_SCOPES: str = _get("CA_SCOPES", "openid profile") or "openid profile"

    # -- Microsoft Graph (acesso INDEPENDENTE do CAv4) ---------------------
    # Estas credenciais sao de uma app registration PROPRIA no Entra ID, com
    # permissao de APLICACAO (app-only / client credentials). NAO reutilizam o
    # token do CAv4 — o backend pega seu proprio token direto no Entra e consulta
    # o Microsoft Graph. Permissao recomendada: User.Read.All (Application).
    GRAPH_TENANT_ID: str | None = _get("GRAPH_TENANT_ID")
    GRAPH_CLIENT_ID: str | None = _get("GRAPH_CLIENT_ID")
    GRAPH_CLIENT_SECRET: str | None = _get("GRAPH_CLIENT_SECRET")
    # Base do Microsoft Graph (perfil completo do Entra ID: cargo, depto, gerente...).
    GRAPH_API_BASE_URL: str = _get("GRAPH_API_BASE_URL", "https://graph.microsoft.com/v1.0") or "https://graph.microsoft.com/v1.0"
    # Authority do Entra para obter o token (client credentials).
    GRAPH_AUTHORITY: str = _get("GRAPH_AUTHORITY", "https://login.microsoftonline.com") or "https://login.microsoftonline.com"
    # Scope do client credentials (sempre o .default da app no Graph).
    GRAPH_SCOPE: str = _get("GRAPH_SCOPE", "https://graph.microsoft.com/.default") or "https://graph.microsoft.com/.default"

    @property
    def is_graph_configured(self) -> bool:
        """True se ha credenciais proprias para o acesso independente ao Graph."""
        return bool(self.GRAPH_TENANT_ID and self.GRAPH_CLIENT_ID and self.GRAPH_CLIENT_SECRET)

    # -- Endpoints OIDC do fwca-authz --------------------------------------
    # Caminho preferido: informar só o documento de discovery e deixar o BFF
    # descobrir os endpoints automaticamente.
    OIDC_DISCOVERY_URL: str | None = _get("OIDC_DISCOVERY_URL")
    # Alternativa: informar os endpoints individualmente (se não houver discovery).
    OIDC_ISSUER: str | None = _get("OIDC_ISSUER")
    OIDC_AUTHORIZATION_ENDPOINT: str | None = _get("OIDC_AUTHORIZATION_ENDPOINT")
    OIDC_TOKEN_ENDPOINT: str | None = _get("OIDC_TOKEN_ENDPOINT")
    OIDC_JWKS_URI: str | None = _get("OIDC_JWKS_URI")

    # -- User API do CA (autorização: roles, resources, groups...) ---------
    # Host base da API do CA (ex.: https://ca-dsv.petrobras.com.br)
    CA_API_BASE_URL: str | None = _get("CA_API_BASE_URL")

    # -- Validação do id_token ---------------------------------------------
    # Validar a assinatura do id_token via JWKS. Em DSV pode desligar (não recomendado).
    OIDC_VERIFY_SIGNATURE: bool = (_get("OIDC_VERIFY_SIGNATURE", "true") or "true").lower() == "true"

    # -- TLS / certificados (rede corporativa) -----------------------------
    # Usar o repositório de certificados do SISTEMA OPERACIONAL (Windows/macOS)
    # em vez do bundle do certifi. É a forma recomendada na rede Petrobras:
    # o Python passa a confiar nas mesmas CAs internas que o navegador e o
    # PowerShell já confiam, sem precisar exportar .pem manualmente.
    # Ligado por padrão. Desligue (false) só se quiser forçar o certifi.
    CA_SSL_USE_TRUSTSTORE: bool = (_get("CA_SSL_USE_TRUSTSTORE", "true") or "true").lower() == "true"
    # Caminho para um bundle de CA customizado (.pem/.crt) contendo a CA raiz
    # interna da Petrobras. Use isto quando o host (caauthz/fwca) usa um
    # certificado emitido por uma CA interna que não está no bundle do certifi.
    # Ex.: CA_SSL_CERT_FILE=C:\certs\petrobras-ca.pem
    CA_SSL_CERT_FILE: str | None = _get("CA_SSL_CERT_FILE")
    # Verificar o certificado TLS nas chamadas ao CA. Em DSV, se você não tiver
    # o bundle da CA interna à mão, pode definir "false" para destravar o login
    # (INSEGURO — não usar em HOM/PROD).
    CA_SSL_VERIFY: bool = (_get("CA_SSL_VERIFY", "true") or "true").lower() == "true"

    @property
    def httpx_verify(self) -> Any:
        """Valor para o parâmetro `verify` do httpx.

        - caminho do bundle, se CA_SSL_CERT_FILE estiver definido;
        - False, se CA_SSL_VERIFY=false (DSV/inseguro);
        - True (padrão seguro), caso contrário.
        """
        if self.CA_SSL_CERT_FILE:
            return self.CA_SSL_CERT_FILE
        return self.CA_SSL_VERIFY

    @property
    def is_oidc_configured(self) -> bool:
        """True se há informação suficiente para iniciar o fluxo OIDC."""
        has_endpoints = bool(self.OIDC_AUTHORIZATION_ENDPOINT and self.OIDC_TOKEN_ENDPOINT)
        return bool(self.CA_CLIENT_ID and self.CA_REDIRECT_URI and (self.OIDC_DISCOVERY_URL or has_endpoints))

    def missing_config(self) -> list[str]:
        """Lista das configurações ainda ausentes, para diagnóstico."""
        missing: list[str] = []
        if not self.CA_CLIENT_ID:
            missing.append("CA_CLIENT_ID")
        if not self.CA_CLIENT_SECRET:
            missing.append("CA_CLIENT_SECRET")
        if not self.CA_REDIRECT_URI:
            missing.append("CA_REDIRECT_URI")
        if not (self.OIDC_DISCOVERY_URL or (self.OIDC_AUTHORIZATION_ENDPOINT and self.OIDC_TOKEN_ENDPOINT)):
            missing.append("OIDC_DISCOVERY_URL (ou OIDC_AUTHORIZATION_ENDPOINT + OIDC_TOKEN_ENDPOINT)")
        if not self.CA_API_BASE_URL:
            missing.append("CA_API_BASE_URL")
        return missing


@lru_cache
def get_settings() -> Settings:
    return Settings()
