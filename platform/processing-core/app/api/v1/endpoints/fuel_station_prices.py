from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies.partner import partner_portal_user
from app.db import get_db
from app.models.fuel import FuelStation, FuelStationPriceSource
from app.schemas.fuel import (
    FuelStationPriceImportError,
    FuelStationPriceImportSummary,
    FuelStationPriceItemOut,
    FuelStationPricesOut,
    FuelStationPricesUpsertIn,
)
from app.services.fuel_prices import (
    get_station_prices,
    import_station_prices_csv,
    upsert_station_prices,
    write_price_audit,
)

router = APIRouter(tags=["fuel-station-prices"])


@router.get("/api/v1/fuel/stations/{station_id}/prices", response_model=FuelStationPricesOut)
def get_fuel_station_prices(
    station_id: str,
    as_of: datetime | None = Query(default=None),
    product_code: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> FuelStationPricesOut:
    station = db.query(FuelStation).filter(FuelStation.id == station_id).one_or_none()
    if station is None:
        raise HTTPException(status_code=404, detail="station_not_found")

    effective_as_of = as_of or datetime.now(timezone.utc)
    rows = get_station_prices(
        db,
        station_id,
        effective_as_of,
        product_code=product_code,
        include_inactive=include_inactive,
    )
    items = [
        FuelStationPriceItemOut(
            product_code=row.product_code,
            price=float(row.price),
            currency=row.currency,
            valid_from=row.valid_from,
            valid_to=row.valid_to,
            source=row.source.value,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
    return FuelStationPricesOut(station_id=station_id, as_of=effective_as_of, currency="RUB", items=items)


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

    source = payload.source.upper()
    if source not in {member.value for member in FuelStationPriceSource}:
        raise HTTPException(status_code=400, detail=f"unsupported_source:{source}")

    actor = token.get("email") or token.get("user_id") or token.get("sub")
    request_id = request.headers.get("X-Request-Id") or request.headers.get("X-Correlation-Id")
    upsert_station_prices(
        db,
        station_id=station_id,
        items=payload.items,
        source=source,
        actor=actor,
        request_id=request_id,
    )
    db.commit()
    effective_as_of = datetime.now(timezone.utc)
    rows = get_station_prices(db, station_id, effective_as_of)
    items = [
        FuelStationPriceItemOut(
            product_code=row.product_code,
            price=float(row.price),
            currency=row.currency,
            valid_from=row.valid_from,
            valid_to=row.valid_to,
            source=row.source.value,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
    return FuelStationPricesOut(station_id=station_id, as_of=effective_as_of, currency="RUB", items=items)


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

    actor = token.get("email") or token.get("user_id") or token.get("sub")
    request_id = request.headers.get("X-Request-Id") or request.headers.get("X-Correlation-Id")

    payload_bytes = await file.read()
    parsed_items, parse_errors = import_station_prices_csv(payload_bytes)
    if len(parsed_items) > 500:
        raise HTTPException(status_code=400, detail="max_items_exceeded")

    row_errors: list[FuelStationPriceImportError] = [
        FuelStationPriceImportError(row=err.row, error=err.error, raw=err.raw) for err in parse_errors
    ]

    inserted = 0
    updated = 0
    skipped = 0
    for idx, item in enumerate(parsed_items, start=2):
        try:
            result = upsert_station_prices(
                db,
                station_id=station_id,
                items=[item],
                source=FuelStationPriceSource.IMPORT.value,
                actor=actor,
                request_id=request_id,
            )
            inserted += result.inserted
            updated += result.updated
            skipped += result.skipped
        except Exception as exc:
            row_errors.append(FuelStationPriceImportError(row=idx, error=str(exc), raw=item.model_dump_json()))

    write_price_audit(
        db,
        station_id=station_id,
        product_code="*",
        action="IMPORT",
        actor=actor,
        source=FuelStationPriceSource.IMPORT.value,
        before=None,
        after=None,
        request_id=request_id,
        meta={"filename": file.filename, "inserted": inserted, "updated": updated, "skipped": skipped},
    )

    db.commit()
    return FuelStationPriceImportSummary(
        station_id=station_id,
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        errors=row_errors,
    )


__all__ = ["router"]
