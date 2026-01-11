from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict


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

