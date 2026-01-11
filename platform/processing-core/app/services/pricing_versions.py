from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import desc, or_, inspect
from sqlalchemy.orm import Session

from app.models.pricing import (
    PriceSchedule,
    PriceScheduleStatus,
    PriceVersion,
    PriceVersionAudit,
    PriceVersionItem,
    PriceVersionStatus,
)
from app.db.schema import DB_SCHEMA


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _pricing_tables_ready(db: Session) -> bool:
    try:
        inspector = inspect(db.get_bind())
        return inspector.has_table("price_versions", schema=DB_SCHEMA)
    except Exception:
        return False


def create_price_version(
    db: Session, *, name: str, notes: str | None = None, created_by: str | None = None
) -> PriceVersion:
    version = PriceVersion(
        id=str(uuid4()),
        name=name,
        status=PriceVersionStatus.DRAFT,
        notes=notes,
        created_by=created_by,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def list_price_versions(db: Session) -> list[PriceVersion]:
    return db.query(PriceVersion).order_by(PriceVersion.created_at.desc()).all()


def add_price_version_item(
    db: Session,
    *,
    price_version_id: str,
    plan_code: str,
    billing_period: str,
    currency: str,
    base_price: str,
    setup_fee: str | None,
    meta: dict | None = None,
) -> PriceVersionItem:
    version = db.get(PriceVersion, price_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="price_version_not_found")
    if version.status != PriceVersionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="price_version_not_editable")

    base_price_value = Decimal(base_price)
    setup_fee_value = Decimal(setup_fee) if setup_fee is not None else None
    item = (
        db.query(PriceVersionItem)
        .filter(
            PriceVersionItem.price_version_id == price_version_id,
            PriceVersionItem.plan_code == plan_code,
            PriceVersionItem.billing_period == billing_period,
            PriceVersionItem.currency == currency,
        )
        .one_or_none()
    )
    if item:
        item.base_price = base_price_value
        item.setup_fee = setup_fee_value
        item.meta = meta
    else:
        item = PriceVersionItem(
            price_version_id=price_version_id,
            plan_code=plan_code,
            billing_period=billing_period,
            currency=currency,
            base_price=base_price_value,
            setup_fee=setup_fee_value,
            meta=meta,
        )
        db.add(item)
    db.commit()
    db.refresh(item)
    return item


def publish_price_version(db: Session, *, price_version_id: str, actor_id: str | None = None) -> PriceVersion:
    version = db.get(PriceVersion, price_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="price_version_not_found")
    if version.status != PriceVersionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="price_version_not_draft")
    version.status = PriceVersionStatus.PUBLISHED
    version.published_at = _now()
    db.add(
        PriceVersionAudit(
            price_version_id=price_version_id,
            event_type="PRICING_PUBLISHED",
            actor_id=actor_id,
            payload={"status": version.status.value},
        )
    )
    db.commit()
    db.refresh(version)
    return version


def create_schedule(
    db: Session,
    *,
    price_version_id: str,
    effective_from: datetime,
    effective_to: datetime | None = None,
    priority: int = 0,
) -> PriceSchedule:
    version = db.get(PriceVersion, price_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="price_version_not_found")
    schedule = PriceSchedule(
        id=str(uuid4()),
        price_version_id=price_version_id,
        effective_from=effective_from,
        effective_to=effective_to,
        priority=priority,
        status=PriceScheduleStatus.SCHEDULED,
    )
    db.add(schedule)
    db.add(
        PriceVersionAudit(
            price_version_id=price_version_id,
            event_type="PRICING_SCHEDULE_CREATED",
            payload={"effective_from": effective_from.isoformat(), "effective_to": effective_to.isoformat() if effective_to else None},
        )
    )
    db.commit()
    db.refresh(schedule)
    return schedule


def activate_schedule_now(db: Session, *, schedule_id: str) -> PriceSchedule:
    schedule = db.get(PriceSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="price_schedule_not_found")
    schedule.effective_from = _now()
    schedule.status = PriceScheduleStatus.ACTIVE
    db.commit()
    db.refresh(schedule)
    return schedule


def cancel_schedule(db: Session, *, schedule_id: str, actor_id: str | None = None) -> PriceSchedule:
    schedule = db.get(PriceSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="price_schedule_not_found")
    schedule.status = PriceScheduleStatus.CANCELLED
    db.add(
        PriceVersionAudit(
            price_version_id=schedule.price_version_id,
            event_type="PRICING_ROLLBACK",
            actor_id=actor_id,
            payload={"schedule_id": schedule_id},
        )
    )
    db.commit()
    db.refresh(schedule)
    return schedule


def get_active_price_version(db: Session, *, at: datetime | None = None) -> PriceVersion | None:
    if not _pricing_tables_ready(db):
        return None
    now = at or _now()
    schedule = (
        db.query(PriceSchedule)
        .filter(
            PriceSchedule.status != PriceScheduleStatus.CANCELLED,
            PriceSchedule.effective_from <= now,
            or_(PriceSchedule.effective_to.is_(None), PriceSchedule.effective_to > now),
        )
        .order_by(desc(PriceSchedule.priority), desc(PriceSchedule.effective_from))
        .first()
    )
    if not schedule:
        return None
    if schedule.status != PriceScheduleStatus.ACTIVE:
        schedule.status = PriceScheduleStatus.ACTIVE
        db.add(schedule)
        db.commit()
    version = db.get(PriceVersion, schedule.price_version_id)
    if version and version.status != PriceVersionStatus.ACTIVE:
        version.status = PriceVersionStatus.ACTIVE
        version.activated_at = now
        db.commit()
    return version


__all__ = [
    "activate_schedule_now",
    "add_price_version_item",
    "cancel_schedule",
    "create_price_version",
    "create_schedule",
    "get_active_price_version",
    "list_price_versions",
    "publish_price_version",
]
