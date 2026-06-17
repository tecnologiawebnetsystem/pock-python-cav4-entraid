"""
Sistema central de erros categorizados do backend.

Objetivo: NUNCA retornar mensagens genéricas. Todo erro carrega:
  - categoria  -> de ONDE vem o erro (config, rede, TLS, CA, Entra, código...);
  - code       -> identificador curto e estável (ex.: "TLS_CERT_VERIFY_FAILED");
  - message    -> o que aconteceu, em linguagem clara;
  - cause      -> causa provável;
  - resolution -> como resolver (passo a passo);
  - detail     -> detalhe técnico original (str da exceção);
  - http_status-> status HTTP sugerido para a resposta.

Assim, ao ler a resposta/erro fica imediato saber se o problema é do CÓDIGO,
do SERVIDOR, da INFRA/REDE, do CA ou do Entra ID.
"""

from __future__ import annotations

import ssl
from enum import Enum
from typing import Any

import httpx


class ErrorCategory(str, Enum):
    """De ONDE o erro se origina."""

    CONFIG = "CONFIG"            # configuração ausente/errada no .env
    CODIGO = "CODIGO"            # bug na aplicação (programação)
    SERVIDOR = "SERVIDOR"        # erro interno do nosso backend em runtime
    INFRA_REDE = "INFRA_REDE"    # rede/VPN/DNS — host não alcançável
    INFRA_TLS = "INFRA_TLS"      # certificado/TLS (CA interna Petrobras)
    CA = "CA"                    # o provedor CA/fwca-authz respondeu com erro
    ENTRA = "ENTRA"             # o Entra ID (provedor de identidade) recusou


# Texto amigável por categoria, para deixar claro de quem é a "culpa".
CATEGORY_LABEL: dict[ErrorCategory, str] = {
    ErrorCategory.CONFIG: "Erro de CONFIGURAÇÃO (variáveis de ambiente do backend)",
    ErrorCategory.CODIGO: "Erro de CÓDIGO (bug na aplicação)",
    ErrorCategory.SERVIDOR: "Erro do SERVIDOR (falha interna do backend)",
    ErrorCategory.INFRA_REDE: "Erro de INFRAESTRUTURA/REDE (host inacessível — VPN/RIC/DNS)",
    ErrorCategory.INFRA_TLS: "Erro de INFRAESTRUTURA/TLS (certificado da CA interna Petrobras)",
    ErrorCategory.CA: "Erro do CA (provedor de Controle de Acesso / fwca-authz)",
    ErrorCategory.ENTRA: "Erro do ENTRA ID (provedor de identidade Microsoft)",
}


