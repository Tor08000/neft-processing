from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.fuel import FuelTransactionStatus
from app.models.internal_ledger import InternalLedgerEntry
from app.models.ledger_entry import LedgerDirection
from app.schemas.fuel import DeclineCode
from app.services.audit_service import AuditService, RequestContext
from app.services.finance_invariants import rules as invariants_rules
from app.services.fuel import events, repository
from app.services.internal_ledger import InternalLedgerService


@dataclass(frozen=True)
class FuelSettlementResult:
    transaction_id: str
    status: FuelTransactionStatus
    ledger_transaction_id: str | None


class FuelSettlementError(Exception):
    def __init__(self, decline_code: DeclineCode, message: str):
        super().__init__(message)
        self.decline_code = decline_code
        self.message = message


def _validate_internal_ledger(db: Session, ledger_transaction_id: str, request_ctx: RequestContext | None) -> None:
    entries = (
        db.query(InternalLedgerEntry)
        .filter(InternalLedgerEntry.ledger_transaction_id == ledger_transaction_id)
        .all()
    )
    lines = [
        {
            "direction": LedgerDirection(entry.direction.value),
            "amount": entry.amount,
            "currency": entry.currency,
        }
        for entry in entries
    ]
    violations = invariants_rules.validate_ledger_lines(lines)
    if violations:
        AuditService(db).audit(
            event_type="FINANCIAL_INVARIANT_VIOLATION",
            entity_type="fuel_transaction",
            entity_id=ledger_transaction_id,
            action="VALIDATE",
            after={"violations": [vars(item) for item in violations]},
            request_ctx=request_ctx,
        )
        raise FuelSettlementError(DeclineCode.INTERNAL_ERROR, "Ledger invariant violated")


def settle_fuel_tx(
    db: Session,
    *,
    transaction_id: str,
    external_settlement_ref: str | None = None,
    request_ctx: RequestContext | None = None,
) -> FuelSettlementResult:
    transaction = repository.get_fuel_transaction(db, transaction_id=transaction_id)
    if transaction is None:
        raise FuelSettlementError(DeclineCode.INVALID_REQUEST, "Fuel transaction not found")
    if transaction.status == FuelTransactionStatus.SETTLED:
        if external_settlement_ref and transaction.external_settlement_ref not in {None, external_settlement_ref}:
            raise FuelSettlementError(DeclineCode.INVALID_REQUEST, "Settlement reference mismatch")
        return FuelSettlementResult(
            transaction_id=str(transaction.id),
            status=transaction.status,
            ledger_transaction_id=str(transaction.ledger_transaction_id) if transaction.ledger_transaction_id else None,
        )
    if transaction.status == FuelTransactionStatus.REVERSED:
        raise FuelSettlementError(DeclineCode.INVALID_REQUEST, "Transaction already reversed")
    if transaction.status == FuelTransactionStatus.REVIEW_REQUIRED:
        raise FuelSettlementError(DeclineCode.RISK_REVIEW_REQUIRED, "Transaction requires review approval")
    if transaction.status != FuelTransactionStatus.AUTHORIZED:
        raise FuelSettlementError(DeclineCode.INVALID_REQUEST, "Invalid transaction status")

    ledger_service = InternalLedgerService(db)
    try:
        ledger_tx = ledger_service.post_fuel_settlement(
            tenant_id=transaction.tenant_id,
            fuel_transaction_id=str(transaction.id),
            client_id=transaction.client_id,
            amount=transaction.amount_total_minor,
            currency=transaction.currency,
            posted_at=transaction.occurred_at,
        )
    except Exception as exc:  # noqa: BLE001
        raise FuelSettlementError(DeclineCode.INTERNAL_ERROR, str(exc)) from exc

    transaction.status = FuelTransactionStatus.SETTLED
    transaction.ledger_transaction_id = ledger_tx.id
    transaction.external_settlement_ref = external_settlement_ref
    db.commit()
    db.refresh(transaction)

    _validate_internal_ledger(db, str(ledger_tx.id), request_ctx)
    events.audit_event(
        db,
        event_type=events.FUEL_EVENT_SETTLED,
        entity_id=str(transaction.id),
        payload={
            "status": transaction.status.value,
            "ledger_transaction_id": str(ledger_tx.id),
        },
        request_ctx=request_ctx,
    )
    return FuelSettlementResult(
        transaction_id=str(transaction.id),
        status=transaction.status,
        ledger_transaction_id=str(ledger_tx.id),
    )


def reverse_fuel_tx(
    db: Session,
    *,
    transaction_id: str,
    external_ref: str | None = None,
    request_ctx: RequestContext | None = None,
) -> FuelSettlementResult:
    transaction = repository.get_fuel_transaction(db, transaction_id=transaction_id)
    if transaction is None:
        raise FuelSettlementError(DeclineCode.INVALID_REQUEST, "Fuel transaction not found")
    if transaction.status == FuelTransactionStatus.REVERSED:
        if external_ref and transaction.external_reverse_ref not in {None, external_ref}:
            raise FuelSettlementError(DeclineCode.INVALID_REQUEST, "Reversal reference mismatch")
        return FuelSettlementResult(
            transaction_id=str(transaction.id),
            status=transaction.status,
            ledger_transaction_id=str(transaction.ledger_transaction_id) if transaction.ledger_transaction_id else None,
        )
    if transaction.status == FuelTransactionStatus.REVIEW_REQUIRED:
        raise FuelSettlementError(DeclineCode.RISK_REVIEW_REQUIRED, "Transaction requires review approval")

    ledger_service = InternalLedgerService(db)
    try:
        ledger_tx = ledger_service.post_fuel_reversal(
            tenant_id=transaction.tenant_id,
            fuel_transaction_id=str(transaction.id),
            client_id=transaction.client_id,
            amount=transaction.amount_total_minor,
            currency=transaction.currency,
            posted_at=transaction.occurred_at,
        )
    except Exception as exc:  # noqa: BLE001
        raise FuelSettlementError(DeclineCode.INTERNAL_ERROR, str(exc)) from exc

    transaction.status = FuelTransactionStatus.REVERSED
    transaction.ledger_transaction_id = ledger_tx.id
    transaction.external_reverse_ref = external_ref
    db.commit()
    db.refresh(transaction)

    _validate_internal_ledger(db, str(ledger_tx.id), request_ctx)
    events.audit_event(
        db,
        event_type=events.FUEL_EVENT_REVERSED,
        entity_id=str(transaction.id),
        payload={
            "status": transaction.status.value,
            "ledger_transaction_id": str(ledger_tx.id),
        },
        request_ctx=request_ctx,
    )
    return FuelSettlementResult(
        transaction_id=str(transaction.id),
        status=transaction.status,
        ledger_transaction_id=str(ledger_tx.id),
    )


__all__ = ["FuelSettlementError", "FuelSettlementResult", "reverse_fuel_tx", "settle_fuel_tx"]
