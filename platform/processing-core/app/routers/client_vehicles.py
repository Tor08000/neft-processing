from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.vehicle_profile import (
    VehicleMileageEvent,
    VehicleMileageSource,
    VehicleOdometerSource,
    VehicleProfile,
    VehicleRecommendation,
    VehicleRecommendationStatus,
)
from app.models.vehicle_maintenance import VehicleMaintenanceDismissal, VehicleUsageProfile
from app.models.vehicle_service_records import VehicleServiceRecord
from app.schemas.vehicle_profile import (
    VehicleCreate,
    VehicleListResponse,
    VehicleMileageEventOut,
    VehicleMileageEventsResponse,
    VehicleMileageOut,
    VehicleOut,
    VehicleRecommendationOut,
    VehicleRecommendationsResponse,
    VehicleUpdate,
)
from app.schemas.vehicle_maintenance import (
    MaintenanceRecommendationOut,
    MaintenanceRecommendationsResponse,
    VehicleServiceRecordCreate,
    VehicleServiceRecordOut,
    VehicleServiceRecordsResponse,
    VehicleUsageProfileOut,
    VehicleUsageProfileUpdate,
)
from app.security.client_auth import require_client_user
from app.services.vehicle_maintenance import build_vehicle_maintenance_recommendations

router = APIRouter(prefix="/client/api/v1/vehicles", tags=["client-vehicles"])


def _require_client_id(token: dict) -> str:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="forbidden")
    return str(client_id)


def _require_tenant_id(token: dict) -> int:
    tenant_id = token.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="forbidden")
    return int(tenant_id)


def _get_vehicle(db: Session, *, vehicle_id: str, client_id: str) -> VehicleProfile:
    vehicle = db.query(VehicleProfile).filter(VehicleProfile.id == vehicle_id).first()
    if not vehicle or vehicle.client_id != client_id:
        raise HTTPException(status_code=404, detail="vehicle_not_found")
    return vehicle