class AppError(Exception):
    """Erro estruturado e categorizado da aplicação."""

    def __init__(
        self,
        *,
        category: ErrorCategory,
        code: str,
        message: str,
        cause: str | None = None,
        resolution: str | None = None,
        detail: str | None = None,
        http_status: int = 500,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.code = code
        self.message = message
        self.cause = cause
        self.resolution = resolution
        self.detail = detail
        self.http_status = http_status

    def to_dict(self) -> dict[str, Any]:
        """Serializa o erro de forma completa para a resposta JSON."""
        return {
            "error": {
                "category": self.category.value,
                "category_label": CATEGORY_LABEL[self.category],
                "code": self.code,
                "message": self.message,
                "cause": self.cause,
                "resolution": self.resolution,
                "detail": self.detail,
            }
        }

    def log_line(self) -> str:
        """Linha compacta para o log do servidor."""
        return f"[{self.category.value}] {self.code}: {self.message}" + (
            f" | detalhe: {self.detail}" if self.detail else ""
        )


# ---------------------------------------------------------------------------
# Classificadores de exceções de rede/TLS (httpx / ssl)
# ---------------------------------------------------------------------------

def is_tls_cert_error(exc: BaseException) -> bool:
    """True se a exceção for falha de verificação de certificado TLS."""
    if isinstance(exc, ssl.SSLError):
        return True
    text = str(exc)
    return "CERTIFICATE_VERIFY_FAILED" in text or (
        "SSL" in text and "certificate" in text.lower()
    )


def classify_network_exception(
    exc: Exception,
    *,
    url: str,
    who: ErrorCategory,
) -> AppError:
    """
    Converte uma exceção de httpx/ssl em um AppError categorizado.

    `who` indica de quem é o endpoint sendo chamado (CA ou ENTRA), usado só
    para enriquecer a mensagem quando NÃO for um problema claro de rede/TLS.
    """
    detail = f"{type(exc).__name__}: {exc}"

    # 1) Problema de certificado TLS (CA interna Petrobras)
    if is_tls_cert_error(exc):
        return AppError(
            category=ErrorCategory.INFRA_TLS,
            code="TLS_CERT_VERIFY_FAILED",
            message=f"Falha ao validar o certificado TLS de {url}.",
            cause=(
                "O host usa um certificado emitido por uma CA INTERNA da Petrobras "
                "que o Python (certifi) não reconhece. O navegador/PowerShell confia "
                "porque usam o repositório de certificados do Windows."
            ),
            resolution=(
                "Por padrão o backend usa truststore (CA_SSL_USE_TRUSTSTORE=true) para "
                "confiar no repositório do Windows. Se você ainda vê este erro: (1) confirme "
                "que o certificado da CA interna está instalado no Windows (o mesmo que o "
                "navegador usa), OU (2) aponte CA_SSL_CERT_FILE para o bundle .pem da CA, "
                "OU (3) só para DSV, defina CA_SSL_VERIFY=false. Depois reinicie o backend."
            ),
            detail=detail,
            http_status=502,
        )

    # 2) Timeout de conexão
    if isinstance(exc, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.PoolTimeout)):
        return AppError(
            category=ErrorCategory.INFRA_REDE,
            code="NETWORK_TIMEOUT",
            message=f"Timeout ao conectar em {url}.",
            cause=(
                "O host não respondeu a tempo. Geralmente significa que a máquina "
                "não está na rede interna da Petrobras (VPN/RIC ausente) ou o serviço está fora."
            ),
            resolution="Confirme a conexão VPN/RIC e se o host está no ar. Depois tente novamente.",
            detail=detail,
            http_status=504,
        )

    # 3) Falha de conexão (DNS, recusada, host inacessível)
    if isinstance(exc, httpx.ConnectError):
        return AppError(
            category=ErrorCategory.INFRA_REDE,
            code="NETWORK_CONNECT_FAILED",
            message=f"Não foi possível conectar em {url}.",
            cause=(
                "Host inacessível: pode ser ausência de VPN/RIC, DNS interno não "
                "resolvido, firewall, ou o serviço do CA estar fora do ar."
            ),
            resolution=(
                "Verifique VPN/RIC, se o DNS interno resolve o host e se o serviço "
                "do CA está disponível. Depois tente novamente."
            ),
            detail=detail,
            http_status=502,
        )

    # 4) Outras falhas de transporte do httpx
    if isinstance(exc, httpx.TransportError):
        return AppError(
            category=ErrorCategory.INFRA_REDE,
            code="NETWORK_TRANSPORT_ERROR",
            message=f"Erro de transporte de rede ao acessar {url}.",
            cause="Falha de baixo nível na comunicação de rede com o host.",
            resolution="Verifique a rede/VPN e tente novamente. Se persistir, contate a infra.",
            detail=detail,
            http_status=502,
        )

    # 5) Não classificado -> trata como erro do servidor/código (inesperado)
    return AppError(
        category=ErrorCategory.SERVIDOR,
        code="UNEXPECTED_NETWORK_CALL_ERROR",
        message=f"Erro inesperado ao chamar {url}.",
        cause=f"Exceção não tratada durante a chamada ao {who.value}.",
        resolution="Verifique o log do servidor para o traceback completo.",
        detail=detail,
        http_status=500,
    )
