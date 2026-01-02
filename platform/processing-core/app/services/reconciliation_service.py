from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from neft_shared.logging_setup import get_logger

from app.models.audit_log import ActorType
from app.models.internal_ledger import (
    InternalLedgerAccount,
    InternalLedgerAccountType,
    InternalLedgerEntry,
    InternalLedgerEntryDirection,
    InternalLedgerTransactionType,
)
from app.models.reconciliation import (
    ExternalStatement,
    ReconciliationDiscrepancy,
    ReconciliationDiscrepancyStatus,
    ReconciliationDiscrepancyType,
    ReconciliationLink,
    ReconciliationLinkDirection,
    ReconciliationLinkStatus,
    ReconciliationRun,
    ReconciliationRunStatus,
    ReconciliationScope,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.internal_ledger import InternalLedgerLine, InternalLedgerService
from app.services.reconciliation_metrics import metrics


logger = get_logger(__name__)

EPSILON = Decimal("0.0001")
MATCH_WINDOW = timedelta(hours=72)


def _safe_decimal(value: object | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _delta(internal_amount: Decimal | None, external_amount: Decimal | None) -> Decimal | None:
    if internal_amount is None or external_amount is None:
        return None
    return external_amount - internal_amount


def _audit_actor(created_by: str | None) -> RequestContext:
    if created_by:
        return RequestContext(actor_type=ActorType.USER, actor_id=created_by)
    return RequestContext(actor_type=ActorType.SYSTEM)


def _canonical_json(data: object) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_payload(data: object) -> str:
    return hashlib.sha256(_canonical_json(data).encode("utf-8")).hexdigest()


def _parse_line_timestamp(line: dict[str, object]) -> datetime | None:
    for key in ("timestamp", "at", "created_at", "date"):
        value = line.get(key)
        if not value:
            continue
        if isinstance(value, datetime):
            return value
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def _parse_line_amount(line: dict[str, object]) -> Decimal | None:
    value = line.get("amount")
    if value is None:
        return None
    amount = Decimal(str(value))
    if amount < 0:
        return abs(amount)
    return amount


def _parse_line_direction(line: dict[str, object], amount: Decimal | None) -> ReconciliationLinkDirection | None:
    raw = line.get("direction") or line.get("type")
    if raw:
        raw_value = str(raw).upper()
        if raw_value == ReconciliationLinkDirection.IN.value:
            return ReconciliationLinkDirection.IN
        if raw_value == ReconciliationLinkDirection.OUT.value:
            return ReconciliationLinkDirection.OUT
    raw_amount = line.get("amount")
    if raw_amount is not None:
        try:
            raw_decimal = Decimal(str(raw_amount))
        except Exception:  # noqa: BLE001
            raw_decimal = None
        if raw_decimal is not None:
            if raw_decimal < 0:
                return ReconciliationLinkDirection.OUT
            if raw_decimal > 0:
                return ReconciliationLinkDirection.IN
    if amount is None:
        return None
    if amount < 0:
        return ReconciliationLinkDirection.OUT
    if amount > 0:
        return ReconciliationLinkDirection.IN
    return None


def _compute_account_balances(
    db: Session,
    *,
    period_start: datetime,
    period_end: datetime,
) -> list[tuple[str, str, Decimal, list[InternalLedgerEntry]]]:
    debit_sum = func.coalesce(
        func.sum(
            case(
                (InternalLedgerEntry.direction == InternalLedgerEntryDirection.DEBIT, InternalLedgerEntry.amount),
                else_=0,
            )
        ),
        0,
    )
    credit_sum = func.coalesce(
        func.sum(
            case(
                (InternalLedgerEntry.direction == InternalLedgerEntryDirection.CREDIT, InternalLedgerEntry.amount),
                else_=0,
            )
        ),
        0,
    )

    rows = (
        db.query(
            InternalLedgerEntry.account_id,
            InternalLedgerEntry.currency,
            debit_sum.label("debit_sum"),
            credit_sum.label("credit_sum"),
        )
        .filter(InternalLedgerEntry.created_at >= period_start)
        .filter(InternalLedgerEntry.created_at <= period_end)
        .group_by(InternalLedgerEntry.account_id, InternalLedgerEntry.currency)
        .all()
    )

    balances: list[tuple[str, str, Decimal, list[InternalLedgerEntry]]] = []
    for account_id, currency, debit_total, credit_total in rows:
        entries = (
            db.query(InternalLedgerEntry)
            .filter(InternalLedgerEntry.account_id == account_id)
            .filter(InternalLedgerEntry.currency == currency)
            .filter(InternalLedgerEntry.created_at >= period_start)
            .filter(InternalLedgerEntry.created_at <= period_end)
            .order_by(InternalLedgerEntry.created_at.asc(), InternalLedgerEntry.id.asc())
            .all()
        )
        balance = Decimal(int(debit_total)) - Decimal(int(credit_total))
        balances.append((str(account_id), currency, balance, entries))
    return balances


def run_internal_reconciliation(
    db: Session,
    *,
    period_start: datetime,
    period_end: datetime,
    created_by: str | None = None,
) -> str:
    run = ReconciliationRun(
        scope=ReconciliationScope.INTERNAL,
        provider=None,
        period_start=period_start,
        period_end=period_end,
        status=ReconciliationRunStatus.STARTED,
        created_by_user_id=created_by,
    )
    db.add(run)
    db.flush()
    metrics.mark_run(scope=run.scope.value, status=run.status.value)
    logger.info("reconciliation run started", extra={"run_id": str(run.id), "scope": run.scope.value})

    discrepancies_created = 0
    total_delta_abs = Decimal("0")
    try:
        balances = _compute_account_balances(db, period_start=period_start, period_end=period_end)
        for account_id, currency, balance, entries in balances:
            expected_balance = None
            for entry in entries:
                if isinstance(entry.meta, dict) and "balance_after" in entry.meta:
                    expected_balance = _safe_decimal(entry.meta.get("balance_after"))
            if expected_balance is None:
                continue
            delta = _delta(balance, expected_balance)
            if delta is None or abs(delta) <= EPSILON:
                continue
            discrepancy = ReconciliationDiscrepancy(
                run_id=run.id,
                ledger_account_id=account_id,
                currency=currency,
                discrepancy_type=ReconciliationDiscrepancyType.BALANCE_MISMATCH,
                internal_amount=balance,
                external_amount=expected_balance,
                delta=delta,
                details={"source": "balance_after"},
                status=ReconciliationDiscrepancyStatus.OPEN,
            )
            db.add(discrepancy)
            discrepancies_created += 1
            total_delta_abs += abs(delta)
            metrics.mark_discrepancy(discrepancy.discrepancy_type.value, discrepancy.status.value)
            metrics.observe_delta_abs(abs(delta))

        summary = {
            "accounts_checked": len(balances),
            "mismatches_found": discrepancies_created,
            "total_delta_abs": str(total_delta_abs),
        }
        run.summary = summary
        run.status = ReconciliationRunStatus.COMPLETED
        audit = AuditService(db).audit(
            event_type="RECONCILIATION_RUN_COMPLETED",
            entity_type="reconciliation_run",
            entity_id=str(run.id),
            action="completed",
            after={"run_id": str(run.id), "summary": summary},
            request_ctx=_audit_actor(created_by),
        )
        run.audit_event_id = audit.id
        db.flush()
        metrics.mark_run(scope=run.scope.value, status=run.status.value)
        logger.info(
            "reconciliation run completed",
            extra={"run_id": str(run.id), "scope": run.scope.value, "mismatches": discrepancies_created},
        )
        return str(run.id)
    except Exception:  # noqa: BLE001
        run.status = ReconciliationRunStatus.FAILED
        db.flush()
        metrics.mark_run(scope=run.scope.value, status=run.status.value)
        logger.exception("reconciliation run failed", extra={"run_id": str(run.id), "scope": run.scope.value})
        raise


def upload_external_statement(
    db: Session,
    *,
    provider: str,
    period_start: datetime,
    period_end: datetime,
    currency: str,
    total_in: Decimal | None,
    total_out: Decimal | None,
    closing_balance: Decimal | None,
    lines: list[dict[str, object]] | None,
    created_by: str | None = None,
) -> ExternalStatement:
    payload = {
        "provider": provider,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "currency": currency,
        "total_in": str(total_in) if total_in is not None else None,
        "total_out": str(total_out) if total_out is not None else None,
        "closing_balance": str(closing_balance) if closing_balance is not None else None,
        "lines": lines or [],
    }
    source_hash = _hash_payload(payload)
    statement = ExternalStatement(
        provider=provider,
        period_start=period_start,
        period_end=period_end,
        currency=currency,
        total_in=total_in,
        total_out=total_out,
        closing_balance=closing_balance,
        lines=lines,
        source_hash=source_hash,
    )
    try:
        db.add(statement)
        db.flush()
    except IntegrityError as exc:
        raise ValueError("statement_already_uploaded") from exc

    audit = AuditService(db).audit(
        event_type="EXTERNAL_STATEMENT_UPLOADED",
        entity_type="external_statement",
        entity_id=str(statement.id),
        action="created",
        after={"statement_id": str(statement.id), "provider": provider, "source_hash": source_hash},
        request_ctx=_audit_actor(created_by),
    )
    statement.audit_event_id = audit.id
    db.flush()
    logger.info(
        "external statement uploaded",
        extra={"statement_id": str(statement.id), "provider": provider},
    )
    if os.getenv("AUTO_RECONCILE_ON_STATEMENT_UPLOAD", "false").lower() in {"1", "true", "yes"}:
        run_external_reconciliation(db, statement_id=str(statement.id), created_by=created_by)
    return statement


def run_external_reconciliation(
    db: Session,
    *,
    statement_id: str,
    created_by: str | None = None,
) -> str:
    statement = db.query(ExternalStatement).filter(ExternalStatement.id == statement_id).one_or_none()
    if statement is None:
        raise ValueError("external_statement_not_found")

    run = ReconciliationRun(
        scope=ReconciliationScope.EXTERNAL,
        provider=statement.provider,
        period_start=statement.period_start,
        period_end=statement.period_end,
        status=ReconciliationRunStatus.STARTED,
        created_by_user_id=created_by,
    )
    db.add(run)
    db.flush()
    metrics.mark_run(scope=run.scope.value, status=run.status.value)
    logger.info("external reconciliation started", extra={"run_id": str(run.id), "statement_id": statement_id})

    discrepancies_created = 0
    total_delta_abs = Decimal("0")
    links_matched = 0
    links_mismatched = 0
    links_pending = 0
    try:
        debit_sum = func.coalesce(
            func.sum(
                case(
                    (InternalLedgerEntry.direction == InternalLedgerEntryDirection.DEBIT, InternalLedgerEntry.amount),
                    else_=0,
                )
            ),
            0,
        )
        credit_sum = func.coalesce(
            func.sum(
                case(
                    (InternalLedgerEntry.direction == InternalLedgerEntryDirection.CREDIT, InternalLedgerEntry.amount),
                    else_=0,
                )
            ),
            0,
        )
        internal_totals = (
            db.query(debit_sum.label("debit_sum"), credit_sum.label("credit_sum"))
            .filter(InternalLedgerEntry.currency == statement.currency)
            .filter(InternalLedgerEntry.created_at >= statement.period_start)
            .filter(InternalLedgerEntry.created_at <= statement.period_end)
            .one()
        )
        internal_in = Decimal(int(internal_totals.debit_sum or 0))
        internal_out = Decimal(int(internal_totals.credit_sum or 0))
        internal_balance = internal_in - internal_out

        def _maybe_add_balance_discrepancy(kind: str, internal_amount: Decimal, external_amount: Decimal) -> None:
            nonlocal discrepancies_created, total_delta_abs
            delta = _delta(internal_amount, external_amount)
            if delta is None or abs(delta) <= EPSILON:
                return
            discrepancy = ReconciliationDiscrepancy(
                run_id=run.id,
                ledger_account_id=None,
                currency=statement.currency,
                discrepancy_type=ReconciliationDiscrepancyType.BALANCE_MISMATCH,
                internal_amount=internal_amount,
                external_amount=external_amount,
                delta=delta,
                details={"kind": kind, "statement_id": str(statement.id)},
                status=ReconciliationDiscrepancyStatus.OPEN,
            )
            db.add(discrepancy)
            discrepancies_created += 1
            total_delta_abs += abs(delta)
            metrics.mark_discrepancy(discrepancy.discrepancy_type.value, discrepancy.status.value)
            metrics.observe_delta_abs(abs(delta))

        if statement.total_in is not None:
            _maybe_add_balance_discrepancy("total_in", internal_in, Decimal(statement.total_in))
        if statement.total_out is not None:
            _maybe_add_balance_discrepancy("total_out", internal_out, Decimal(statement.total_out))
        if statement.closing_balance is not None:
            _maybe_add_balance_discrepancy("closing_balance", internal_balance, Decimal(statement.closing_balance))

        line_payloads: list[dict[str, object]] = []
        if isinstance(statement.lines, list):
            for line in statement.lines:
                if not isinstance(line, dict):
                    continue
                line_payloads.append(line)

        pending_links = (
            db.query(ReconciliationLink)
            .filter(ReconciliationLink.provider == statement.provider)
            .filter(ReconciliationLink.currency == statement.currency)
            .filter(ReconciliationLink.status == ReconciliationLinkStatus.PENDING)
            .filter(ReconciliationLink.expected_at >= statement.period_start)
            .filter(ReconciliationLink.expected_at <= statement.period_end)
            .all()
        )
        links_by_match_key = {
            link.match_key: link for link in pending_links if link.match_key is not None
        }
        matched_link_ids: set[str] = set()

        for line in line_payloads:
            line_ref = line.get("ref") or line.get("id") or line.get("match_key")
            line_key = str(line_ref) if line_ref else None
            line_amount = _parse_line_amount(line)
            direction = _parse_line_direction(line, line_amount)
            timestamp = _parse_line_timestamp(line)

            link = None
            if line_key and line_key in links_by_match_key:
                link = links_by_match_key[line_key]
                if str(link.id) in matched_link_ids:
                    link = None
            else:
                for candidate in pending_links:
                    if str(candidate.id) in matched_link_ids:
                        continue
                    if line_amount is None or direction is None:
                        continue
                    if Decimal(candidate.expected_amount) != line_amount:
                        continue
                    if candidate.direction != direction:
                        continue
                    if timestamp:
                        delta = abs(candidate.expected_at - timestamp)
                        if delta > MATCH_WINDOW:
                            continue
                    link = candidate
                    break

            if link is None:
                if line_key:
                    discrepancy = ReconciliationDiscrepancy(
                        run_id=run.id,
                        ledger_account_id=None,
                        currency=statement.currency,
                        discrepancy_type=ReconciliationDiscrepancyType.UNMATCHED_EXTERNAL,
                        internal_amount=None,
                        external_amount=None,
                        delta=None,
                        details={"ref": line_key, "statement_id": str(statement.id)},
                        status=ReconciliationDiscrepancyStatus.OPEN,
                    )
                    db.add(discrepancy)
                    discrepancies_created += 1
                    metrics.mark_discrepancy(discrepancy.discrepancy_type.value, discrepancy.status.value)
                continue

            matched_link_ids.add(str(link.id))
            if line_amount is not None and Decimal(link.expected_amount) != line_amount:
                discrepancy = ReconciliationDiscrepancy(
                    run_id=run.id,
                    ledger_account_id=None,
                    currency=statement.currency,
                    discrepancy_type=ReconciliationDiscrepancyType.MISMATCHED_AMOUNT,
                    internal_amount=Decimal(link.expected_amount),
                    external_amount=line_amount,
                    delta=_delta(Decimal(link.expected_amount), line_amount),
                    details={
                        "entity_type": link.entity_type,
                        "entity_id": str(link.entity_id),
                        "statement_id": str(statement.id),
                    },
                    status=ReconciliationDiscrepancyStatus.OPEN,
                )
                db.add(discrepancy)
                discrepancies_created += 1
                metrics.mark_discrepancy(discrepancy.discrepancy_type.value, discrepancy.status.value)
                link.status = ReconciliationLinkStatus.MISMATCHED
                link.run_id = run.id
                links_mismatched += 1
            else:
                link.status = ReconciliationLinkStatus.MATCHED
                link.run_id = run.id
                links_matched += 1

        for link in pending_links:
            if str(link.id) in matched_link_ids:
                continue
            link.status = ReconciliationLinkStatus.MISMATCHED
            link.run_id = run.id
            links_mismatched += 1
            discrepancy = ReconciliationDiscrepancy(
                run_id=run.id,
                ledger_account_id=None,
                currency=statement.currency,
                discrepancy_type=ReconciliationDiscrepancyType.UNMATCHED_INTERNAL,
                internal_amount=Decimal(link.expected_amount),
                external_amount=None,
                delta=None,
                details={
                    "entity_type": link.entity_type,
                    "entity_id": str(link.entity_id),
                    "statement_id": str(statement.id),
                },
                status=ReconciliationDiscrepancyStatus.OPEN,
            )
            db.add(discrepancy)
            discrepancies_created += 1
            metrics.mark_discrepancy(discrepancy.discrepancy_type.value, discrepancy.status.value)

        links_pending = len(pending_links) - links_matched - links_mismatched
        metrics.mark_link(status=ReconciliationLinkStatus.MATCHED.value, count=links_matched)
        metrics.mark_link(status=ReconciliationLinkStatus.MISMATCHED.value, count=links_mismatched)
        metrics.mark_link(status=ReconciliationLinkStatus.PENDING.value, count=max(links_pending, 0))

        summary = {
            "mismatches_found": discrepancies_created,
            "total_delta_abs": str(total_delta_abs),
            "links_matched": links_matched,
            "links_mismatched": links_mismatched,
            "links_pending": max(links_pending, 0),
        }
        run.summary = summary
        run.status = ReconciliationRunStatus.COMPLETED
        audit = AuditService(db).audit(
            event_type="RECONCILIATION_RUN_COMPLETED",
            entity_type="reconciliation_run",
            entity_id=str(run.id),
            action="completed",
            after={"run_id": str(run.id), "summary": summary, "statement_id": str(statement.id)},
            request_ctx=_audit_actor(created_by),
        )
        AuditService(db).audit(
            event_type="EXTERNAL_RECONCILIATION_COMPLETED",
            entity_type="reconciliation_run",
            entity_id=str(run.id),
            action="completed",
            after={"run_id": str(run.id), "summary": summary, "statement_id": str(statement.id)},
            request_ctx=_audit_actor(created_by),
        )
        run.audit_event_id = audit.id
        db.flush()
        metrics.mark_run(scope=run.scope.value, status=run.status.value)
        logger.info(
            "external reconciliation completed",
            extra={"run_id": str(run.id), "statement_id": str(statement.id), "mismatches": discrepancies_created},
        )
        return str(run.id)
    except Exception:  # noqa: BLE001
        run.status = ReconciliationRunStatus.FAILED
        db.flush()
        metrics.mark_run(scope=run.scope.value, status=run.status.value)
        logger.exception("external reconciliation failed", extra={"run_id": str(run.id), "statement_id": statement_id})
        raise


def resolve_discrepancy_with_adjustment(
    db: Session,
    discrepancy_id: str,
    *,
    note: str,
    created_by: str | None = None,
) -> str:
    discrepancy = (
        db.query(ReconciliationDiscrepancy)
        .filter(ReconciliationDiscrepancy.id == discrepancy_id)
        .one_or_none()
    )
    if discrepancy is None:
        raise ValueError("discrepancy_not_found")
    if discrepancy.status != ReconciliationDiscrepancyStatus.OPEN:
        raise ValueError("discrepancy_not_open")
    if discrepancy.ledger_account_id is None:
        raise ValueError("discrepancy_missing_account")

    account = (
        db.query(InternalLedgerAccount)
        .filter(InternalLedgerAccount.id == discrepancy.ledger_account_id)
        .one_or_none()
    )
    if account is None:
        raise ValueError("ledger_account_not_found")

    delta = _safe_decimal(discrepancy.delta)
    if delta is None:
        raise ValueError("discrepancy_missing_delta")
    if delta == 0:
        raise ValueError("discrepancy_zero_delta")
    if delta != delta.to_integral_value():
        raise ValueError("discrepancy_delta_not_integral")

    amount = int(abs(delta))
    direction_target = (
        InternalLedgerEntryDirection.DEBIT if delta > 0 else InternalLedgerEntryDirection.CREDIT
    )
    direction_suspense = (
        InternalLedgerEntryDirection.CREDIT if delta > 0 else InternalLedgerEntryDirection.DEBIT
    )

    ledger_service = InternalLedgerService(db)
    result = ledger_service.post_transaction(
        tenant_id=account.tenant_id,
        transaction_type=InternalLedgerTransactionType.ADJUSTMENT,
        external_ref_type="RECONCILIATION_DISCREPANCY",
        external_ref_id=str(discrepancy.id),
        idempotency_key=f"reconciliation:adjustment:{discrepancy.id}",
        posted_at=datetime.now(timezone.utc),
        meta={"note": note, "discrepancy_id": str(discrepancy.id)},
        entries=[
            InternalLedgerLine(
                account_type=account.account_type,
                client_id=account.client_id,
                direction=direction_target,
                amount=amount,
                currency=discrepancy.currency,
            ),
            InternalLedgerLine(
                account_type=InternalLedgerAccountType.SUSPENSE,
                client_id=None,
                direction=direction_suspense,
                amount=amount,
                currency=discrepancy.currency,
            ),
        ],
    )

    resolution = {
        "adjustment_tx_id": str(result.transaction.id),
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "resolved_by": created_by,
        "note": note,
    }
    discrepancy.status = ReconciliationDiscrepancyStatus.RESOLVED
    discrepancy.resolution = resolution
    db.flush()
    metrics.mark_discrepancy(discrepancy.discrepancy_type.value, discrepancy.status.value)
    metrics.mark_resolved()

    AuditService(db).audit(
        event_type="DISCREPANCY_RESOLVED",
        entity_type="reconciliation_discrepancy",
        entity_id=str(discrepancy.id),
        action="resolved",
        after={"discrepancy_id": str(discrepancy.id), "adjustment_tx_id": str(result.transaction.id)},
        request_ctx=_audit_actor(created_by),
    )
    logger.info(
        "discrepancy resolved",
        extra={"discrepancy_id": str(discrepancy.id), "adjustment_tx_id": str(result.transaction.id)},
    )
    return str(result.transaction.id)


def ignore_discrepancy(
    db: Session,
    discrepancy_id: str,
    *,
    reason: str,
    created_by: str | None = None,
) -> None:
    discrepancy = (
        db.query(ReconciliationDiscrepancy)
        .filter(ReconciliationDiscrepancy.id == discrepancy_id)
        .one_or_none()
    )
    if discrepancy is None:
        raise ValueError("discrepancy_not_found")
    if discrepancy.status != ReconciliationDiscrepancyStatus.OPEN:
        raise ValueError("discrepancy_not_open")

    discrepancy.status = ReconciliationDiscrepancyStatus.IGNORED
    discrepancy.resolution = {
        "reason": reason,
        "ignored_at": datetime.now(timezone.utc).isoformat(),
        "ignored_by": created_by,
    }
    db.flush()
    metrics.mark_discrepancy(discrepancy.discrepancy_type.value, discrepancy.status.value)

    AuditService(db).audit(
        event_type="DISCREPANCY_IGNORED",
        entity_type="reconciliation_discrepancy",
        entity_id=str(discrepancy.id),
        action="ignored",
        after={"discrepancy_id": str(discrepancy.id), "reason": reason},
        request_ctx=_audit_actor(created_by),
    )
    logger.info("discrepancy ignored", extra={"discrepancy_id": str(discrepancy.id)})
