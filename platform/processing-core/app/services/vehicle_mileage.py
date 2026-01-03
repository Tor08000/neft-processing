from __future__ import annotations

from decimal import Decimal
import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.fuel import FuelTransaction
from app.models.vehicle_profile import (
    ServiceInterval,
    VehicleCardLink,
    VehicleMileageEvent,
    VehicleMileageSource,
    VehicleOdometerSource,
    VehicleProfile,
    VehicleRecommendation,
    VehicleRecommendationStatus,
    VehicleServiceType,
)

logger = logging.getLogger(__name__)

_DEFAULT_CONSUMPTION: dict[str, Decimal] = {
    "petrol": Decimal("9.0"),
    "diesel": Decimal("8.0"),
    "hybrid": Decimal("6.5"),
}

_SERVICE_THRESHOLDS_KM: dict[VehicleServiceType, Decimal] = {
    VehicleServiceType.OIL_CHANGE: Decimal("750"),
    VehicleServiceType.FILTERS: Decimal("1000"),
    VehicleServiceType.BRAKES: Decimal("2000"),
    VehicleServiceType.TIMING: Decimal("1500"),
    VehicleServiceType.OTHER: Decimal("500"),
}


def _resolve_vehicle_for_tx(db: Session, transaction: FuelTransaction) -> VehicleProfile | None:
    if not transaction.card_id:
        return None
    link = (
        db.query(VehicleCardLink)
        .join(VehicleProfile, VehicleProfile.id == VehicleCardLink.vehicle_id)
        .filter(VehicleCardLink.card_id == transaction.card_id)
        .filter(VehicleProfile.client_id == transaction.client_id)
        .first()
    )
    if link:
        return db.query(VehicleProfile).filter(VehicleProfile.id == link.vehicle_id).first()
    return None


def _resolve_avg_consumption(vehicle: VehicleProfile) -> Decimal | None:
    if vehicle.avg_consumption_l_per_100km:
        return Decimal(vehicle.avg_consumption_l_per_100km)
    if vehicle.engine_type:
        return _DEFAULT_CONSUMPTION.get(vehicle.engine_type.value)
    return None


def _ensure_recommendations(
    db: Session,
    *,
    vehicle: VehicleProfile,
    current_km: Decimal,
) -> None:
    intervals = (
        db.query(ServiceInterval)
        .filter(or_(ServiceInterval.brand.is_(None), ServiceInterval.brand == vehicle.brand))
        .filter(or_(ServiceInterval.model.is_(None), ServiceInterval.model == vehicle.model))
    )
    if vehicle.engine_type:
        intervals = intervals.filter(
            or_(ServiceInterval.engine_type.is_(None), ServiceInterval.engine_type == vehicle.engine_type)
        )
    intervals = intervals.all()

    if not intervals:
        return

    for interval in intervals:
        threshold = _SERVICE_THRESHOLDS_KM.get(interval.service_type, Decimal("500"))
        target_km = Decimal(interval.interval_km) if interval.interval_km is not None else None
        if not target_km:
            continue
        recommended_at = Decimal(vehicle.start_odometer_km) + target_km
        if current_km < recommended_at - threshold:
            continue

        existing = (
            db.query(VehicleRecommendation)
            .filter(VehicleRecommendation.vehicle_id == vehicle.id)
            .filter(VehicleRecommendation.service_type == interval.service_type)
            .filter(VehicleRecommendation.status.in_([VehicleRecommendationStatus.ACTIVE, VehicleRecommendationStatus.ACCEPTED]))
            .first()
        )
        if existing:
            continue

        distance_since_start = current_km - Decimal(vehicle.start_odometer_km)
        reason = (
            f"Вы проехали {distance_since_start:.0f} км с момента старта пробега. "
            f"Рекомендуемый интервал: {target_km:.0f} км."
        )
        db.add(
            VehicleRecommendation(
                vehicle_id=vehicle.id,
                service_type=interval.service_type,
                recommended_at_km=recommended_at,
                current_km=current_km,
                status=VehicleRecommendationStatus.ACTIVE,
                reason=reason,
                partner_id=None,
            )
        )


def apply_fuel_transaction_mileage(db: Session, *, transaction: FuelTransaction) -> None:
    try:
        vehicle = _resolve_vehicle_for_tx(db, transaction)
        if not vehicle:
            return
        if transaction.volume_liters is None:
            return
        liters = Decimal(transaction.volume_liters)
        if liters <= 0:
            return
        avg_consumption = _resolve_avg_consumption(vehicle)
        if not avg_consumption or avg_consumption <= 0:
            return

        estimated_km = (liters / avg_consumption) * Decimal("100")
        odometer_before = Decimal(vehicle.current_odometer_km)
        odometer_after = odometer_before + estimated_km

        db.add(
            VehicleMileageEvent(
                vehicle_id=vehicle.id,
                source=VehicleMileageSource.FUEL_TXN,
                fuel_txn_id=transaction.id,
                liters=liters,
                estimated_km=estimated_km,
                odometer_before=odometer_before,
                odometer_after=odometer_after,
            )
        )
        vehicle.current_odometer_km = odometer_after
        if vehicle.odometer_source == VehicleOdometerSource.MANUAL:
            vehicle.odometer_source = VehicleOdometerSource.MIXED
        else:
            vehicle.odometer_source = VehicleOdometerSource.ESTIMATED
        if vehicle.avg_consumption_l_per_100km is None:
            vehicle.avg_consumption_l_per_100km = avg_consumption

        _ensure_recommendations(db, vehicle=vehicle, current_km=odometer_after)
    except Exception:  # noqa: BLE001 - mileage should not block settlement
        logger.exception("Failed to apply fuel mileage update", extra={"transaction_id": str(transaction.id)})
