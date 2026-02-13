from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies.partner import partner_portal_user
from app.db import get_db
from app.models.audit_log import ActorType, AuditVisibility
from app.models.fuel import FuelStation, FuelStationPrice, FuelStationPriceSource, FuelStationPriceStatus
from app.schemas.fuel import (
    FuelStationPriceImportSummary,
    FuelStationPriceItemIn,
    FuelStationPriceItemOut,
    FuelStationPricesOut,
    FuelStationPricesUpsertIn,
)
from app.services.audit_service import AuditService, request_context_from_request

router = APIRouter(tags=["fuel-station-prices"])

_ALLOWED_CURRENCY = {"RUB"}
_ALLOWED_PRODUCTS = {"AI95", "AI92", "DT"}


def _normalize_item(item: FuelStationPriceItemIn) -> FuelStationPriceItemIn:
    item.product_code = item.product_code.strip().upper()
    item.currency = item.currency.strip().upper()
    if item.currency not in _ALLOWED_CURRENCY:
        raise HTTPException(status_code=400, detail=f"unsupported_currency:{item.currency}")
    if item.product_code not in _ALLOWED_PRODUCTS:
        raise HTTPException(status_code=400, detail=f"unknown_product_code:{item.product_code}")
    if item.valid_from and item.valid_to and item.valid_to <= item.valid_from:
        raise HTTPException(status_code=400, detail="invalid_validity_window")
    return item


def _current_prices_query(db: Session, station_id: str, as_of: datetime):
    return (
        db.query(FuelStationPrice)
        .filter(
            FuelStationPrice.station_id == station_id,
            FuelStationPrice.status == FuelStationPriceStatus.ACTIVE,
            (FuelStationPrice.valid_from.is_(None) | (FuelStationPrice.valid_from <= as_of)),
            (FuelStationPrice.valid_to.is_(None) | (FuelStationPrice.valid_to > as_of)),
        )
        .order_by(FuelStationPrice.updated_at.desc())
    )


def _upsert_prices(
    db: Session,
    station_id: str,
    items: list[FuelStationPriceItemIn],
    source: FuelStationPriceSource,
    updated_by: str | None,
) -> tuple[list[dict], list[dict], int, int]:
    inserted = 0
    updated = 0
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
            "source": source.value,
            "updated_by": updated_by,
        }

        if row is None:
            row = FuelStationPrice(
                station_id=station_id,
                product_code=normalized.product_code,
                price=Decimal(str(normalized.price)),
                currency=normalized.currency,
                status=FuelStationPriceStatus.ACTIVE,
                valid_from=normalized.valid_from,
                valid_to=normalized.valid_to,
                source=source,
                updated_by=updated_by,
                meta=normalized.meta,
            )
            db.add(row)
            inserted += 1
            before_items.append({"product_code": normalized.product_code, "created": True})
            after_items.append(after_payload)
            continue

        before_items.append(
            {
                "product_code": row.product_code,
                "price": float(row.price),
                "currency": row.currency,
                "valid_from": row.valid_from.isoformat() if row.valid_from else None,
                "valid_to": row.valid_to.isoformat() if row.valid_to else None,
            }
        )
        row.price = Decimal(str(normalized.price))
        row.currency = normalized.currency
        row.status = FuelStationPriceStatus.ACTIVE
        row.source = source
        row.updated_by = updated_by
        row.meta = normalized.meta
        row.updated_at = datetime.now(timezone.utc)
        updated += 1
        after_items.append(after_payload)

    db.flush()
    return before_items, after_items, inserted, updated


