from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from neft_shared.logging_setup import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class AdminWriteContext:
    actor_id: str | None
    action: str
    reason: str
    request_id: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] | None = None


def log_admin_write_attempt(ctx: AdminWriteContext) -> None:
    logger.info(
        "admin.write.attempt",
        extra={
            "actor_id": ctx.actor_id,
            "action": ctx.action,
            "reason": ctx.reason,
            "request_id": ctx.request_id,
            "correlation_id": ctx.correlation_id,
            "metadata": ctx.metadata or {},
        },
    )


__all__ = ["AdminWriteContext", "log_admin_write_attempt"]
