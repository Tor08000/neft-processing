from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class AnalyticsSummaryOut(BaseModel):
    period: str
    revenue: Decimal = Decimal("0")
    orders: int = 0
    avg_check: Decimal = Decimal("0")
    commission_paid: Decimal = Decimal("0")


class ProductAnalyticsOut(BaseModel):
    product_id: str
    orders: int = 0
    revenue: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")
    avg_check: Decimal = Decimal("0")


class ProductAnalyticsResponse(BaseModel):
    items: list[ProductAnalyticsOut] = Field(default_factory=list)
    total: int = 0


class ClientAnalyticsOut(BaseModel):
    new_clients: int = 0
    repeat_clients: int = 0
    ltv: Decimal = Decimal("0")


class ConversionAnalyticsOut(BaseModel):
    view_to_order_rate: float | None = None
    order_to_completed_rate: float | None = None
    created_orders: int = 0
    completed_orders: int = 0
