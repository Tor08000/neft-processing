from __future__ import annotations

import logging
from typing import Any

from app.config import settings


logger = logging.getLogger(__name__)


def notify_sla_breach(*, payload: dict[str, Any]) -> bool:
    if not settings.ACCOUNTING_EXPORT_ALERTING_ENABLED:
        logger.info("accounting_export_alerting_disabled", extra=payload)
        return False
    logger.warning(
        "accounting_export_sla_alert_stub",
        extra={
            "targets": settings.ACCOUNTING_EXPORT_ALERTING_TARGETS,
            **payload,
        },
    )
    return True


__all__ = ["notify_sla_breach"]
