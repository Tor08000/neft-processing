from __future__ import annotations

import logging
from pathlib import Path

from app.schemas.auth import HealthResponse
from app.settings import get_settings

logger = logging.getLogger(__name__)


def build_health_response() -> tuple[HealthResponse, int]:
    status_code = 200
    status = "ok"

    try:
        settings = get_settings()
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Health check failed to load settings: %s", exc)
        return HealthResponse(status="fail", service="auth-host"), 500

    private_key_path = Path(settings.auth_private_key_path)
    public_key_path = Path(settings.auth_public_key_path)
    if not private_key_path.exists() or not public_key_path.exists():
        status = "fail"
        status_code = 500

    return HealthResponse(status=status, service="auth-host"), status_code
