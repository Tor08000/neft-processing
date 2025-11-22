from __future__ import annotations

import os

from fastapi import FastAPI
from pydantic import BaseModel

from neft_shared.logging_setup import init_logging, get_logger

# ---------------------------------------------------------------------------
#  Логирование и настройки сервиса
# ---------------------------------------------------------------------------

SERVICE_NAME = os.getenv("SERVICE_NAME", "auth-host")

init_logging(service_name=SERVICE_NAME)
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
#  Приложение FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(title="NEFT Auth Host", version="1.0.0")


@app.get("/health")
def health():
    logger.info("Health check", extra={"endpoint": "/health"})
    return {"status": "ok", "service": "auth-host"}


# --- Модели для authorize (упрощённо) ---


class TxAuthorizeRequest(BaseModel):
    card_token: str
    amount: int
    product_code: str


class TxAuthorizeResponse(BaseModel):
    authorized: bool
    reason: str | None = None


@app.post("/v1/tx/authorize", response_model=TxAuthorizeResponse)
def authorize_tx(payload: TxAuthorizeRequest):
    """
    Упрощённая заглушка авторизации.
    Всегда авторизует, но логирует запрос.
    """
    logger.info(
        "Authorize request",
        extra={
            "endpoint": "/v1/tx/authorize",
            "card_token": payload.card_token,
            "amount": payload.amount,
            "product_code": payload.product_code,
        },
    )
    return TxAuthorizeResponse(authorized=True, reason=None)
