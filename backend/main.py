"""
POC Python — FastAPI
Ponto de entrada principal da API.

Fluxo único: o frontend tem um botão "Conectar" que chama /auth/login;
o CA autentica no Entra e o /auth/entra-callback retorna, num único JSON,
todas as informações do usuário (Entra + CAv4).
"""

import logging
import os
import traceback
from datetime import datetime
from typing import Any

import fastapi
import fastapi.middleware.cors
from fastapi.responses import JSONResponse

from auth import router as auth_router
from config import get_settings
from errors import CATEGORY_LABEL, AppError, ErrorCategory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ca.main")

# --- TLS na rede corporativa Petrobras --------------------------------------
# Faz o Python confiar no repositório de certificados do SISTEMA (Windows),
# igual ao navegador e ao PowerShell. Resolve o erro de certificado da CA
# interna (CERTIFICATE_VERIFY_FAILED) sem exportar .pem nem desligar verificação.
if get_settings().CA_SSL_USE_TRUSTSTORE:
    try:
        import truststore

        truststore.inject_into_ssl()
        logger.info("[v0] TLS: truststore ATIVO (usando o repositório de certificados do SO).")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[v0] TLS: falha ao ativar truststore (%s). Seguindo com certifi.", exc)

app = fastapi.FastAPI(
    title="Pock Python POC",
    description="Login CA Petrobras (Entra) + consulta CAv4",
    version="0.1.0",
)

# CORS: origem do frontend (separado por vírgula em CORS_ALLOW_ORIGINS).
# Em dev, cai para localhost:3000.
_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "")
_allow_origins = [o.strip() for o in _origins_env.split(",") if o.strip()] or [
    "http://localhost:3000",
]

app.add_middleware(
    fastapi.middleware.cors.CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas de autenticação (login no CA/Entra + consulta CAv4)
app.include_router(auth_router)


# --- Handlers globais de erro: SEMPRE respostas categorizadas, nunca genéricas ---


@app.exception_handler(AppError)
async def app_error_handler(_request: fastapi.Request, exc: AppError) -> JSONResponse:
    """Resposta padronizada para erros conhecidos/categorizados."""
    logger.error("[v0] AppError — %s", exc.log_line())
    return JSONResponse(status_code=exc.http_status, content=exc.to_dict())


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    _request: fastapi.Request, exc: Exception
) -> JSONResponse:
    """
    Catch-all: qualquer exceção não tratada é, por definição, um BUG do nosso
    código/servidor. Logamos o traceback completo e devolvemos um erro
    categorizado como CODIGO/SERVIDOR (sem vazar stack para o cliente).
    """
    tb = traceback.format_exc()
    logger.error("[v0] Exceção NÃO TRATADA (provável bug de código):\n%s", tb)
    body = {
        "error": {
            "category": ErrorCategory.CODIGO.value,
            "category_label": CATEGORY_LABEL[ErrorCategory.CODIGO],
            "code": "UNHANDLED_EXCEPTION",
            "message": "Erro interno não tratado no backend.",
            "cause": f"{type(exc).__name__}: {exc}",
            "resolution": "Bug do código/servidor. Veja o traceback no log do backend.",
            "detail": f"{type(exc).__name__}: {exc}",
        }
    }
    return JSONResponse(status_code=500, content=body)


@app.get("/health", tags=["Sistema"])
async def health() -> dict[str, Any]:
    """Verifica se a API está funcionando."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": app.version,
    }
