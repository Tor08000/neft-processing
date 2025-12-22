from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field
from app.models.invoice import InvoicePdfStatus, InvoiceStatus


class ClientUser(BaseModel):
    id: str
    email: str
    role: str = "CLIENT_USER"
    organization_id: str
    organization_name: str | None = None


class ClientOperation(BaseModel):
    id: str
    date: datetime
    type: str
    status: str
    amount: int
    currency: str = "RUB"
    card_ref: str | None = None
    fuel_type: str | None = None


class ClientOperationsResponse(BaseModel):
    items: List[ClientOperation]
    total: int
    limit: int
    offset: int


class LimitItem(BaseModel):
    id: str
    type: str
    period: str
    amount: int
    used: int = 0
    remaining: int = Field(default=0, description="Оставшийся лимит")


class LimitsResponse(BaseModel):
    items: List[LimitItem]


class DashboardTotals(BaseModel):
    total_operations: int
    total_amount: int
    period: str
    active_limits: int
    spending_trend: List[int]
    dates: List[date]


class DashboardResponse(BaseModel):
    summary: DashboardTotals
    recent_operations: List[ClientOperation]
    limits: List[LimitItem]


class ClientProfile(BaseModel):
    id: str
    name: str
    external_id: str | None = None
    inn: str | None = None
    tariff_plan: str | None = None
    account_manager: str | None = None
    status: str


class CardLimit(BaseModel):
    type: str
    value: int
    window: str


class ClientCard(BaseModel):
    id: str
    pan_masked: str | None = None
    status: str
    limits: List[CardLimit] = Field(default_factory=list)


class ClientCardsResponse(BaseModel):
    items: List[ClientCard]


class OperationSummary(BaseModel):
    id: str
    created_at: datetime
    status: str
    amount: int
    currency: str = "RUB"
    card_id: str
    product_type: str | None = None
    merchant_id: str | None = None
    terminal_id: str | None = None
    reason: str | None = None
    quantity: Decimal | None = None


class OperationDetails(OperationSummary):
    pass


class BalanceItem(BaseModel):
    currency: str
    current: Decimal
    available: Decimal


class BalancesResponse(BaseModel):
    items: List[BalanceItem]


class OperationsPage(BaseModel):
    items: List[OperationSummary]
    total: int
    limit: int
    offset: int


class StatementResponse(BaseModel):
    currency: str
    start_balance: Decimal
    end_balance: Decimal
    credits: Decimal
    debits: Decimal


class ClientInvoiceLine(BaseModel):
    """Simplified invoice line for client-facing APIs."""

    card_id: str | None = None
    product_id: str
    liters: Decimal | None = None
    amount: int = Field(alias="line_amount")
    tax_amount: int

    model_config = {"from_attributes": True, "populate_by_name": True}


class ClientInvoiceSummary(BaseModel):
    """Invoice summary item without internal fields."""

    id: str
    period_from: date
    period_to: date
    currency: str
    due_date: date | None = None
    payment_terms_days: int | None = None
    total_amount: int
    tax_amount: int
    total_with_tax: int
    amount_paid: int
    amount_due: int
    status: InvoiceStatus
    created_at: datetime | None = None
    issued_at: datetime | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    paid_at: datetime | None = None
    cancelled_at: datetime | None = None
    closed_at: datetime | None = None
    refunded_at: datetime | None = None
    pdf_url: str | None = None
    pdf_status: InvoicePdfStatus | None = None
    pdf_generated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ClientInvoiceDetails(ClientInvoiceSummary):
    """Detailed invoice representation with line items."""

    lines: List[ClientInvoiceLine] = Field(default_factory=list)


class ClientInvoiceListResponse(BaseModel):
    """Collection of client invoices."""

    items: List[ClientInvoiceSummary]
    total: int
    limit: int
    offset: int
