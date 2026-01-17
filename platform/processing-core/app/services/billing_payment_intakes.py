from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import MetaData, Table, insert, func, select, update
from sqlalchemy.orm import Session

from app.db.schema import DB_SCHEMA


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


def list_payment_intakes(
    db: Session,
    *,
    org_id: int | None = None,
    status: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    if not _tables_ready(db, ["billing_payment_intakes"]):
        return [], 0
    intakes = _table(db, "billing_payment_intakes")
    query = select(intakes)
    if org_id is not None:
        query = query.where(intakes.c.org_id == org_id)
    if status:
        query = query.where(intakes.c.status == status)
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar() or 0
    rows = (
        db.execute(query.order_by(intakes.c.created_at.desc()).offset(offset).limit(limit))
        .mappings()
        .all()
    )
    return rows, total


def get_payment_intake(db: Session, *, intake_id: int) -> dict[str, Any] | None:
    if not _tables_ready(db, ["billing_payment_intakes"]):
        return None
    intakes = _table(db, "billing_payment_intakes")
    return (
        db.execute(select(intakes).where(intakes.c.id == intake_id))
        .mappings()
        .first()
    )


def get_invoice(db: Session, *, invoice_id: int) -> dict[str, Any] | None:
    if not _tables_ready(db, ["billing_invoices"]):
        return None
    invoices = _table(db, "billing_invoices")
    return db.execute(select(invoices).where(invoices.c.id == invoice_id)).mappings().first()


def list_invoice_payment_intakes(db: Session, *, invoice_id: int) -> list[dict[str, Any]]:
    if not _tables_ready(db, ["billing_payment_intakes"]):
        return []
    intakes = _table(db, "billing_payment_intakes")
    rows = (
        db.execute(
            select(intakes)
            .where(intakes.c.invoice_id == invoice_id)
            .order_by(intakes.c.created_at.desc())
        )
        .mappings()
        .all()
    )
    return rows


def create_payment_intake(
    db: Session,
    *,
    org_id: int,
    invoice_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    intakes = _table(db, "billing_payment_intakes")
    insert_stmt = (
        insert(intakes)
        .values(**payload, org_id=org_id, invoice_id=invoice_id, created_at=_now())
        .returning(intakes)
    )
    return db.execute(insert_stmt).mappings().first()


def review_payment_intake(
    db: Session,
    *,
    intake_id: int,
    status: str,
    reviewed_by_admin: str | None,
    review_note: str | None,
) -> dict[str, Any] | None:
    if not _tables_ready(db, ["billing_payment_intakes"]):
        return None
    intakes = _table(db, "billing_payment_intakes")
    update_stmt = (
        update(intakes)
        .where(intakes.c.id == intake_id)
        .values(
            status=status,
            reviewed_by_admin=reviewed_by_admin,
            reviewed_at=_now(),
            review_note=review_note,
        )
        .returning(intakes)
    )
    return db.execute(update_stmt).mappings().first()


def mark_payment_intake_status(
    db: Session,
    *,
    intake_id: int,
    status: str,
) -> dict[str, Any] | None:
    if not _tables_ready(db, ["billing_payment_intakes"]):
        return None
    intakes = _table(db, "billing_payment_intakes")
    update_stmt = update(intakes).where(intakes.c.id == intake_id).values(status=status).returning(intakes)
    return db.execute(update_stmt).mappings().first()
