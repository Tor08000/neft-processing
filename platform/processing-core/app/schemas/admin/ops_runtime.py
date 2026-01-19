from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _normalize_env_name(raw: str) -> str:
    value = raw.lower()
    if value in {"local", "dev"}:
        return "dev"
    if "stage" in value:
        return "stage"
    if "prod" in value:
        return "prod"
    return value


class OpsEnvSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    build: str

    @classmethod
    def from_env(cls) -> "OpsEnvSummary":
        name = _normalize_env_name(os.getenv("NEFT_ENV", "dev"))
        build = os.getenv("GIT_SHA", os.getenv("BUILD_SHA", "unknown"))
        return cls(name=name, build=build)


class OpsTimeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    now: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OpsCoreSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    health: str


class OpsExportQueueSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queued: int
    running: int
    failed_1h: int


class OpsPayoutQueueSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queued: int
    blocked: int


class OpsSettlementQueueSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queued: int
    finalizing: int


class OpsEmailQueueSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queued: int
    failed_1h: int


class OpsHelpdeskQueueSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queued: int
    failed_1h: int


class OpsQueuesSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exports: OpsExportQueueSummary
    payouts: OpsPayoutQueueSummary
    settlements: OpsSettlementQueueSummary
    emails: OpsEmailQueueSummary
    helpdesk_outbox: OpsHelpdeskQueueSummary

    @staticmethod
    def build_exports(*, queued: int, running: int, failed_1h: int) -> OpsExportQueueSummary:
        return OpsExportQueueSummary(queued=queued, running=running, failed_1h=failed_1h)

    @staticmethod
    def build_emails(*, queued: int, failed_1h: int) -> OpsEmailQueueSummary:
        return OpsEmailQueueSummary(queued=queued, failed_1h=failed_1h)


class OpsMorTopReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str
    count: int


class OpsMorSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    immutable_violations_24h: int
    payout_blocked_total_24h: int
    payout_blocked_top_reasons: list[OpsMorTopReason]
    clawback_required_24h: int
    admin_overrides_24h: int


class OpsBillingSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overdue_orgs: int
    overdue_amount: int
    dunning_sent_24h: int
    auto_suspends_24h: int


class OpsReconciliationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    imports_24h: int
    parse_failed_24h: int
    unmatched_24h: int
    auto_approved_24h: int


class OpsExportsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jobs_24h: int
    failed_24h: int
    avg_duration_sec: int


class OpsSupportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    open_tickets: int
    sla_breaches_24h: int


class OpsSignalsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["GREEN", "YELLOW", "RED"]
    reasons: list[str]


class OpsSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    env: OpsEnvSummary
    time: OpsTimeSummary
    core: OpsCoreSummary
    queues: OpsQueuesSummary
    mor: OpsMorSummary
    billing: OpsBillingSummary
    reconciliation: OpsReconciliationSummary
    exports: OpsExportsSummary
    support: OpsSupportSummary
    signals: OpsSignalsSummary


class OpsHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool


class OpsBlockedPayoutItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    settlement_id: str
    status: str
    amount: int
    currency: str
    created_at: datetime
    error: str | None = None


class OpsFailedExportItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    report_type: str
    format: str
    status: str
    created_at: datetime
    error_message: str | None = None


class OpsFailedReconciliationImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    uploaded_at: datetime
    error: str | None = None


class OpsSupportBreachItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    priority: str
    created_at: datetime
    sla_first_response_status: str
    sla_resolution_status: str


class OpsFailedExportsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OpsFailedExportItem]


class OpsBlockedPayoutsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OpsBlockedPayoutItem]


class OpsFailedImportsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OpsFailedReconciliationImport]


class OpsSupportBreachesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OpsSupportBreachItem]
