"""
Основной модуль FastAPI для NEFT AI Service.
Пока реализуем только health-endpoint, чтобы контейнер успешно проходил healthcheck.
Дальше сюда можно будет добавлять реальные AI-эндпоинты.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict

from fastapi import FastAPI

from neft_shared.logging_setup import init_logging, get_logger

SERVICE_NAME = os.getenv("SERVICE_NAME", "ai-service")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Настройка логирования при старте
    init_logging(default_level=LOG_LEVEL, service_name=SERVICE_NAME)
    logger = get_logger(__name__, service=SERVICE_NAME)
    logger.info("AI service starting up")
    try:
        yield
    finally:
        logger.info("AI service shutting down")


app = FastAPI(
    title="NEFT AI Service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> Dict[str, str]:
    """
    Простой health-endpoint для docker healthcheck.
    """
    return {"status": "ok"}
