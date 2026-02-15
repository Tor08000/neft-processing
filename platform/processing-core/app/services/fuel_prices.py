from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.fuel import (
    FuelStationPrice,
    FuelStationPriceAudit,
    FuelStationPriceSource,
    FuelStationPriceStatus,
)
from app.schemas.fuel import FuelStationPriceItemIn

_ALLOWED_CURRENCY = {"RUB"}
_ALLOWED_SOURCE = {source.value for source in FuelStationPriceSource}


@dataclass
class ImportErrorItem:
    row: int
    error: str
    raw: str


@dataclass
class UpsertResult:
    inserted: int
    updated: int
    skipped: int
    before_items: list[dict]
    after_items: list[dict]


def _normalize_item(item: FuelStationPriceItemIn) -> FuelStationPriceItemIn:
    item.product_code = item.product_code.strip().upper()
    item.currency = item.currency.strip().upper()

    if item.currency not in _ALLOWED_CURRENCY:
        raise ValueError(f"unsupported_currency:{item.currency}")
    if item.valid_to is not None and item.valid_from is not None and item.valid_to <= item.valid_from:
        raise ValueError("invalid_validity_window")
    return item


def get_station_prices(
    db: Session,
    station_id: str,
    as_of: datetime,
    product_code: str | None = None,
    include_inactive: bool = False,
) -> list[FuelStationPrice]:
    query = db.query(FuelStationPrice).filter(FuelStationPrice.station_id == station_id)

    if not include_inactive:
        query = query.filter(FuelStationPrice.status == FuelStationPriceStatus.ACTIVE)

    if product_code:
        query = query.filter(FuelStationPrice.product_code == product_code.strip().upper())

    query = query.filter(
        (FuelStationPrice.valid_from.is_(None) | (FuelStationPrice.valid_from <= as_of)),
        (FuelStationPrice.valid_to.is_(None) | (FuelStationPrice.valid_to > as_of)),
    )

    return query.order_by(FuelStationPrice.product_code.asc(), FuelStationPrice.updated_at.desc()).all()


def write_price_audit(
    db: Session,
    *,
    station_id: str,
    product_code: str,
    action: str,
    actor: str | None,
    source: str,
    before: dict | None,
    after: dict | None,
    request_id: str | None,
    meta: dict | None = None,
) -> None:
    if source not in _ALLOWED_SOURCE and source != "SYSTEM":
        raise HTTPException(status_code=400, detail=f"unsupported_source:{source}")

    db.add(
        FuelStationPriceAudit(
            station_id=station_id,
            product_code=product_code,
            action=action,
            actor=actor,
            source=source,
            before=before,
            after=after,
            request_id=request_id,
            meta=meta,
        )
    )


def upsert_station_prices(
    db: Session,
    *,
    station_id: str,
    items: list[FuelStationPriceItemIn],
    source: str,
    actor: str | None,
    request_id: str | None,
) -> UpsertResult:
    now = datetime.now(timezone.utc)
    inserted = 0
    updated = 0
    skipped = 0
    before_items: list[dict] = []
    after_items: list[dict] = []

    for item in items:
        normalized = _normalize_item(item)

        row = (
            db.query(FuelStationPrice)
            .filter(
                FuelStationPrice.station_id == station_id,
                FuelStationPrice.product_code == normalized.product_code,
                FuelStationPrice.valid_from == normalized.valid_from,
                FuelStationPrice.valid_to == normalized.valid_to,
            )
            .one_or_none()
        )

        after_payload = {
            "product_code": normalized.product_code,
            "price": float(normalized.price),
            "currency": normalized.currency,
            "valid_from": normalized.valid_from.isoformat() if normalized.valid_from else None,
            "valid_to": normalized.valid_to.isoformat() if normalized.valid_to else None,
            "source": source,
            "updated_at": now.isoformat(),
            "updated_by": actor,
        }

        if row is None:
            db.add(
                FuelStationPrice(
                    station_id=station_id,
                    product_code=normalized.product_code,
                    price=Decimal(str(normalized.price)),
                    currency=normalized.currency,
                    status=FuelStationPriceStatus.ACTIVE,
                    valid_from=normalized.valid_from,
                    valid_to=normalized.valid_to,
                    source=FuelStationPriceSource(source),
                    updated_at=now,
                    updated_by=actor,
                    meta=normalized.meta,
                )
            )
            inserted += 1
            before_payload = None
        else:
            before_payload = {
                "product_code": row.product_code,
                "price": float(row.price),
                "currency": row.currency,
                "valid_from": row.valid_from.isoformat() if row.valid_from else None,
                "valid_to": row.valid_to.isoformat() if row.valid_to else None,
                "source": row.source.value,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "updated_by": row.updated_by,
            }

            unchanged = (
                float(row.price) == float(normalized.price)
                and row.currency == normalized.currency
                and row.status == FuelStationPriceStatus.ACTIVE
                and row.source == FuelStationPriceSource(source)
                and row.meta == normalized.meta
                and row.updated_by == actor
            )
            if unchanged:
                skipped += 1
                continue

            row.price = Decimal(str(normalized.price))
            row.currency = normalized.currency
            row.status = FuelStationPriceStatus.ACTIVE
            row.source = FuelStationPriceSource(source)
            row.updated_by = actor
            row.meta = normalized.meta
            row.updated_at = now
            updated += 1

        before_items.append(before_payload or {"product_code": normalized.product_code})
        after_items.append(after_payload)
        write_price_audit(
            db,
            station_id=station_id,
            product_code=normalized.product_code,
            action="UPSERT",
            actor=actor,
            source=source,
            before=before_payload,
            after=after_payload,
            request_id=request_id,
        )

    db.flush()
    return UpsertResult(inserted=inserted, updated=updated, skipped=skipped, before_items=before_items, after_items=after_items)


def import_station_prices_csv(content: bytes) -> tuple[list[FuelStationPriceItemIn], list[ImportErrorItem]]:
    raw = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(raw))
    items: list[FuelStationPriceItemIn] = []
    errors: list[ImportErrorItem] = []

    for row_idx, row in enumerate(reader, start=2):
        try:
            items.append(
                FuelStationPriceItemIn.model_validate(
                    {
                        "product_code": row.get("product_code"),
                        "price": row.get("price"),
                        "currency": row.get("currency") or "RUB",
                        "valid_from": row.get("valid_from") or None,
                        "valid_to": row.get("valid_to") or None,
                    }
                )
            )
        except Exception as exc:
            errors.append(ImportErrorItem(row=row_idx, error=str(exc), raw=str(row)))

    return items, errors
