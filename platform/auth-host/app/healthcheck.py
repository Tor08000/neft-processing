from __future__ import annotations

import logging
import os

from app.alembic_runtime import check_db_readiness
from app.schemas.auth import HealthResponse
from app.settings import get_settings
from app.services import keys

logger = logging.getLogger(__name__)


def _database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://{user}:{password}@{host}:{port}/{db}".format(
            user=os.getenv("POSTGRES_USER", "neft"),
            password=os.getenv("POSTGRES_PASSWORD", "change-me"),
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            db=os.getenv("POSTGRES_DB", "neft"),
        ),
    )


def build_health_response() -> tuple[HealthResponse, int]:
    try:
        settings = get_settings()
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Health check failed to load settings: %s", exc)
        return HealthResponse(status="fail", service="auth-host"), 503

    if not settings.auth_issuer.strip() or not settings.auth_audience.strip():
        return (
            HealthResponse(status="fail", service="auth-host", reason="invalid_token_config"),
            503,
        )

    keypair_valid, reason = keys.validate_keypair_files()
    if not keypair_valid:
        reason = reason or "rsa_keys_missing"
        return (
            HealthResponse(status="fail", service="auth-host", reason=reason),
            503,
        )

    db_state = check_db_readiness(_database_url())
    if not db_state.available:
        return (
            HealthResponse(status="fail", service="auth-host", reason=db_state.reason or "db_unavailable"),
            503,
        )

    if db_state.missing_tables:
        return (
            HealthResponse(
                status="fail",
                service="auth-host",
                reason=f"missing_tables:{','.join(db_state.missing_tables)}",
            ),
            503,
        )

    if not db_state.revision_matches_head:
        return (
            HealthResponse(
                status="fail",
                service="auth-host",
                reason=db_state.reason or "alembic_not_ready",
            ),
            503,
        )

    return HealthResponse(status="ok", service="auth-host"), 200
