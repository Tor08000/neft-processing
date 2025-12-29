import logging
import os
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html

from app.api.routes.admin_users import router as admin_users_router
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.processing import router as processing_router
from app.bootstrap import seed_demo_client_account
from app.metrics import metrics_middleware, metrics_response

DEFAULT_API_PREFIX = "/api/auth"
LEGACY_API_PREFIX = "/api"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NEFT Auth Host")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(metrics_middleware)


def _normalize_prefix(prefix: str, default: str) -> str:
    if not prefix:
        return default
    normalized = prefix if prefix.startswith("/") else f"/{prefix}"
    return normalized.rstrip("/") or default


API_PREFIX_AUTH = _normalize_prefix(os.getenv("API_PREFIX_AUTH", DEFAULT_API_PREFIX), DEFAULT_API_PREFIX)

app.include_router(health_router, prefix=LEGACY_API_PREFIX)
app.include_router(auth_router, prefix=LEGACY_API_PREFIX)
app.include_router(admin_users_router, prefix=LEGACY_API_PREFIX)
app.include_router(processing_router, prefix=LEGACY_API_PREFIX)

app.include_router(health_router, prefix=API_PREFIX_AUTH)
app.include_router(auth_router, prefix=API_PREFIX_AUTH)
app.include_router(admin_users_router, prefix=API_PREFIX_AUTH)
app.include_router(processing_router, prefix=API_PREFIX_AUTH)

api_prefixed_router = APIRouter(prefix="/api/auth")
api_prefixed_router.include_router(health_router)
api_prefixed_router.include_router(auth_router)
api_prefixed_router.include_router(admin_users_router)
api_prefixed_router.include_router(processing_router)


@app.get("/health")
@app.get(f"{API_PREFIX_AUTH}/health")
def health_root():
    return {"status": "ok", "service": "auth-host"}


@app.get("/metrics", include_in_schema=False)
@app.get("/api/v1/metrics", include_in_schema=False)
def metrics_root():
    return metrics_response()


@api_prefixed_router.get("/health")
def prefixed_health_root():
    return {"status": "ok", "service": "auth-host"}


@app.get("/api/auth/openapi.json", include_in_schema=False)
def prefixed_openapi():
    return app.openapi()


@app.get("/api/auth/docs", include_in_schema=False)
def prefixed_docs():
    return get_swagger_ui_html(openapi_url="/api/auth/openapi.json", title="NEFT Auth API")


app.include_router(api_prefixed_router)


@app.on_event("startup")
async def bootstrap_demo_user() -> None:
    logger.info("auth-host: bootstrap demo users start")
    await seed_demo_client_account()
    logger.info("auth-host: bootstrap demo users done")