@router.post("", response_model=VehicleOut)
async def create_vehicle(
    payload: VehicleCreate,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> VehicleOut:
    client_id = _require_client_id(token)
    tenant_id = _require_tenant_id(token)

    start_odometer = payload.start_odometer_km
    current_odometer = payload.current_odometer_km or start_odometer

    vehicle = VehicleProfile(
        tenant_id=tenant_id,
        client_id=client_id,
        brand=payload.brand,
        model=payload.model,
        generation=payload.generation,
        year=payload.year,
        engine_type=payload.engine_type,
        engine_volume=payload.engine_volume,
        fuel_type=payload.fuel_type,
        transmission=payload.transmission,
        drive_type=payload.drive_type,
        vin=payload.vin,
        plate_number=payload.plate_number,
        start_odometer_km=start_odometer,
        current_odometer_km=current_odometer,
        odometer_source=VehicleOdometerSource.MANUAL,
        avg_consumption_l_per_100km=payload.avg_consumption_l_per_100km,
        usage_type=payload.usage_type,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return VehicleOut.model_validate(vehicle)


@router.get("", response_model=VehicleListResponse)
async def list_vehicles(
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> VehicleListResponse:
    client_id = _require_client_id(token)
    vehicles = db.query(VehicleProfile).filter(VehicleProfile.client_id == client_id).all()
    return VehicleListResponse(items=[VehicleOut.model_validate(vehicle) for vehicle in vehicles])


@router.get("/{vehicle_id}", response_model=VehicleOut)
async def get_vehicle(
    vehicle_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> VehicleOut:
    client_id = _require_client_id(token)
    vehicle = _get_vehicle(db, vehicle_id=vehicle_id, client_id=client_id)
    return VehicleOut.model_validate(vehicle)


@router.patch("/{vehicle_id}", response_model=VehicleOut)
async def update_vehicle(
    vehicle_id: str,
    payload: VehicleUpdate,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> VehicleOut:
    client_id = _require_client_id(token)
    vehicle = _get_vehicle(db, vehicle_id=vehicle_id, client_id=client_id)

    manual_update = payload.current_odometer_km is not None
    if manual_update:
        new_value = Decimal(payload.current_odometer_km)
        odometer_before = Decimal(vehicle.current_odometer_km)
        if new_value != odometer_before:
            db.add(
                VehicleMileageEvent(
                    vehicle_id=vehicle.id,
                    source=VehicleMileageSource.MANUAL_UPDATE,
                    fuel_txn_id=None,
                    liters=None,
                    estimated_km=None,
                    odometer_before=odometer_before,
                    odometer_after=new_value,
                )
            )
            vehicle.current_odometer_km = new_value
            vehicle.odometer_source = (
                VehicleOdometerSource.MANUAL
                if vehicle.odometer_source == VehicleOdometerSource.MANUAL
                else VehicleOdometerSource.MIXED
            )

    for field in (
        "brand",
        "model",
        "generation",
        "year",
        "engine_type",
        "engine_volume",
        "fuel_type",
        "transmission",
        "drive_type",
        "vin",
        "plate_number",
        "start_odometer_km",
        "avg_consumption_l_per_100km",
        "usage_type",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(vehicle, field, value)

    db.commit()
    db.refresh(vehicle)
    return VehicleOut.model_validate(vehicle)


@router.get("/{vehicle_id}/mileage", response_model=VehicleMileageOut)
async def get_vehicle_mileage(
    vehicle_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> VehicleMileageOut:
    client_id = _require_client_id(token)
    vehicle = _get_vehicle(db, vehicle_id=vehicle_id, client_id=client_id)
    return VehicleMileageOut(
        current_odometer_km=vehicle.current_odometer_km,
        odometer_source=vehicle.odometer_source,
        avg_consumption_l_per_100km=vehicle.avg_consumption_l_per_100km,
    )


@router.get("/{vehicle_id}/events", response_model=VehicleMileageEventsResponse)
async def list_vehicle_mileage_events(
    vehicle_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> VehicleMileageEventsResponse:
    client_id = _require_client_id(token)
    vehicle = _get_vehicle(db, vehicle_id=vehicle_id, client_id=client_id)

    query = db.query(VehicleMileageEvent).filter(VehicleMileageEvent.vehicle_id == vehicle.id)
    total = query.count()
    events = (
        query.order_by(VehicleMileageEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [VehicleMileageEventOut.model_validate(event) for event in events]
    return VehicleMileageEventsResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{vehicle_id}/recommendations", response_model=VehicleRecommendationsResponse)
async def list_vehicle_recommendations(
    vehicle_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> VehicleRecommendationsResponse:
    client_id = _require_client_id(token)
    vehicle = _get_vehicle(db, vehicle_id=vehicle_id, client_id=client_id)
    items = (
        db.query(VehicleRecommendation)
        .filter(VehicleRecommendation.vehicle_id == vehicle.id)
        .order_by(VehicleRecommendation.created_at.desc())
        .all()
    )
    return VehicleRecommendationsResponse(items=[VehicleRecommendationOut.model_validate(item) for item in items])


def _update_recommendation_status(
    *,
    db: Session,
    vehicle: VehicleProfile,
    rec_id: str,
    status: VehicleRecommendationStatus,
) -> VehicleRecommendationOut:
    rec = (
        db.query(VehicleRecommendation)
        .filter(VehicleRecommendation.vehicle_id == vehicle.id)
        .filter(VehicleRecommendation.id == rec_id)
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="recommendation_not_found")
    if rec.status in {VehicleRecommendationStatus.DONE, VehicleRecommendationStatus.DISMISSED}:
        raise HTTPException(status_code=409, detail="recommendation_closed")
    rec.status = status
    db.commit()
    db.refresh(rec)
    return VehicleRecommendationOut.model_validate(rec)


@router.post("/{vehicle_id}/recommendations/{rec_id}/accept", response_model=VehicleRecommendationOut)
async def accept_vehicle_recommendation(
    vehicle_id: str,
    rec_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> VehicleRecommendationOut:
    client_id = _require_client_id(token)
    vehicle = _get_vehicle(db, vehicle_id=vehicle_id, client_id=client_id)
    return _update_recommendation_status(
        db=db,
        vehicle=vehicle,
        rec_id=rec_id,
        status=VehicleRecommendationStatus.ACCEPTED,
    )


@router.post("/{vehicle_id}/recommendations/{rec_id}/dismiss", response_model=VehicleRecommendationOut)
async def dismiss_vehicle_recommendation(
    vehicle_id: str,
    rec_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> VehicleRecommendationOut:
    client_id = _require_client_id(token)
    vehicle = _get_vehicle(db, vehicle_id=vehicle_id, client_id=client_id)
    return _update_recommendation_status(
        db=db,
        vehicle=vehicle,
        rec_id=rec_id,
        status=VehicleRecommendationStatus.DISMISSED,
    )


@router.get("/{vehicle_id}/usage", response_model=VehicleUsageProfileOut)
async def get_vehicle_usage_profile(
    vehicle_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> VehicleUsageProfileOut:
    client_id = _require_client_id(token)
    vehicle = _get_vehicle(db, vehicle_id=vehicle_id, client_id=client_id)
    profile = (
        db.query(VehicleUsageProfile)
        .filter(VehicleUsageProfile.vehicle_id == vehicle.id)
        .one_or_none()
    )
    if not profile:
        profile = VehicleUsageProfile(vehicle_id=vehicle.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return VehicleUsageProfileOut.model_validate(profile)


@router.patch("/{vehicle_id}/usage", response_model=VehicleUsageProfileOut)
async def update_vehicle_usage_profile(
    vehicle_id: str,
    payload: VehicleUsageProfileUpdate,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> VehicleUsageProfileOut:
    client_id = _require_client_id(token)
    vehicle = _get_vehicle(db, vehicle_id=vehicle_id, client_id=client_id)
    profile = (
        db.query(VehicleUsageProfile)
        .filter(VehicleUsageProfile.vehicle_id == vehicle.id)
        .one_or_none()
    )
    if not profile:
        profile = VehicleUsageProfile(vehicle_id=vehicle.id)
        db.add(profile)

    for field in (
        "usage_type",
        "aggressiveness_score",
        "heavy_load_flag",
        "climate_zone",
        "avg_monthly_km",
        "avg_consumption_l_100",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return VehicleUsageProfileOut.model_validate(profile)


@router.get("/{vehicle_id}/service-records", response_model=VehicleServiceRecordsResponse)
async def list_vehicle_service_records(
    vehicle_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> VehicleServiceRecordsResponse:
    client_id = _require_client_id(token)
    vehicle = _get_vehicle(db, vehicle_id=vehicle_id, client_id=client_id)
    query = db.query(VehicleServiceRecord).filter(VehicleServiceRecord.vehicle_id == vehicle.id)
    total = query.count()
    records = (
        query.order_by(VehicleServiceRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [VehicleServiceRecordOut.model_validate(record) for record in records]
    return VehicleServiceRecordsResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/{vehicle_id}/service-records", response_model=VehicleServiceRecordOut)
async def create_vehicle_service_record(
    vehicle_id: str,
    payload: VehicleServiceRecordCreate,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> VehicleServiceRecordOut:
    client_id = _require_client_id(token)
    vehicle = _get_vehicle(db, vehicle_id=vehicle_id, client_id=client_id)
    record = VehicleServiceRecord(
        vehicle_id=vehicle.id,
        item_code=payload.item_code,
        service_at_km=payload.service_at_km,
        service_at=payload.service_at,
        partner_id=payload.partner_id,
        order_id=payload.order_id,
        note=payload.note,
        source=payload.source,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return VehicleServiceRecordOut.model_validate(record)


@router.get("/{vehicle_id}/maintenance", response_model=MaintenanceRecommendationsResponse)
async def list_vehicle_maintenance_recommendations(
    vehicle_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> MaintenanceRecommendationsResponse:
    client_id = _require_client_id(token)
    vehicle = _get_vehicle(db, vehicle_id=vehicle_id, client_id=client_id)
    recommendations = build_vehicle_maintenance_recommendations(db, vehicle=vehicle)
    items = [
        MaintenanceRecommendationOut(
            item_code=payload.item.code,
            title=payload.item.title,
            status=payload.status,
            interval_km=payload.interval_km,
            interval_months=payload.interval_months,
            effective_interval_km=payload.effective_interval_km,
            effective_interval_months=payload.effective_interval_months,
            last_service_km=payload.last_service_km,
            last_service_at=payload.last_service_at,
            current_km=payload.current_km,
            due_km=payload.due_km,
            due_in_km=payload.due_in_km,
            overdue_km=payload.overdue_km,
            due_at=payload.due_at,
            due_in_months=payload.due_in_months,
            explain=payload.explain,
        )
        for payload in recommendations
    ]
    return MaintenanceRecommendationsResponse(items=items)


@router.post("/{vehicle_id}/maintenance/{rec_id}/dismiss")
async def dismiss_vehicle_maintenance_recommendation(
    vehicle_id: str,
    rec_id: str,
    token: dict = Depends(require_client_user),
    db: Session = Depends(get_db),
) -> None:
    client_id = _require_client_id(token)
    vehicle = _get_vehicle(db, vehicle_id=vehicle_id, client_id=client_id)
    dismissal = VehicleMaintenanceDismissal(vehicle_id=vehicle.id, item_code=rec_id)
    db.add(dismissal)
    db.commit()
    return None
