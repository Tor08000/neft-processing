from __future__ import annotations

"""Основной модуль FastAPI для NEFT AI Service."""

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import APIRouter, FastAPI, Response
from fastapi.openapi.docs import get_swagger_ui_html

from neft_shared.logging_setup import get_logger, init_logging
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .api.v1.health import router as health_router
from .api.v1.score import router as score_router
from .settings import settings

SERVICE_NAME = os.getenv("SERVICE_NAME", "ai-service")
DEFAULT_API_PREFIX = "/api/ai"


def _normalize_prefix(prefix: str, default: str) -> str:
    if not prefix:
        return default
    normalized = prefix if prefix.startswith("/") else f"/{prefix}"
    return normalized.rstrip("/") or default


API_PREFIX_AI = _normalize_prefix(os.getenv("API_PREFIX_AI", DEFAULT_API_PREFIX), DEFAULT_API_PREFIX)


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
    app.include_router(health_router, prefix="/api")
    app.include_router(score_router, prefix="/api")
    app.include_router(health_router, prefix=API_PREFIX_AI)
    app.include_router(score_router, prefix=API_PREFIX_AI)

    prefixed_router = APIRouter(prefix="/api/ai")
    prefixed_router.include_router(health_router)
    prefixed_router.include_router(score_router)

    @app.get("/health")
    async def health_alias():
        return {"status": "ok", "service": "ai-service"}

    prefixed_router.add_api_route("/health", health_alias, methods=["GET"])
    app.include_router(prefixed_router)

    @app.get("/api/ai/openapi.json", include_in_schema=False)
    async def prefixed_openapi():
        return app.openapi()

    @app.get("/api/ai/docs", include_in_schema=False)
    async def prefixed_docs():
        return get_swagger_ui_html(openapi_url="/api/ai/openapi.json", title="AI Service API")

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
