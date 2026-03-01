from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from decimal import Decimal
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import settings
from app.models.billing_period import BillingPeriodType
from app.models.fuel import FuelTransactionStatus
from app.domains.ledger.enums import EntryType, LineDirection
from app.domains.ledger.errors import IdempotencyMismatch, InvariantViolation
from app.domains.ledger.models import LedgerEntryV1
from app.domains.ledger.schemas import LedgerLineIn, LedgerPostRequest
from app.domains.ledger.service import InternalLedgerService as InternalLedgerV1Service
from app.models.internal_ledger import InternalLedgerEntry
from app.models.ledger_entry import LedgerDirection
from app.models.money_flow_v3 import MoneyFlowLinkNodeType, MoneyFlowLinkType
from app.schemas.fuel import DeclineCode
from app.services.audit_service import AuditService, RequestContext
from app.services.billing_periods import BillingPeriodService, period_bounds_for_dates
from app.services.finance_invariants import rules as invariants_rules
from app.services.fuel import events, repository
from app.services.logistics import fuel_linker
from app.services.internal_ledger import InternalLedgerService
from app.services.money_flow.graph import MoneyFlowGraphBuilder, ensure_money_flow_links
from app.services.vehicle_mileage import apply_fuel_transaction_mileage


@dataclass(frozen=True)
class FuelSettlementResult:
    transaction_id: str
    status: FuelTransactionStatus
    ledger_transaction_id: str | None


