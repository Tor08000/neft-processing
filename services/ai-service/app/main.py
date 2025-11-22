from __future__ import annotations

"""Основной модуль FastAPI для NEFT AI Service."""

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from neft_shared.logging_setup import get_logger, init_logging

from .api.v1.health import router as health_router
from .api.v1.score import router as score_router
from .config import settings

SERVICE_NAME = os.getenv("SERVICE_NAME", "ai-service")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_logging(default_level=settings.log_level, service_name=SERVICE_NAME)
    logger = get_logger(__name__)
    logger.info("AI service starting up")
    try:
        yield
    finally:
        logger.info("AI service shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="NEFT AI Service",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(score_router)
    return app


app = create_app()
