from __future__ import annotations

import logging
from app.schemas.auth import HealthResponse
from app.settings import get_settings
from app.services import keys

logger = logging.getLogger(__name__)


def build_health_response() -> tuple[HealthResponse, int]:
    status_code = 200
    status = "ok"

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
        status_code = 503
        reason = reason or "rsa_keys_missing"
        return (
            HealthResponse(status="fail", service="auth-host", reason=reason),
            status_code,
        )

    return HealthResponse(status=status, service="auth-host"), status_code
