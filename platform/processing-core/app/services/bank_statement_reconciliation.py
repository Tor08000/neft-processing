from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import MetaData, Table, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db.schema import DB_SCHEMA
from app.db.types import new_uuid_str
from app.models.audit_log import AuditVisibility
from app.services.audit_service import AuditService, RequestContext
from app.services.client_notifications import ADMIN_TARGET_ROLES, ClientNotificationSeverity, create_notification
from app.services.entitlements_v2_service import get_org_entitlements_snapshot
from app.services.subscription_billing import update_invoice_status


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=db.get_bind(), schema=DB_SCHEMA)


def _tables_ready(db: Session, table_names: list[str]) -> bool:
    try:
        from sqlalchemy import inspect

        inspector = inspect(db.get_bind())
        return all(inspector.has_table(name, schema=DB_SCHEMA) for name in table_names)
    except Exception:
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    cleaned = value.replace(" ", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except (InvalidOperation, AttributeError):
        return None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _extract_invoice_id(text: str) -> str | None:
    patterns = [
        r"invoice\\s*#?(?P<invoice>[a-zA-Z0-9-]{6,36})",
        r"neft\\s*invoice\\s*(?P<invoice>[a-zA-Z0-9-]{6,36})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group("invoice")
    return None


def _extract_org_id(text: str) -> int | None:
    match = re.search(r"org\\s*(?P<org>\\d{1,18})", text, flags=re.IGNORECASE)
    if match:
        return int(match.group("org"))
    return None


def _normalize_purpose(text: str | None) -> str:
    return (text or "").strip()


def create_import_record(
    db: Session,
    *,
    import_id: str,
    admin_id: str | None,
    file_object_key: str,
    fmt: str,
    period_from: datetime | None,
    period_to: datetime | None,
) -> dict[str, Any]:
    if not _tables_ready(db, ["bank_statement_imports"]):
        raise RuntimeError("bank_statement_imports_table_missing")
    imports = _table(db, "bank_statement_imports")
    insert_stmt = (
        insert(imports)
        .values(
            id=import_id,
            uploaded_by_admin=admin_id,
            uploaded_at=_now(),
            file_object_key=file_object_key,
            format=fmt,
            period_from=period_from.date() if period_from else None,
            period_to=period_to.date() if period_to else None,
            status="IMPORTED",
        )
        .returning(imports)
    )
    return db.execute(insert_stmt).mappings().first()


def mark_import_status(
    db: Session,
    *,
    import_id: str,
    status: str,
    error: str | None = None,
) -> dict[str, Any] | None:
    if not _tables_ready(db, ["bank_statement_imports"]):
        return None
    imports = _table(db, "bank_statement_imports")
    update_stmt = (
        update(imports)
        .where(imports.c.id == import_id)
        .values(status=status, error=error)
        .returning(imports)
    )
    return db.execute(update_stmt).mappings().first()


def parse_csv_simple(
    db: Session,
    *,
    import_id: str,
    payload: bytes,
    actor: RequestContext,
) -> int:
    required_tables = ["bank_statement_imports", "bank_statement_transactions"]
    if not _tables_ready(db, required_tables):
        raise RuntimeError("bank_statement_tables_missing")

    transactions = _table(db, "bank_statement_transactions")
    decoded = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(decoded))
    created = 0
    for row in reader:
        posted_at = _parse_date(row.get("date"))
        amount = _parse_decimal(row.get("amount"))
        if posted_at is None or amount is None:
            continue
        currency = (row.get("currency") or "RUB").strip().upper()
        bank_tx_id = (row.get("transaction_id") or row.get("bank_tx_id") or "").strip()
        reference = (row.get("reference") or "").strip()
        if not bank_tx_id:
            if not reference:
                continue
            bank_tx_id = f"ref:{reference}:{amount}:{posted_at.date().isoformat()}"
        record = {
            "id": new_uuid_str(),
            "import_id": import_id,
            "bank_tx_id": bank_tx_id,
            "posted_at": posted_at,
            "amount": amount,
            "currency": currency,
            "payer_name": (row.get("payer_name") or "").strip() or None,
            "payer_inn": (row.get("payer_inn") or "").strip() or None,
            "reference": reference or None,
            "purpose_text": (row.get("purpose_text") or "").strip() or None,
            "raw_json": row,
            "matched_status": "UNMATCHED",
            "confidence_score": Decimal("0"),
            "created_at": _now(),
        }
        insert_stmt = pg_insert(transactions).values(**record).on_conflict_do_nothing(
            index_elements=["bank_tx_id"]
        )
        result = db.execute(insert_stmt)
        if result.rowcount:
            created += 1

    AuditService(db).audit(
        event_type="bank_statement_parsed",
        entity_type="bank_statement_import",
        entity_id=str(import_id),
        action="PARSE",
        visibility=AuditVisibility.INTERNAL,
        after={"transactions_created": created},
        request_ctx=actor,
    )
    return created


@dataclass(frozen=True)
class MatchResult:
    status: str
    invoice_id: str | None
    confidence: Decimal


def _match_transaction(
    tx: dict[str, Any],
    invoice_by_id: dict[str, dict[str, Any]],
    invoices_by_org_amount: dict[tuple[int, Decimal], list[dict[str, Any]]],
    invoices_by_inn_amount: dict[tuple[str, Decimal], list[dict[str, Any]]],
) -> MatchResult:
    if tx.get("amount") is None or Decimal(tx["amount"]) <= 0:
        return MatchResult(status="IGNORED", invoice_id=None, confidence=Decimal("0"))

    purpose = _normalize_purpose(tx.get("purpose_text"))
    invoice_id_in_purpose = _extract_invoice_id(purpose)
    if invoice_id_in_purpose and invoice_id_in_purpose in invoice_by_id:
        return MatchResult(status="MATCHED", invoice_id=invoice_id_in_purpose, confidence=Decimal("100"))

    org_id = _extract_org_id(purpose)
    amount = Decimal(tx["amount"])
    if org_id is not None:
        candidates = invoices_by_org_amount.get((org_id, amount), [])
        if len(candidates) == 1:
            return MatchResult(status="MATCHED", invoice_id=str(candidates[0]["id"]), confidence=Decimal("95"))
        if len(candidates) > 1:
            return MatchResult(status="AMBIGUOUS", invoice_id=None, confidence=Decimal("60"))

    payer_inn = (tx.get("payer_inn") or "").strip()
    if payer_inn:
        candidates = invoices_by_inn_amount.get((payer_inn, amount), [])
        if len(candidates) == 1:
            return MatchResult(status="MATCHED", invoice_id=str(candidates[0]["id"]), confidence=Decimal("85"))
        if len(candidates) > 1:
            return MatchResult(status="AMBIGUOUS", invoice_id=None, confidence=Decimal("60"))

    return MatchResult(status="UNMATCHED", invoice_id=None, confidence=Decimal("0"))


def match_transactions(
    db: Session,
    *,
    import_id: str,
    actor: RequestContext,
) -> int:
    required_tables = [
        "bank_statement_transactions",
        "billing_invoices",
        "billing_accounts",
    ]
    if not _tables_ready(db, required_tables):
        raise RuntimeError("bank_statement_tables_missing")

    transactions = _table(db, "bank_statement_transactions")
    billing_invoices = _table(db, "billing_invoices")
    billing_accounts = _table(db, "billing_accounts")

    invoice_rows = (
        db.execute(
            select(billing_invoices)
            .where(billing_invoices.c.status.in_(["ISSUED", "OVERDUE"]))
        )
        .mappings()
        .all()
    )
    invoice_by_id = {str(row["id"]): row for row in invoice_rows}
    invoices_by_org_amount: dict[tuple[int, Decimal], list[dict[str, Any]]] = {}
    invoices_by_inn_amount: dict[tuple[str, Decimal], list[dict[str, Any]]] = {}

    account_rows = db.execute(select(billing_accounts)).mappings().all()
    inn_by_org = {row["org_id"]: row.get("inn") for row in account_rows if row.get("inn")}

    for invoice in invoice_rows:
        amount = Decimal(str(invoice["total_amount"]))
        org_id = invoice["org_id"]
        invoices_by_org_amount.setdefault((org_id, amount), []).append(invoice)
        inn = inn_by_org.get(org_id)
        if inn:
            invoices_by_inn_amount.setdefault((inn, amount), []).append(invoice)

    rows = (
        db.execute(
            select(transactions).where(
                transactions.c.import_id == import_id,
                transactions.c.matched_status == "UNMATCHED",
            )
        )
        .mappings()
        .all()
    )
    updated = 0
    for row in rows:
        match = _match_transaction(row, invoice_by_id, invoices_by_org_amount, invoices_by_inn_amount)
        update_stmt = (
            update(transactions)
            .where(transactions.c.id == row["id"])
            .values(
                matched_status=match.status,
                matched_invoice_id=match.invoice_id,
                confidence_score=match.confidence,
            )
        )
        db.execute(update_stmt)
        updated += 1

    AuditService(db).audit(
        event_type="reconciliation_matched",
        entity_type="bank_statement_import",
        entity_id=str(import_id),
        action="MATCH",
        visibility=AuditVisibility.INTERNAL,
        after={"transactions_updated": updated},
        request_ctx=actor,
    )
    return updated


def _should_auto_approve(tx: dict[str, Any], invoice: dict[str, Any]) -> bool:
    if not invoice:
        return False
    if invoice["status"] not in {"ISSUED", "OVERDUE"}:
        return False
    if tx["currency"] != invoice["currency"]:
        return False
    if Decimal(str(tx["amount"])) != Decimal(str(invoice["total_amount"])):
        return False
    threshold = Decimal(str(settings.NEFT_RECONCILIATION_AUTO_APPROVE_THRESHOLD))
    return Decimal(str(tx["confidence_score"])) >= threshold


def _create_payment_intake(
    db: Session,
    *,
    invoice: dict[str, Any],
    tx: dict[str, Any],
    status: str,
    actor: RequestContext,
) -> dict[str, Any]:
    intakes = _table(db, "billing_payment_intakes")
    payload = {
        "status": status,
        "amount": tx["amount"],
        "currency": tx["currency"],
        "payer_name": tx.get("payer_name"),
        "payer_inn": tx.get("payer_inn"),
        "bank_reference": tx.get("reference") or tx.get("bank_tx_id"),
        "paid_at_claimed": tx.get("posted_at").date() if tx.get("posted_at") else None,
        "comment": tx.get("purpose_text"),
        "created_by_user_id": actor.actor_id or "reconciliation",
        "created_at": _now(),
    }
    insert_stmt = (
        insert(intakes)
        .values(org_id=invoice["org_id"], invoice_id=invoice["id"], **payload)
        .returning(intakes)
    )
    created = db.execute(insert_stmt).mappings().first()
    return created


def apply_matches(
    db: Session,
    *,
    import_id: str,
    actor: RequestContext,
) -> dict[str, int]:
    required_tables = ["bank_statement_transactions", "billing_invoices", "billing_payment_intakes", "org_subscriptions"]
    if not _tables_ready(db, required_tables):
        raise RuntimeError("bank_statement_tables_missing")

    transactions = _table(db, "bank_statement_transactions")
    billing_invoices = _table(db, "billing_invoices")
    intakes = _table(db, "billing_payment_intakes")

    rows = (
        db.execute(
            select(transactions)
            .where(
                transactions.c.import_id == import_id,
                transactions.c.matched_status.in_(["MATCHED", "AMBIGUOUS"]),
            )
        )
        .mappings()
        .all()
    )
    applied = 0
    under_review = 0
    for tx in rows:
        if tx.get("matched_invoice_id") is None:
            continue
        invoice = (
            db.execute(select(billing_invoices).where(billing_invoices.c.id == tx["matched_invoice_id"]))
            .mappings()
            .first()
        )
        if not invoice:
            continue

        existing = (
            db.execute(
                select(intakes.c.id)
                .where(
                    intakes.c.invoice_id == invoice["id"],
                    intakes.c.bank_reference == (tx.get("reference") or tx.get("bank_tx_id")),
                )
            )
            .mappings()
            .first()
        )
        if existing:
            continue

        if _should_auto_approve(tx, invoice):
            intake = _create_payment_intake(db, invoice=invoice, tx=tx, status="APPROVED", actor=actor)
            update_invoice_status(db, invoice_id=invoice["id"], status="PAID", request_ctx=actor)
            get_org_entitlements_snapshot(db, org_id=invoice["org_id"])
            AuditService(db).audit(
                event_type="reconciliation_auto_approved",
                entity_type="bank_statement_transaction",
                entity_id=str(tx["id"]),
                action="AUTO_APPROVE",
                visibility=AuditVisibility.INTERNAL,
                after={"invoice_id": invoice["id"], "payment_intake_id": intake["id"]},
                request_ctx=actor,
            )
            applied += 1
        else:
            _create_payment_intake(db, invoice=invoice, tx=tx, status="UNDER_REVIEW", actor=actor)
            create_notification(
                db,
                org_id=str(invoice["org_id"]),
                event_type="reconciliation_needs_review",
                severity=ClientNotificationSeverity.WARNING,
                title="Требуется проверка транзакции",
                body="Транзакция из банковской выписки требует ручной проверки.",
                link="/admin/reconciliation/transactions",
                target_roles=ADMIN_TARGET_ROLES,
                entity_type="bank_statement_transaction",
                entity_id=str(tx["id"]),
            )
            under_review += 1

    AuditService(db).audit(
        event_type="reconciliation_applied",
        entity_type="bank_statement_import",
        entity_id=str(import_id),
        action="APPLY",
        visibility=AuditVisibility.INTERNAL,
        after={"auto_approved": applied, "under_review": under_review},
        request_ctx=actor,
    )
    return {"auto_approved": applied, "under_review": under_review}


def list_imports(db: Session) -> list[dict[str, Any]]:
    if not _tables_ready(db, ["bank_statement_imports"]):
        return []
    imports = _table(db, "bank_statement_imports")
    return db.execute(select(imports).order_by(imports.c.uploaded_at.desc())).mappings().all()


def get_import(db: Session, *, import_id: str) -> dict[str, Any] | None:
    if not _tables_ready(db, ["bank_statement_imports"]):
        return None
    imports = _table(db, "bank_statement_imports")
    return db.execute(select(imports).where(imports.c.id == import_id)).mappings().first()


def list_transactions(
    db: Session,
    *,
    import_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    if not _tables_ready(db, ["bank_statement_transactions"]):
        return []
    transactions = _table(db, "bank_statement_transactions")
    query = select(transactions)
    if import_id:
        query = query.where(transactions.c.import_id == import_id)
    if status:
        query = query.where(transactions.c.matched_status == status)
    return db.execute(query.order_by(transactions.c.posted_at.desc())).mappings().all()


def apply_transaction_to_invoice(
    db: Session,
    *,
    transaction_id: str,
    invoice_id: str,
    actor: RequestContext,
) -> dict[str, Any] | None:
    required_tables = ["bank_statement_transactions", "billing_invoices", "billing_payment_intakes", "org_subscriptions"]
    if not _tables_ready(db, required_tables):
        return None
    transactions = _table(db, "bank_statement_transactions")
    billing_invoices = _table(db, "billing_invoices")
    tx = db.execute(select(transactions).where(transactions.c.id == transaction_id)).mappings().first()
    if not tx:
        return None
    invoice = db.execute(select(billing_invoices).where(billing_invoices.c.id == invoice_id)).mappings().first()
    if not invoice:
        return None

    update_stmt = (
        update(transactions)
        .where(transactions.c.id == transaction_id)
        .values(matched_status="MATCHED", matched_invoice_id=invoice_id, confidence_score=Decimal("100"))
    )
    db.execute(update_stmt)

    intake = _create_payment_intake(db, invoice=invoice, tx=tx, status="APPROVED", actor=actor)
    update_invoice_status(db, invoice_id=invoice["id"], status="PAID", request_ctx=actor)
    get_org_entitlements_snapshot(db, org_id=invoice["org_id"])

    AuditService(db).audit(
        event_type="reconciliation_manual_applied",
        entity_type="bank_statement_transaction",
        entity_id=str(transaction_id),
        action="MANUAL_APPLY",
        visibility=AuditVisibility.INTERNAL,
        after={"invoice_id": invoice_id, "payment_intake_id": intake["id"]},
        request_ctx=actor,
    )
    return intake


def ignore_transaction(
    db: Session,
    *,
    transaction_id: str,
    actor: RequestContext,
) -> bool:
    if not _tables_ready(db, ["bank_statement_transactions"]):
        return False
    transactions = _table(db, "bank_statement_transactions")
    updated = (
        db.execute(
            update(transactions)
            .where(transactions.c.id == transaction_id)
            .values(matched_status="IGNORED")
        )
        .rowcount
        or 0
    )
    if updated:
        AuditService(db).audit(
            event_type="reconciliation_ignored",
            entity_type="bank_statement_transaction",
            entity_id=str(transaction_id),
            action="IGNORE",
            visibility=AuditVisibility.INTERNAL,
            request_ctx=actor,
        )
    return bool(updated)
