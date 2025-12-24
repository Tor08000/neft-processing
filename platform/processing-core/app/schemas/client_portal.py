from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field
from app.models.invoice import InvoiceStatus


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


class ClientInvoiceSummary(BaseModel):
    """Invoice summary item without internal fields."""

    id: str
    number: str
    issued_at: datetime | None = None
    status: InvoiceStatus
    amount_total: Decimal
    amount_paid: Decimal
    amount_refunded: Decimal
    amount_due: Decimal
    currency: str


class ClientInvoicePayment(BaseModel):
    id: str
    amount: Decimal
    status: str
    provider: str | None = None
    external_ref: str | None = None
    created_at: datetime


class ClientInvoiceRefund(BaseModel):
    id: str
    amount: Decimal
    status: str
    provider: str | None = None
    external_ref: str | None = None
    created_at: datetime
    reason: str | None = None


class ClientInvoiceDetails(ClientInvoiceSummary):
    """Detailed invoice representation with payments and refunds."""

    pdf_available: bool = False
    payments: List[ClientInvoicePayment] = Field(default_factory=list)
    refunds: List[ClientInvoiceRefund] = Field(default_factory=list)


class ClientInvoiceListResponse(BaseModel):
    """Collection of client invoices."""

    items: List[ClientInvoiceSummary]
    total: int
    limit: int
    offset: int


class ClientExportItem(BaseModel):
    type: str
    title: str
    created_at: datetime | None = None
    download_url: str


class ClientExportListResponse(BaseModel):
    items: List[ClientExportItem]


class ClientAuditEvent(BaseModel):
    id: str
    ts: datetime
    event_type: str
    entity_type: str
    entity_id: str
    action: str | None = None
    actor_type: str | None = None
    actor_id: str | None = None
    external_refs: dict | None = None
    before: dict | None = None
    after: dict | None = None
    hash: str | None = None
    prev_hash: str | None = None


class ClientAuditListResponse(BaseModel):
    items: List[ClientAuditEvent]
    total: int
    limit: int
    offset: int
