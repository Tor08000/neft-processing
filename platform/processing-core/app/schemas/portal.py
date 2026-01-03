from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PortalSlaSummary(BaseModel):
    status: str
    violations: int = 0


class MarketplaceSlaObligationSummary(BaseModel):
    metric: str
    threshold: Decimal
    comparison: str
    window: str | None = None
    penalty: str | None = None


class MarketplaceSlaSummary(BaseModel):
    obligations: list[MarketplaceSlaObligationSummary] = Field(default_factory=list)
    penalties: str | None = None


class MarketplacePartnerSummary(BaseModel):
    id: str | None = None
    company_name: str | None = None
    profile_url: str | None = None
    verified: bool | None = None


class MarketplaceProductSummary(BaseModel):
    id: str
    type: str
    title: str
    short_description: str | None = None
    category: str | None = None
    price_model: str | None = None
    price_summary: str | None = None
    partner_name: str | None = None
    partner_id: str | None = None
    published_at: datetime | None = None


class MarketplaceProductListResponse(BaseModel):
    items: list[MarketplaceProductSummary]
    total: int
    limit: int
    offset: int


class MarketplaceProductDetails(BaseModel):
    id: str
    type: str
    title: str
    description: str | None = None
    category: str | None = None
    price_model: str | None = None
    price_summary: str | None = None
    price_config: dict | None = None
    partner: MarketplacePartnerSummary | None = None
    sla_summary: MarketplaceSlaSummary | None = None


class ClientDashboardResponse(BaseModel):
    active_contracts: int
    invoices_due: int
    invoices_due_amount: Decimal
    payments_last_30d: Decimal
    payments_last_30d_count: int
    sla: PortalSlaSummary


class ClientInvoiceSummary(BaseModel):
    invoice_number: str
    period_start: date
    period_end: date
    amount_total: Decimal
    status: str
    due_date: date | None = None
    currency: str


class ClientInvoicePaymentSummary(BaseModel):
    amount: Decimal
    status: str
    provider: str | None = None
    external_ref: str | None = None
    created_at: datetime


class ClientInvoiceRefundSummary(BaseModel):
    amount: Decimal
    status: str
    provider: str | None = None
    external_ref: str | None = None
    created_at: datetime
    reason: str | None = None


class ClientInvoiceDetails(BaseModel):
    invoice_number: str
    period_start: date
    period_end: date
    amount_total: Decimal
    amount_paid: Decimal
    amount_refunded: Decimal
    amount_due: Decimal
    status: str
    due_date: date | None = None
    currency: str
    download_url: str | None = None
    payments: list[ClientInvoicePaymentSummary] = Field(default_factory=list)
    refunds: list[ClientInvoiceRefundSummary] = Field(default_factory=list)


class ClientInvoiceListResponse(BaseModel):
    items: list[ClientInvoiceSummary]
    total: int
    limit: int
    offset: int


class ContractObligationSummary(BaseModel):
    obligation_type: str
    metric: str
    threshold: Decimal
    comparison: str
    window: str | None = None
    penalty_type: str
    penalty_value: Decimal


class SlaResultSummary(BaseModel):
    period_start: datetime
    period_end: datetime
    status: str
    measured_value: Decimal


class ClientContractSummary(BaseModel):
    contract_number: str
    contract_type: str
    effective_from: datetime
    effective_to: datetime | None = None
    status: str
    sla_status: str
    sla_violations: int


class ClientContractsResponse(BaseModel):
    items: list[ClientContractSummary]


class ClientContractDetails(BaseModel):
    contract_number: str
    contract_type: str
    effective_from: datetime
    effective_to: datetime | None = None
    status: str
    sla_status: str
    sla_violations: int
    penalties_total: Decimal
    obligations: list[ContractObligationSummary] = Field(default_factory=list)
    sla_results: list[SlaResultSummary] = Field(default_factory=list)


class PartnerDashboardResponse(BaseModel):
    active_contracts: int
    current_settlement_period: str | None = None
    upcoming_payout: Decimal | None = None
    sla_score: float | None = None
    sla: PortalSlaSummary


class PartnerContractSummary(BaseModel):
    contract_number: str
    contract_type: str
    effective_from: datetime
    effective_to: datetime | None = None
    status: str
    sla_status: str
    sla_violations: int


class PartnerContractsResponse(BaseModel):
    items: list[PartnerContractSummary]


class PartnerSettlementSummary(BaseModel):
    settlement_ref: str
    period_start: datetime
    period_end: datetime
    gross: Decimal
    fees: Decimal
    refunds: Decimal
    net_amount: Decimal
    status: str
    currency: str


class PartnerSettlementListResponse(BaseModel):
    items: list[PartnerSettlementSummary]


class PartnerSettlementItemSummary(BaseModel):
    source_type: str
    direction: str
    count: int
    amount: Decimal


class PartnerSettlementDetails(PartnerSettlementSummary):
    items_summary: list[PartnerSettlementItemSummary] = Field(default_factory=list)
    payout_status: str | None = None
