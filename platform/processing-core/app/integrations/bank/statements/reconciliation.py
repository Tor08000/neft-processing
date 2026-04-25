from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy.orm import Session

from neft_shared.logging_setup import get_logger

from app.models.client import Client
from app.models.integrations import (
    BankReconciliationDiff,
    BankReconciliationMatch,
    BankReconciliationRun,
    BankTransaction,
    ReconciliationDiffReason,
    ReconciliationDiffSource,
    ReconciliationMatchType,
    ReconciliationRunStatus,
)
from app.models.invoice import Invoice
from app.services.audit_service import AuditService, RequestContext

logger = get_logger(__name__)

AMOUNT_TOLERANCE_ABS = Decimal("1.00")
AMOUNT_TOLERANCE_PCT = Decimal("0.001")
DATE_TOLERANCE_DAYS = 3
PURPOSE_SIMILARITY_THRESHOLD = 0.85


@dataclass(frozen=True)
class NormalizedPurpose:
    text: str
    invoice_refs: list[str]
    inn_values: list[str]


def _normalize_purpose(text: str | None) -> NormalizedPurpose:
    if not text:
        return NormalizedPurpose(text="", invoice_refs=[], inn_values=[])
    normalized = text.upper()
    normalized = re.sub(r"[^A-Z0-9\-/ ]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    invoice_refs = re.findall(r"[A-Z]{2,}-\d{4}-\d+", normalized)
    inn_values = re.findall(r"\b\d{10,12}\b", normalized)
    return NormalizedPurpose(text=normalized, invoice_refs=invoice_refs, inn_values=inn_values)


def _amount_matches(expected: Decimal, actual: Decimal) -> bool:
    tolerance = max(AMOUNT_TOLERANCE_ABS, expected * AMOUNT_TOLERANCE_PCT)
    return abs(actual - expected) <= tolerance


def _invoice_date(invoice: Invoice) -> datetime:
    if invoice.issued_at:
        return _as_utc(invoice.issued_at)
    return datetime.combine(invoice.period_to, datetime.min.time(), tzinfo=timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _date_matches(invoice: Invoice, tx_date: datetime) -> bool:
    delta = abs(_invoice_date(invoice) - _as_utc(tx_date))
    return delta <= timedelta(days=DATE_TOLERANCE_DAYS)


def _similarity(purpose: str, invoice: Invoice, client: Client | None) -> float:
    candidate = invoice.number or invoice.id
    if client and client.name:
        candidate = f"{candidate} {client.name}"
    return SequenceMatcher(None, purpose, candidate.upper()).ratio()


def _load_client_for_invoice(db: Session, *, client_id: str | None) -> Client | None:
    if not client_id:
        return None
    try:
        return db.get(Client, UUID(str(client_id)))
    except (TypeError, ValueError, AttributeError):
        return None


def run_bank_reconciliation(db: Session, *, statement_id: str, actor: RequestContext) -> str:
    statement_txs = (
        db.query(BankTransaction)
        .filter(BankTransaction.statement_id == statement_id)
        .all()
    )
    run = BankReconciliationRun(
        statement_id=statement_id,
        status=ReconciliationRunStatus.STARTED,
        started_at=datetime.now(timezone.utc),
        config={
            "amount_tolerance_abs": str(AMOUNT_TOLERANCE_ABS),
            "amount_tolerance_pct": str(AMOUNT_TOLERANCE_PCT),
            "date_tolerance_days": DATE_TOLERANCE_DAYS,
        },
    )
    db.add(run)
    db.flush()

    invoices = db.query(Invoice).all()
    invoice_by_number = {invoice.number: invoice for invoice in invoices if invoice.number}
    client_cache: dict[str, Client | None] = {}

    for tx in statement_txs:
        purpose_norm = _normalize_purpose(tx.purpose or "")
        expected_invoice = None
        match_type = None

        if tx.external_ref and tx.external_ref in invoice_by_number:
            expected_invoice = invoice_by_number[tx.external_ref]
        elif purpose_norm.invoice_refs:
            for ref in purpose_norm.invoice_refs:
                if ref in invoice_by_number:
                    expected_invoice = invoice_by_number[ref]
                    break

        if expected_invoice:
            client = client_cache.setdefault(
                expected_invoice.client_id,
                _load_client_for_invoice(db, client_id=expected_invoice.client_id),
            )
            if purpose_norm.inn_values and client and client.inn and client.inn not in purpose_norm.inn_values:
                db.add(
                    BankReconciliationDiff(
                        run_id=run.id,
                        source=ReconciliationDiffSource.BANK,
                        tx_id=str(tx.id),
                        reason=ReconciliationDiffReason.COUNTERPARTY_MISMATCH,
                    )
                )
                continue
            expected_amount = Decimal(expected_invoice.total_with_tax) / Decimal(100)
            if not _amount_matches(expected_amount, Decimal(tx.amount)):
                db.add(
                    BankReconciliationDiff(
                        run_id=run.id,
                        source=ReconciliationDiffSource.BANK,
                        tx_id=str(tx.id),
                        reason=ReconciliationDiffReason.AMOUNT_MISMATCH,
                    )
                )
                continue
            if not _date_matches(expected_invoice, tx.date):
                db.add(
                    BankReconciliationDiff(
                        run_id=run.id,
                        source=ReconciliationDiffSource.BANK,
                        tx_id=str(tx.id),
                        reason=ReconciliationDiffReason.DATE_MISMATCH,
                    )
                )
                continue
            match_type = ReconciliationMatchType.EXACT_REF
        else:
            candidates: list[Invoice] = []
            for invoice in invoices:
                client = client_cache.setdefault(
                    invoice.client_id,
                    _load_client_for_invoice(db, client_id=invoice.client_id),
                )
                if purpose_norm.inn_values and client and client.inn and client.inn not in purpose_norm.inn_values:
                    continue
                expected_amount = Decimal(invoice.total_with_tax) / Decimal(100)
                if not _amount_matches(expected_amount, Decimal(tx.amount)):
                    continue
                if not _date_matches(invoice, tx.date):
                    continue
                candidates.append(invoice)

            if not candidates:
                fuzzy_candidates: list[tuple[Invoice, float]] = []
                for invoice in invoices:
                    score = _similarity(purpose_norm.text, invoice, client_cache.get(invoice.client_id))
                    if score >= PURPOSE_SIMILARITY_THRESHOLD:
                        expected_amount = Decimal(invoice.total_with_tax) / Decimal(100)
                        if not _amount_matches(expected_amount, Decimal(tx.amount)):
                            continue
                        if not _date_matches(invoice, tx.date):
                            continue
                        fuzzy_candidates.append((invoice, score))
                if len(fuzzy_candidates) == 1:
                    expected_invoice = fuzzy_candidates[0][0]
                    match_type = ReconciliationMatchType.FUZZY
                elif len(fuzzy_candidates) > 1:
                    db.add(
                        BankReconciliationDiff(
                            run_id=run.id,
                            source=ReconciliationDiffSource.BANK,
                            tx_id=str(tx.id),
                            reason=ReconciliationDiffReason.DUPLICATE_MATCH,
                        )
                    )
                    continue
            else:
                if len(candidates) > 1:
                    db.add(
                        BankReconciliationDiff(
                            run_id=run.id,
                            source=ReconciliationDiffSource.BANK,
                            tx_id=str(tx.id),
                            reason=ReconciliationDiffReason.DUPLICATE_MATCH,
                        )
                    )
                    continue
                expected_invoice = candidates[0]
                match_type = ReconciliationMatchType.INN_AMOUNT_DATE

        if expected_invoice and match_type:
            db.add(
                BankReconciliationMatch(
                    run_id=run.id,
                    bank_tx_id=tx.id,
                    invoice_id=expected_invoice.id,
                    match_type=match_type,
                    score=Decimal("1.0") if match_type == ReconciliationMatchType.EXACT_REF else Decimal("0.9"),
                )
            )
        else:
            db.add(
                BankReconciliationDiff(
                    run_id=run.id,
                    source=ReconciliationDiffSource.BANK,
                    tx_id=str(tx.id),
                    reason=ReconciliationDiffReason.NOT_FOUND,
                )
            )

    run.status = ReconciliationRunStatus.COMPLETED
    run.finished_at = datetime.now(timezone.utc)

    AuditService(db).audit(
        event_type="RECONCILIATION_RUN_COMPLETED",
        entity_type="bank_reconciliation_run",
        entity_id=str(run.id),
        action="completed",
        after={"run_id": str(run.id), "statement_id": statement_id},
        request_ctx=actor,
    )

    logger.info("bank_reconciliation_completed", extra={"run_id": str(run.id)})
    return str(run.id)


__all__ = ["run_bank_reconciliation"]
