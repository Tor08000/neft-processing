from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.export_jobs import ExportJobFormat, ExportJobReportType, ExportJobStatus
from app.models.report_schedules import ReportScheduleKind, ReportScheduleStatus

class ClientOrgIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org_type: str = Field(..., description="LEGAL/IP/INDIVIDUAL")
    name: str = Field(..., min_length=1)
    inn: str | None = None
    kpp: str | None = None
    ogrn: str | None = None
    address: str | None = None


class ClientOrgOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    org_type: str | None = None
    name: str
    inn: str | None = None
    kpp: str | None = None
    ogrn: str | None = None
    address: str | None = None
    status: str


class ContractInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: str
    status: str
    pdf_url: str | None = None
    version: int | None = None


class ContractSignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    otp: str


class ClientSubscriptionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_code: str
    status: str | None = None
    modules: dict[str, dict[str, Any]]
    limits: dict[str, dict[str, Any]]


class ClientSubscriptionSelectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_code: str
    auto_renew: bool = False
    duration_months: int | None = None


class ClientUserInviteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    role: str


class ClientUserSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    email: str
    role: str
    status: str | None = None
    last_login: str | None = None


class ClientUsersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ClientUserSummary]


class ClientDocSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    status: str
    date: date
    download_url: str


class ClientDocsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ClientDocSummary]


class ClientAuditEventSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    created_at: datetime
    org_id: str | None = None
    actor_user_id: str | None = None
    actor_label: str | None = None
    action: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    entity_label: str | None = None
    request_id: str | None = None
    ip: str | None = None
    ua: str | None = None
    result: str | None = None
    summary: str | None = None


class ClientAuditEventsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ClientAuditEventSummary]
    next_cursor: str | None = None


class ExportJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_type: ExportJobReportType
    format: ExportJobFormat
    filters: dict[str, Any] = Field(default_factory=dict)


class ExportJobCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: ExportJobStatus


class ExportJobOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    org_id: str
    created_by_user_id: str
    report_type: ExportJobReportType
    format: ExportJobFormat
    status: ExportJobStatus
    filters: dict[str, Any]
    file_name: str | None = None
    content_type: str | None = None
    row_count: int | None = None
    processed_rows: int
    estimated_total_rows: int | None = None
    progress_percent: int | None = None
    avg_rows_per_sec: float | None = None
    eta_seconds: int | None = None
    eta_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    expires_at: datetime | None = None


class ExportJobListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ExportJobOut]
    next_cursor: str | None = None


class ReportScheduleDelivery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    in_app: bool = True
    email_to_creator: bool = True
    email_to_roles: list[str] = Field(default_factory=list)


class ReportScheduleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_type: ExportJobReportType
    format: ExportJobFormat
    filters: dict[str, Any] = Field(default_factory=dict)
    schedule_kind: ReportScheduleKind
    schedule_meta: dict[str, int]
    timezone: str = "Europe/Moscow"
    delivery: ReportScheduleDelivery = Field(default_factory=ReportScheduleDelivery)


class ReportScheduleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: ExportJobFormat | None = None
    filters: dict[str, Any] | None = None
    schedule_kind: ReportScheduleKind | None = None
    schedule_meta: dict[str, int] | None = None
    timezone: str | None = None
    delivery: ReportScheduleDelivery | None = None


class ReportScheduleOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    org_id: str
    created_by_user_id: str
    report_type: ExportJobReportType
    format: ExportJobFormat
    filters: dict[str, Any]
    schedule_kind: ReportScheduleKind
    schedule_meta: dict[str, int]
    timezone: str
    delivery: ReportScheduleDelivery
    status: ReportScheduleStatus
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    next_run_at_local: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ReportScheduleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ReportScheduleOut]


class ClientAnalyticsPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_: date = Field(..., alias="from")
    to: date


class ClientAnalyticsSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transactions_count: int
    total_spend: float
    total_liters: float | None = None
    active_cards: int
    blocked_cards: int
    unique_drivers: int
    open_tickets: int
    sla_breaches_first: int
    sla_breaches_resolution: int


class ClientAnalyticsTimeseriesPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    spend: float
    liters: float | None = None
    count: int


class ClientAnalyticsTopCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_id: str
    label: str
    spend: float
    count: int
    liters: float | None = None


class ClientAnalyticsTopDriver(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    label: str
    spend: float
    count: int


class ClientAnalyticsTopStation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    station_id: str
    label: str
    spend: float
    count: int
    liters: float | None = None


class ClientAnalyticsTopLists(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cards: list[ClientAnalyticsTopCard]
    drivers: list[ClientAnalyticsTopDriver]
    stations: list[ClientAnalyticsTopStation]


class ClientAnalyticsSupport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    open: int
    avg_first_response_minutes: float | None = None
    avg_resolve_minutes: float | None = None


class ClientDashboardWidget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    key: str
    data: Any | None = None


class ClientDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    timezone: str
    widgets: list[ClientDashboardWidget]


class ClientAnalyticsSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: ClientAnalyticsPeriod
    summary: ClientAnalyticsSummary
    timeseries: list[ClientAnalyticsTimeseriesPoint]
    tops: ClientAnalyticsTopLists
    support: ClientAnalyticsSupport


class ClientAnalyticsDrillTransaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tx_id: str
    occurred_at: datetime
    card_id: str
    card_label: str
    driver_user_id: str | None = None
    driver_label: str | None = None
    amount: float
    currency: str
    liters: float | None = None
    station: str
    status: str


class ClientAnalyticsDrillResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ClientAnalyticsDrillTransaction]
    next_cursor: str | None = None


class ClientAnalyticsSupportDrillItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    subject: str
    status: str
    priority: str
    created_at: datetime
    first_response_status: str
    resolution_status: str


class ClientAnalyticsSupportDrillResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ClientAnalyticsSupportDrillItem]
    next_cursor: str | None = None
