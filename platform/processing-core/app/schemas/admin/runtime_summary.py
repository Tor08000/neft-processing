from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class HealthStatus(str, Enum):
    UP = "UP"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"


class RuntimeHealth(BaseModel):
    core_api: HealthStatus
    auth_host: HealthStatus
    gateway: HealthStatus
    integration_hub: HealthStatus
    document_service: HealthStatus
    logistics_service: HealthStatus
    ai_service: HealthStatus
    postgres: HealthStatus
    redis: HealthStatus
    minio: HealthStatus
    clickhouse: HealthStatus
    prometheus: HealthStatus
    grafana: HealthStatus
    loki: HealthStatus
    otel_collector: HealthStatus


class RuntimeQueueState(BaseModel):
    depth: int
    oldest_age_sec: int


class RuntimeQueueCount(BaseModel):
    count: int


class RuntimeQueues(BaseModel):
    settlement: RuntimeQueueState
    payout: RuntimeQueueState
    blocked_payouts: RuntimeQueueCount
    payment_intakes_pending: RuntimeQueueCount


class RuntimeViolationTop(BaseModel):
    count: int
    top: list[str]


class RuntimeViolations(BaseModel):
    immutable: RuntimeViolationTop
    invariants: RuntimeViolationTop
    sla_penalties: RuntimeViolationTop


class RuntimeMoneyRisk(BaseModel):
    payouts_blocked: int
    settlements_pending: int
    overdue_clients: int


class RuntimeEvent(BaseModel):
    ts: str
    kind: str
    message: str
    correlation_id: str | None = None


class RuntimeEvents(BaseModel):
    critical_last_10: list[RuntimeEvent]


class ExternalProviderStatus(str, Enum):
    DISABLED = "DISABLED"
    CONFIGURED = "CONFIGURED"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    AUTH_FAILED = "AUTH_FAILED"
    TIMEOUT = "TIMEOUT"
    UNSUPPORTED = "UNSUPPORTED"
    RATE_LIMITED = "RATE_LIMITED"


class ExternalProviderHealth(BaseModel):
    service: str
    provider: str
    mode: str
    status: ExternalProviderStatus
    configured: bool = False
    last_success_at: str | None = None
    last_error_code: str | None = None
    message: str | None = None


class RuntimeSummaryResponse(BaseModel):
    ts: datetime
    environment: str
    read_only: bool
    health: RuntimeHealth
    queues: RuntimeQueues
    violations: RuntimeViolations
    money_risk: RuntimeMoneyRisk
    events: RuntimeEvents
    warnings: list[str] = []
    missing_tables: list[str] = []
    external_providers: list[ExternalProviderHealth] = []


__all__ = [
    "HealthStatus",
    "ExternalProviderHealth",
    "ExternalProviderStatus",
    "RuntimeHealth",
    "RuntimeQueues",
    "RuntimeViolations",
    "RuntimeMoneyRisk",
    "RuntimeEvents",
    "RuntimeSummaryResponse",
]
