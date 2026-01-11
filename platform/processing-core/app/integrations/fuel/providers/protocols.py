from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class NotSupportedError(RuntimeError):
    pass


@dataclass(frozen=True)
class IngestBatchRequest:
    provider_code: str
    source: str
    batch_key: str
    payload_ref: bytes | str
    received_at: datetime


@dataclass(frozen=True)
class AuthorizeRequest:
    client_id: str | None
    card_id: str | None
    vehicle_id: str | None
    merchant_id: str | None
    station_id: str | None
    amount: str
    currency: str
    product_code: str | None
    timestamp: datetime
    offline_mode_allowed: bool
    context: dict | None
    provider_tx_id: str | None = None
    card_token: str | None = None


@dataclass(frozen=True)
class SettlementExportRequest:
    period: str
    client_id: str | None = None
    partner_id: str | None = None
    format: str = "CSV"
    include_details: bool = True


@dataclass(frozen=True)
class IngestResult:
    batch_id: str
    records_total: int
    records_applied: int
    records_duplicate: int
    records_failed: int
    status: str
    error: str | None = None


@dataclass(frozen=True)
class AuthorizeResult:
    decision: str
    reason_code: str
    auth_code: str | None
    offline_profile: str | None


@dataclass(frozen=True)
class SettlementResult:
    payload_ref: str
    format: str
    records_total: int


@dataclass(frozen=True)
class ReconciliationResult:
    status: str
    message: str | None = None


class FuelProvider(Protocol):
    code: str

    def ingest_batch(self, db, request: IngestBatchRequest) -> IngestResult: ...

    def authorize(self, db, request: AuthorizeRequest) -> AuthorizeResult: ...

    def settlement_export(self, db, request: SettlementExportRequest) -> SettlementResult: ...

    def reconciliation_import(self, db, payload_ref: str) -> ReconciliationResult: ...
