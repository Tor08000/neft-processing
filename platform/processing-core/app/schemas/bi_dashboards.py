from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BiDashboardMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_from: date
    period_to: date
    currency: str
    mart_version: str


class CfoFinanceTotals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gross_revenue: int
    net_revenue: int
    commission_income: int
    vat: int
    refunds: int
    penalties: int
    margin: int


class CfoFinanceSeriesItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    gross_revenue: int
    net_revenue: int
    commission_income: int
    vat: int
    refunds: int
    penalties: int
    margin: int


class CfoOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    totals: CfoFinanceTotals
    series: list[CfoFinanceSeriesItem]
    meta: BiDashboardMeta


class CashflowTotals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inflow: int
    outflow: int
    net_cashflow: int
    balance_estimated: int


class CashflowSeriesItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    inflow: int
    outflow: int
    net_cashflow: int
    balance_estimated: int


class CfoCashflowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    totals: CashflowTotals
    series: list[CashflowSeriesItem]
    meta: BiDashboardMeta


class OpsSlaTotals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_orders: int
    sla_breaches: int
    avg_resolution_time: float | None
    p95_resolution_time: float | None


class OpsSlaSeriesItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    total_orders: int
    sla_breaches: int
    avg_resolution_time: float | None
    p95_resolution_time: float | None


class OpsSlaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    totals: OpsSlaTotals
    series: list[OpsSlaSeriesItem]
    top_partners_by_breaches: list[dict[str, Any]]
    meta: BiDashboardMeta


class PartnerPerformanceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    partner_id: str
    period: date
    orders_count: int
    revenue: int
    penalties: int
    payout_amount: int
    sla_score: float | None


class PartnerPerformanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PartnerPerformanceItem]
    meta: BiDashboardMeta


class ClientSpendItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: str
    period: date
    spend_total: int
    spend_by_product: dict[str, Any] | None
    fuel_spend: int
    marketplace_spend: int
    avg_ticket: int


class ClientSpendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ClientSpendItem]
    meta: BiDashboardMeta


class AnalyticsAttentionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    description: str | None = None
    href: str
    severity: str | None = None


class AnalyticsSeriesPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    value: int


class AnalyticsDailySpendSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    series: list[AnalyticsSeriesPoint]


class AnalyticsDailyOrdersSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    completed: int
    refunds: int
    series: list[AnalyticsSeriesPoint]


class AnalyticsDailyDeclinesSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    top_reason: str | None = None
    series: list[AnalyticsSeriesPoint]


class AnalyticsAttentionCounter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attention: int


class ClientAnalyticsDailyMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: date = Field(alias="from")
    to: date
    currency: str | None = None
    spend: AnalyticsDailySpendSummary
    orders: AnalyticsDailyOrdersSummary
    declines: AnalyticsDailyDeclinesSummary
    documents: AnalyticsAttentionCounter
    exports: AnalyticsAttentionCounter
    attention: list[AnalyticsAttentionItem]


class AnalyticsTopReasonItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str
    count: int


class AnalyticsDeclineTrendItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    reason: str
    count: int


class AnalyticsDeclineHeatmapItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    station: str
    reason: str
    count: int


class AnalyticsExpensiveDeclineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    reason: str
    amount: int
    station: str | None = None


class ClientAnalyticsDeclinesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    top_reasons: list[AnalyticsTopReasonItem]
    trend: list[AnalyticsDeclineTrendItem]
    heatmap: list[AnalyticsDeclineHeatmapItem] | None = None
    expensive: list[AnalyticsExpensiveDeclineItem]


class AnalyticsTopServiceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    orders: int


class AnalyticsStatusBreakdownItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    count: int


class ClientAnalyticsOrdersSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    completed: int
    cancelled: int
    refunds_rate: int
    refunds_count: int
    avg_order_value: int
    top_services: list[AnalyticsTopServiceItem]
    status_breakdown: list[AnalyticsStatusBreakdownItem]


class AnalyticsDocumentAttentionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    status: str


class ClientAnalyticsDocumentsSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issued: int
    signed: int
    edo_pending: int
    edo_failed: int
    attention: list[AnalyticsDocumentAttentionItem]


class AnalyticsExportSummaryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    checksum: str | None = None
    mapping_version: str | None = None
    created_at: datetime


class ClientAnalyticsExportsSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    ok: int
    mismatch: int
    items: list[AnalyticsExportSummaryItem]


class AnalyticsNamedAmountItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    amount: int


class AnalyticsProductAmountItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: str
    amount: int


class ClientAnalyticsSpendSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str | None = None
    total_spend: int
    avg_daily_spend: int | None = None
    trend: list[AnalyticsSeriesPoint]
    top_stations: list[AnalyticsNamedAmountItem]
    top_merchants: list[AnalyticsNamedAmountItem]
    top_cards: list[AnalyticsNamedAmountItem]
    top_drivers: list[AnalyticsNamedAmountItem]
    product_breakdown: list[AnalyticsProductAmountItem]
    export_available: bool | None = None
    export_dataset: str | None = None


class ClientAnalyticsExportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    dataset: Literal["spend"]
    from_: date = Field(alias="from")
    to: date


class ClientAnalyticsExportJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    dataset: str
    status: str
    format: str
    created_at: datetime
    ready: bool
    error_message: str | None = None


class ClientAnalyticsExportDownloadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    url: str
    sha256: str | None = None
