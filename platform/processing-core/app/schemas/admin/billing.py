from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.billing_period import BillingPeriodType
from app.models.invoice import InvoiceStatus


class TariffPlanRead(BaseModel):
    """Representation of a tariff plan for admin API."""

    id: str
    name: str
    params: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TariffPlanListResponse(BaseModel):
    """Paginated list of tariff plans."""

    items: list[TariffPlanRead]
    total: int
    limit: int
    offset: int


class TariffPricePayload(BaseModel):
    """Input payload for creating or updating tariff prices."""

    id: int | None = Field(default=None, description="Pass id to update existing price")
    product_id: str
    partner_id: str | None = None
    azs_id: str | None = None
    price_per_liter: Decimal
    cost_price_per_liter: Decimal | None = None
    currency: str
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    priority: int = 100


class TariffPriceRead(TariffPricePayload):
    """Tariff price entity returned to clients."""

    id: int
    tariff_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TariffPriceListResponse(BaseModel):
    """Collection of tariff prices."""

    items: list[TariffPriceRead]


class InvoiceLineRead(BaseModel):
    """Single line of an invoice."""

    id: str
    invoice_id: str
    operation_id: str | None = None
    card_id: str | None = None
    product_id: str
    liters: Decimal | None = None
    unit_price: Decimal | None = None
    line_amount: int
    tax_amount: int
    partner_id: str | None = None
    azs_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceRead(BaseModel):
    """Invoice with aggregated totals and optional lines."""

    id: str
    client_id: str
    period_from: date
    period_to: date
    currency: str
    total_amount: int
    tax_amount: int
    total_with_tax: int
    status: InvoiceStatus
    created_at: datetime | None = None
    issued_at: datetime | None = None
    paid_at: datetime | None = None
    external_number: str | None = None
    lines: list[InvoiceLineRead] = []

    model_config = ConfigDict(from_attributes=True)


class InvoiceListResponse(BaseModel):
    """Paginated list of invoices for admin UI."""

    items: list[InvoiceRead]
    total: int
    limit: int
    offset: int


class InvoiceGenerateRequest(BaseModel):
    """Parameters for invoice generation job."""

    period_from: date
    period_to: date
    status: InvoiceStatus = InvoiceStatus.ISSUED


class InvoiceGenerateResponse(BaseModel):
    """Result of invoice generation run."""

    created_ids: list[str]


class InvoiceStatusChangeRequest(BaseModel):
    """Payload to move invoice to another lifecycle status."""

    status: InvoiceStatus


class BillingRunRequest(BaseModel):
    """Manual billing run parameters."""

    period_type: BillingPeriodType = BillingPeriodType.ADHOC
    start_at: datetime
    end_at: datetime
    tz: str = "UTC"
    client_id: str | None = None


class BillingRunResponse(BaseModel):
    """Aggregated result of billing run."""

    billing_period_id: str
    period_from: date
    period_to: date
    clients_processed: int
    invoices_created: int
    invoices_rebuilt: int
    invoices_skipped: int
    invoice_lines_created: int
    total_amount: int