@router.get("/api/v1/fuel/stations/{station_id}/prices", response_model=FuelStationPricesOut)
def get_fuel_station_prices(
    station_id: str,
    as_of: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> FuelStationPricesOut:
    station = db.query(FuelStation).filter(FuelStation.id == station_id).one_or_none()
    if station is None:
        raise HTTPException(status_code=404, detail="station_not_found")

    effective_as_of = as_of or datetime.now(timezone.utc)
    rows = _current_prices_query(db, station_id, effective_as_of).all()
    items = [
        FuelStationPriceItemOut(
            product_code=row.product_code,
            price=float(row.price),
            currency=row.currency,
            valid_from=row.valid_from,
            valid_to=row.valid_to,
        )
        for row in rows
    ]
    return FuelStationPricesOut(station_id=station_id, as_of=effective_as_of, items=items)


@router.put("/api/v1/partner/fuel/stations/{station_id}/prices", response_model=FuelStationPricesOut)
def put_fuel_station_prices(
    station_id: str,
    payload: FuelStationPricesUpsertIn,
    request: Request,
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> FuelStationPricesOut:
    station = db.query(FuelStation).filter(FuelStation.id == station_id).one_or_none()
    if station is None:
        raise HTTPException(status_code=404, detail="station_not_found")

    source = FuelStationPriceSource(payload.source.upper())
    updated_by = token.get("email") or token.get("user_id") or token.get("sub")
    before_items, after_items, _, _ = _upsert_prices(db, station_id, payload.items, source, updated_by)

    audit = AuditService(db)
    audit.audit(
        event_type="fuel.station.prices.updated",
        entity_type="fuel_station",
        entity_id=station_id,
        action="upsert_prices",
        visibility=AuditVisibility.INTERNAL,
        before={"items": before_items},
        after={"items": after_items, "source": source.value},
        request_ctx=request_context_from_request(request, token=token, actor_type=ActorType.USER),
    )

    db.commit()
    return get_fuel_station_prices(station_id=station_id, as_of=datetime.now(timezone.utc), db=db)


@router.post("/api/v1/partner/fuel/stations/{station_id}/prices/import", response_model=FuelStationPriceImportSummary)
async def import_fuel_station_prices(
    station_id: str,
    request: Request,
    file: UploadFile = File(...),
    token: dict = Depends(partner_portal_user),
    db: Session = Depends(get_db),
) -> FuelStationPriceImportSummary:
    station = db.query(FuelStation).filter(FuelStation.id == station_id).one_or_none()
    if station is None:
        raise HTTPException(status_code=404, detail="station_not_found")

    payload_bytes = await file.read()
    raw = payload_bytes.decode("utf-8")
    errors: list[str] = []
    parsed_items: list[FuelStationPriceItemIn] = []

    try:
        if file.filename and file.filename.lower().endswith(".json"):
            data = json.loads(raw)
            rows = data.get("items", data)
            for row in rows:
                parsed_items.append(FuelStationPriceItemIn.model_validate(row))
        else:
            reader = csv.DictReader(io.StringIO(raw))
            for row in reader:
                parsed_items.append(
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
        raise HTTPException(status_code=400, detail=f"import_parse_error:{exc}") from exc

    if len(parsed_items) > 500:
        raise HTTPException(status_code=400, detail="max_items_exceeded")

    updated_by = token.get("email") or token.get("user_id") or token.get("sub")
    try:
        before_items, after_items, inserted, updated = _upsert_prices(
            db,
            station_id,
            parsed_items,
            FuelStationPriceSource.IMPORT,
            updated_by,
        )
    except HTTPException as exc:
        errors.append(str(exc.detail))
        raise

    audit = AuditService(db)
    audit.audit(
        event_type="fuel.station.prices.imported",
        entity_type="fuel_station",
        entity_id=station_id,
        action="import_prices",
        visibility=AuditVisibility.INTERNAL,
        before={"items": before_items},
        after={"items": after_items, "filename": file.filename},
        request_ctx=request_context_from_request(request, token=token, actor_type=ActorType.USER),
    )

    db.commit()
    return FuelStationPriceImportSummary(inserted=inserted, updated=updated, errors=errors)


__all__ = ["router"]