class FuelSettlementError(Exception):
    def __init__(self, decline_code: DeclineCode, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.decline_code = decline_code
        self.message = message
        self.status_code = status_code


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




def _minor_to_decimal(value: int) -> Decimal:
    return (Decimal(value) / Decimal("100")).quantize(Decimal("0.01"))


def _resolve_owner_uuid(value: str):
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return uuid5(UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8"), str(value))


def _post_capture_ledger_v1(db: Session, *, transaction) -> str:
    fee_minor_raw = (transaction.meta or {}).get("platform_fee_minor", 0)
    try:
        platform_fee_minor = int(fee_minor_raw or 0)
    except (TypeError, ValueError) as exc:
        raise FuelSettlementError(DeclineCode.INVALID_REQUEST, "Invalid platform_fee_minor", status_code=409) from exc
    gross_minor = int(transaction.amount_total_minor)
    partner_net_minor = gross_minor - platform_fee_minor
    if platform_fee_minor < 0:
        raise FuelSettlementError(DeclineCode.INVALID_REQUEST, "platform_fee must be non-negative", status_code=409)
    if partner_net_minor < 0:
        raise FuelSettlementError(DeclineCode.INVALID_REQUEST, "platform_fee exceeds gross", status_code=409)
    if gross_minor != partner_net_minor + platform_fee_minor:
        raise FuelSettlementError(DeclineCode.INTERNAL_ERROR, "capture amount split invariant violated", status_code=409)

    partner_id = str((transaction.meta or {}).get("partner_id") or transaction.network_id)
    dims = {
        "client_id": str(transaction.client_id),
        "partner_id": partner_id,
        "fuel_tx_id": str(transaction.id),
        "station_id": str(transaction.station_id),
    }
    merchant_id = (transaction.meta or {}).get("merchant_id") or transaction.merchant_key
    contract_id = (transaction.meta or {}).get("contract_id")
    invoice_id = (transaction.meta or {}).get("invoice_id")
    if merchant_id:
        dims["merchant_id"] = str(merchant_id)
    if contract_id:
        dims["contract_id"] = str(contract_id)
    if invoice_id:
        dims["invoice_id"] = str(invoice_id)

    lines = [
        LedgerLineIn(
            account_code="CLIENT_AR",
            owner_id=_resolve_owner_uuid(str(transaction.client_id)),
            direction=LineDirection.DEBIT,
            amount=_minor_to_decimal(gross_minor),
            currency=transaction.currency,
            memo=f"fuel_tx_id={transaction.id}",
        ),
        LedgerLineIn(
            account_code="PARTNER_AP",
            owner_id=_resolve_owner_uuid(partner_id),
            direction=LineDirection.CREDIT,
            amount=_minor_to_decimal(partner_net_minor),
            currency=transaction.currency,
            memo=f"fuel_tx_id={transaction.id}",
        ),
    ]
    if platform_fee_minor > 0:
        lines.append(
            LedgerLineIn(
                account_code="PLATFORM_FEES_REVENUE",
                owner_id=None,
                direction=LineDirection.CREDIT,
                amount=_minor_to_decimal(platform_fee_minor),
                currency=transaction.currency,
                memo=f"fuel_tx_id={transaction.id}",
            )
        )

    try:
        entry = InternalLedgerV1Service(db).post_entry(
            LedgerPostRequest(
                entry_type=EntryType.CAPTURE,
                idempotency_key=f"fuel:capture:{transaction.id}",
                correlation_id=str(transaction.id),
                narrative=(
                    f"Fuel CAPTURE tx={transaction.id} client={transaction.client_id} "
                    f"partner={partner_id} gross={_minor_to_decimal(gross_minor)} "
                    f"fee={_minor_to_decimal(platform_fee_minor)} net={_minor_to_decimal(partner_net_minor)}"
                ),
                dimensions=dims,
                lines=lines,
            )
        )
    except IdempotencyMismatch as exc:
        raise FuelSettlementError(DeclineCode.INVALID_REQUEST, "ledger idempotency mismatch", status_code=409) from exc
    except InvariantViolation as exc:
        raise FuelSettlementError(DeclineCode.INVALID_REQUEST, str(exc), status_code=409) from exc
    except Exception as exc:  # noqa: BLE001
        raise FuelSettlementError(DeclineCode.INTERNAL_ERROR, "ledger posting failed", status_code=500) from exc

    return str(entry.entry_id)

def _resolve_billing_period_id(db: Session, *, occurred_at) -> str:
    tz = ZoneInfo(settings.NEFT_BILLING_TZ)
    timestamp = occurred_at
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    local_date = timestamp.astimezone(tz).date()
    period_start, period_end = period_bounds_for_dates(date_from=local_date, date_to=local_date, tz=settings.NEFT_BILLING_TZ)
    period = BillingPeriodService(db).get_or_create(
        period_type=BillingPeriodType.DAILY,
        start_at=period_start,
        end_at=period_end,
        tz=settings.NEFT_BILLING_TZ,
    )
    return str(period.id)


def _write_money_flow_links(db: Session, *, transaction, ledger_transaction_id: str | None) -> None:
    billing_period_id = _resolve_billing_period_id(db, occurred_at=transaction.occurred_at)
    builder = MoneyFlowGraphBuilder(tenant_id=transaction.tenant_id, client_id=transaction.client_id)
    if ledger_transaction_id:
        builder.add_link(
            src_type=MoneyFlowLinkNodeType.FUEL_TX,
            src_id=str(transaction.id),
            link_type=MoneyFlowLinkType.POSTS,
            dst_type=MoneyFlowLinkNodeType.LEDGER_TX,
            dst_id=str(ledger_transaction_id),
            meta={"status": transaction.status.value},
        )
    builder.add_link(
        src_type=MoneyFlowLinkNodeType.FUEL_TX,
        src_id=str(transaction.id),
        link_type=MoneyFlowLinkType.RELATES,
        dst_type=MoneyFlowLinkNodeType.BILLING_PERIOD,
        dst_id=billing_period_id,
        meta={"occurred_at": transaction.occurred_at.isoformat()},
    )
    ensure_money_flow_links(
        db,
        tenant_id=transaction.tenant_id,
        client_id=transaction.client_id,
        links=builder.build(),
    )


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
        capture_entry = (
            db.query(LedgerEntryV1)
            .filter(LedgerEntryV1.idempotency_key == f"fuel:capture:{transaction.id}")
            .one_or_none()
        )
        return FuelSettlementResult(
            transaction_id=str(transaction.id),
            status=transaction.status,
            ledger_transaction_id=str(capture_entry.id) if capture_entry else (str(transaction.ledger_transaction_id) if transaction.ledger_transaction_id else None),
        )
    if transaction.status == FuelTransactionStatus.REVERSED:
        raise FuelSettlementError(DeclineCode.INVALID_REQUEST, "Transaction already reversed")
    if transaction.status == FuelTransactionStatus.REVIEW_REQUIRED:
        raise FuelSettlementError(DeclineCode.RISK_REVIEW_REQUIRED, "Transaction requires review approval")
    if transaction.status != FuelTransactionStatus.AUTHORIZED:
        raise FuelSettlementError(DeclineCode.INVALID_REQUEST, "Invalid transaction status")

    ledger_v1_entry_id = _post_capture_ledger_v1(db, transaction=transaction)

    ledger_service = InternalLedgerService(db)
    try:
        legacy_ledger_tx = ledger_service.post_fuel_settlement(
            tenant_id=transaction.tenant_id,
            fuel_transaction_id=str(transaction.id),
            client_id=transaction.client_id,
            amount=transaction.amount_total_minor,
            currency=transaction.currency,
            posted_at=transaction.occurred_at,
        )
    except Exception as exc:  # noqa: BLE001
        raise FuelSettlementError(DeclineCode.INTERNAL_ERROR, str(exc), status_code=500) from exc

    transaction.status = FuelTransactionStatus.SETTLED
    transaction.ledger_transaction_id = legacy_ledger_tx.id
    transaction.external_settlement_ref = external_settlement_ref
    _write_money_flow_links(db, transaction=transaction, ledger_transaction_id=str(legacy_ledger_tx.id))
    apply_fuel_transaction_mileage(db, transaction=transaction)
    db.commit()
    db.refresh(transaction)

    _validate_internal_ledger(db, str(legacy_ledger_tx.id), request_ctx)
    events.audit_event(
        db,
        event_type=events.FUEL_EVENT_SETTLED,
        entity_id=str(transaction.id),
        payload={
            "status": transaction.status.value,
            "ledger_transaction_id": str(legacy_ledger_tx.id),
            "ledger_v1_entry_id": ledger_v1_entry_id,
        },
        request_ctx=request_ctx,
    )
    fuel_linker.auto_link_fuel_tx(db, transaction=transaction, request_ctx=request_ctx)
    return FuelSettlementResult(
        transaction_id=str(transaction.id),
        status=transaction.status,
        ledger_transaction_id=ledger_v1_entry_id,
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
    _write_money_flow_links(db, transaction=transaction, ledger_transaction_id=str(ledger_tx.id))
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
