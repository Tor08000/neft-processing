from __future__ import annotations

import os
from datetime import datetime, timezone

from app.config import settings
from app.schemas.admin.runtime_summary import (
    HealthStatus,
    RuntimeEvents,
    RuntimeHealth,
    RuntimeMoneyRisk,
    RuntimeQueues,
    RuntimeQueueCount,
    RuntimeQueueState,
    RuntimeSummaryResponse,
    RuntimeViolations,
    RuntimeViolationTop,
)


def _normalize_env_name(raw: str) -> str:
    value = raw.lower()
    if value in {"local", "dev"}:
        return "dev"
    if "stage" in value:
        return "stage"
    if "prod" in value:
        return "prod"
    return value


def build_runtime_summary() -> RuntimeSummaryResponse:
    environment = _normalize_env_name(os.getenv("NEFT_ENV", "dev"))
    return RuntimeSummaryResponse(
        ts=datetime.now(timezone.utc),
        environment=environment,
        read_only=settings.ADMIN_READ_ONLY,
        health=RuntimeHealth(
            core_api=HealthStatus.UP,
            auth_host=HealthStatus.UP,
            gateway=HealthStatus.UP,
            postgres=HealthStatus.UP,
            redis=HealthStatus.UP,
            minio=HealthStatus.UP,
            clickhouse=HealthStatus.UP,
        ),
        queues=RuntimeQueues(
            settlement=RuntimeQueueState(depth=0, oldest_age_sec=0),
            payout=RuntimeQueueState(depth=0, oldest_age_sec=0),
            blocked_payouts=RuntimeQueueCount(count=0),
            payment_intakes_pending=RuntimeQueueCount(count=0),
        ),
        violations=RuntimeViolations(
            immutable=RuntimeViolationTop(count=0, top=[]),
            invariants=RuntimeViolationTop(count=0, top=[]),
        ),
        money_risk=RuntimeMoneyRisk(
            payouts_blocked=0,
            settlements_pending=0,
            overdue_clients=0,
        ),
        events=RuntimeEvents(critical_last_10=[]),
    )


__all__ = ["build_runtime_summary"]
