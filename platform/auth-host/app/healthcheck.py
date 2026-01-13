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
        get_settings()
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Health check failed to load settings: %s", exc)
        return HealthResponse(status="fail", service="auth-host"), 500

    keypair_valid, reason = keys.validate_keypair_files()
    if not keypair_valid:
        status_code = 500
        if reason == "invalid_rsa_keys":
            return (
                HealthResponse(status="error", service="auth-host", reason="invalid_rsa_keys"),
                status_code,
            )
        status = "fail"

    return HealthResponse(status=status, service="auth-host"), status_code
