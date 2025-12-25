from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Literal


@dataclass(frozen=True)
class AccountingEntry:
    entry_id: str
    batch_id: str
    export_type: Literal["CHARGES", "SETTLEMENT"]

    tenant_id: int
    client_id: str
    currency: str

    posting_date: date
    period_from: date | None
    period_to: date | None

    document_type: str
    document_id: str
    document_number: str | None

    amount_gross: int
    vat_rate: str | None
    vat_amount: int | None
    amount_net: int | None

    counterparty_ref: str | None
    contract_ref: str | None
    cost_center: str | None

    source_type: str | None
    source_id: str | None
    external_ref: str | None
    provider: str | None

    meta: dict[str, Any] = field(default_factory=dict)


def _normalize_entry_value(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize_entry_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalize_entry_value(item) for item in value]
    return value


def entry_identity_payload(entry: AccountingEntry) -> dict[str, Any]:
    payload = {
        "export_type": entry.export_type,
        "tenant_id": entry.tenant_id,
        "client_id": entry.client_id,
        "currency": entry.currency,
        "posting_date": entry.posting_date,
        "period_from": entry.period_from,
        "period_to": entry.period_to,
        "document_type": entry.document_type,
        "document_id": entry.document_id,
        "document_number": entry.document_number,
        "amount_gross": entry.amount_gross,
        "vat_rate": entry.vat_rate,
        "vat_amount": entry.vat_amount,
        "amount_net": entry.amount_net,
        "counterparty_ref": entry.counterparty_ref,
        "contract_ref": entry.contract_ref,
        "cost_center": entry.cost_center,
        "source_type": entry.source_type,
        "source_id": entry.source_id,
        "external_ref": entry.external_ref,
        "provider": entry.provider,
        "meta": entry.meta,
    }
    return _normalize_entry_value(payload)


def build_entry_id(entry: AccountingEntry) -> str:
    payload = entry_identity_payload(entry)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def entry_to_dict(entry: AccountingEntry) -> dict[str, Any]:
    raw = asdict(entry)
    return _normalize_entry_value(raw)


__all__ = ["AccountingEntry", "build_entry_id", "entry_identity_payload", "entry_to_dict"]
