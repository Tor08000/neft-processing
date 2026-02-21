import logging
import os
from fastapi import APIRouter, FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html

from app.adapters.oauth_providers import oidc_client
from app.api.routes.admin_users import router as admin_users_router
from app.api.routes.auth import router as auth_router
from app.api.routes.sso import router as sso_router
from app.api.routes.admin_sso import router as admin_sso_router
from app.api.routes.health import router as health_router
from app.api.routes.internal import router as internal_router
from app.api.routes.processing import router as processing_router
from app.bootstrap import bootstrap_required_users
from app.db import ensure_users_table
from app.healthcheck import build_health_response
from app.services.keys import get_public_jwk, initialize_keys
from app.settings import get_settings
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
app.include_router(sso_router, prefix=LEGACY_API_PREFIX)
app.include_router(admin_sso_router, prefix=LEGACY_API_PREFIX)
app.include_router(admin_users_router, prefix=LEGACY_API_PREFIX)
app.include_router(processing_router, prefix=LEGACY_API_PREFIX)
app.include_router(internal_router, prefix=LEGACY_API_PREFIX)

app.include_router(health_router, prefix=API_PREFIX_AUTH)
app.include_router(auth_router, prefix=API_PREFIX_AUTH)
app.include_router(sso_router, prefix=API_PREFIX_AUTH)
app.include_router(admin_sso_router, prefix=API_PREFIX_AUTH)
app.include_router(admin_users_router, prefix=API_PREFIX_AUTH)
app.include_router(processing_router, prefix=API_PREFIX_AUTH)
app.include_router(internal_router, prefix=API_PREFIX_AUTH)

api_prefixed_router = APIRouter(prefix="/api/auth")
api_prefixed_router.include_router(health_router)
api_prefixed_router.include_router(auth_router)
api_prefixed_router.include_router(sso_router)
api_prefixed_router.include_router(admin_sso_router)
api_prefixed_router.include_router(admin_users_router)
api_prefixed_router.include_router(processing_router)
api_prefixed_router.include_router(internal_router)


@app.get("/health")
@app.get(f"{API_PREFIX_AUTH}/health")
def health_root():
    response, status_code = build_health_response()
    content = response.model_dump(exclude_none=True)
    if status_code != status.HTTP_200_OK:
        return JSONResponse(status_code=status_code, content=content)
    return JSONResponse(status_code=status_code, content=content)


@app.get("/metrics", include_in_schema=False)
@app.get("/api/v1/metrics", include_in_schema=False)
def metrics_root():
    return metrics_response()


@app.get("/.well-known/jwks.json", include_in_schema=False)
@app.get(f"{API_PREFIX_AUTH}/.well-known/jwks.json", include_in_schema=False)
def jwks_root():
    return {"keys": [get_public_jwk()]}


@api_prefixed_router.get("/health")
def prefixed_health_root():
    response, status_code = build_health_response()
    content = response.model_dump(exclude_none=True)
    if status_code != status.HTTP_200_OK:
        return JSONResponse(status_code=status_code, content=content)
    return JSONResponse(status_code=status_code, content=content)


@app.get("/api/auth/openapi.json", include_in_schema=False)
def prefixed_openapi():
    return app.openapi()


@app.get("/api/auth/docs", include_in_schema=False)
def prefixed_docs():
    return get_swagger_ui_html(openapi_url="/api/auth/openapi.json", title="NEFT Auth API")


app.include_router(api_prefixed_router)


@app.on_event("startup")
async def bootstrap_demo_user() -> None:
    await ensure_users_table()
    logger.info("auth-host: bootstrap start")
    initialize_keys()
    settings = get_settings()
    await oidc_client.fail_fast_validate_enabled_providers()
    dev_seed_users = (os.getenv("DEV_SEED_USERS", "1") or "1").strip().lower() not in {"0", "false", "no", "off"}
    if settings.bootstrap_enabled and dev_seed_users:
        try:
            await bootstrap_required_users(settings)
        except Exception:
            app_env = (getattr(settings, "APP_ENV", "prod") or "prod").strip().lower()
            start_mode = (os.getenv("START_MODE", "") or "").strip().lower()
            if app_env == "dev" or start_mode == "dev":
                logger.warning(
                    "auth-host: demo bootstrap failed in dev; continuing startup",
                    exc_info=True,
                )
            else:
                logger.exception("auth-host: bootstrap failed in non-dev environment")
                raise
    else:
        logger.info("auth-host: bootstrap disabled; skipping demo seed")
    if dev_seed_users:
        logger.info(
            "DEV users ready: client@neft.local, partner@neft.local, admin@neft.local"
        )
    logger.info("auth-host: bootstrap done")
