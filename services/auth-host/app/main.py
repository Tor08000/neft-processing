from __future__ import annotations

import os

from fastapi import FastAPI

from neft_shared.logging_setup import get_logger, init_logging
from app.api.routes import auth_router, health_router, processing_router
from app.db import init_db

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
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(processing_router)


@app.on_event("startup")
async def startup_event() -> None:
    await init_db()
    logger.info("Auth-host startup complete")
