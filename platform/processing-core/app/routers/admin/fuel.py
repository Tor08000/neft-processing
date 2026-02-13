from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fleet import FleetDriver, FleetVehicle
from app.models.fuel import (
    FuelAnalyticsEvent,
    FuelCard,
    FuelCardGroup,
    FuelLimit,
    FuelNetwork,
    FuelStation,
    FuelStationNetwork,
    FuelTransaction,
    FuelTransactionStatus,
)
from app.schemas.fleet import (
    CardCreate,
    CardOut,
    DriverCreate,
    DriverOut,
    LimitCreate,
    LimitOut,
    VehicleCreate,
    VehicleOut,
)
from app.schemas.fuel import (
    FuelCardGroupCreate,
    FuelCardGroupOut,
    FuelNetworkCreate,
    FuelNetworkOut,
    FuelStationCreate,
    FuelStationOut,
    FuelStationNetworkCreate,
    FuelStationNetworkOut,
    DeclineCode,
)
from app.services.admin_auth import require_admin
from app.services.audit_service import request_context_from_request
from app.services.fuel import events
from app.services.policy import actor_from_token

router = APIRouter(prefix="/fuel", tags=["admin", "fuel"])

_REVIEW_ROLES = {"FINANCE", "SUPERVISOR", "ADMIN_FINANCE", "ADMIN_SUPERVISOR", "SUPERADMIN"}


def _require_review_role(token: dict) -> None:
    actor = actor_from_token(token)
    if not actor.roles.intersection(_REVIEW_ROLES):
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/health", response_model=dict)
def fuel_health(request: Request, db: Session = Depends(get_db), token: dict = Depends(require_admin)) -> dict:
    _require_review_role(token)
    orphan_settled = (
        db.query(FuelTransaction)
        .filter(FuelTransaction.status == FuelTransactionStatus.SETTLED)
        .filter(FuelTransaction.ledger_transaction_id.is_(None))
        .count()
    )
    missing_risk = (
        db.query(FuelTransaction)
        .filter(FuelTransaction.status.in_([FuelTransactionStatus.AUTHORIZED, FuelTransactionStatus.REVIEW_REQUIRED]))
        .filter(FuelTransaction.risk_decision_id.is_(None))
        .count()
    )
    active_limits = db.query(FuelLimit).filter(FuelLimit.active.is_(True)).count()
    analytics_backlog = db.query(FuelAnalyticsEvent).count()

    issues = []
    if orphan_settled:
        issues.append({"type": "orphan_settled", "count": orphan_settled})
    if missing_risk:
        issues.append({"type": "missing_risk_decision", "count": missing_risk})
    if active_limits == 0:
        issues.append({"type": "missing_limit_configs", "count": 0})
    if analytics_backlog:
        issues.append({"type": "analytics_backlog", "count": analytics_backlog})

    return {
        "status": "ok" if not issues else "degraded",
        "issues": issues,
        "stats": {
            "orphan_settled": orphan_settled,
            "missing_risk_decision": missing_risk,
            "active_limits": active_limits,
            "analytics_backlog": analytics_backlog,
        },
    }


@router.post("/transactions/{transaction_id}/approve", response_model=dict)
def approve_review_transaction(
    transaction_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> dict:
    _require_review_role(token)
    tx = db.query(FuelTransaction).filter(FuelTransaction.id == transaction_id).one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="transaction not found")
    if tx.status != FuelTransactionStatus.REVIEW_REQUIRED:
        raise HTTPException(status_code=400, detail="transaction not in review")
    tx.status = FuelTransactionStatus.AUTHORIZED
    tx.decline_code = None
    db.commit()
    db.refresh(tx)
    ctx = request_context_from_request(request, token=token)
    events.audit_event(
        db,
        event_type=events.FUEL_EVENT_REVIEW_APPROVED,
        entity_id=str(tx.id),
        payload={"status": tx.status.value},
        request_ctx=ctx,
    )
    return {"status": "approved", "transaction_id": str(tx.id)}


@router.post("/transactions/{transaction_id}/reject", response_model=dict)
def reject_review_transaction(
    transaction_id: str,
    request: Request,
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> dict:
    _require_review_role(token)
    tx = db.query(FuelTransaction).filter(FuelTransaction.id == transaction_id).one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="transaction not found")
    if tx.status != FuelTransactionStatus.REVIEW_REQUIRED:
        raise HTTPException(status_code=400, detail="transaction not in review")
    tx.status = FuelTransactionStatus.DECLINED
    tx.decline_code = DeclineCode.RISK_REVIEW_REQUIRED.value
    db.commit()
    db.refresh(tx)
    ctx = request_context_from_request(request, token=token)
    events.audit_event(
        db,
        event_type=events.FUEL_EVENT_REVIEW_REJECTED,
        entity_id=str(tx.id),
        payload={"status": tx.status.value, "decline_code": tx.decline_code},
        request_ctx=ctx,
    )
    return {"status": "rejected", "transaction_id": str(tx.id)}


@router.post("/networks", response_model=FuelNetworkOut)
def create_network(payload: FuelNetworkCreate, db: Session = Depends(get_db)) -> FuelNetworkOut:
    network = FuelNetwork(
        name=payload.name,
        provider_code=payload.provider_code,
        status=payload.status,
    )
    db.add(network)
    db.commit()
    db.refresh(network)
    return FuelNetworkOut.model_validate(network)


@router.get("/networks", response_model=list[FuelNetworkOut])
def list_networks(db: Session = Depends(get_db)) -> list[FuelNetworkOut]:
    return [FuelNetworkOut.model_validate(item) for item in db.query(FuelNetwork).all()]


@router.post("/stations", response_model=FuelStationOut)
def create_station(payload: FuelStationCreate, db: Session = Depends(get_db)) -> FuelStationOut:
    station = FuelStation(
        network_id=payload.network_id,
        station_network_id=payload.station_network_id,
        station_code=payload.station_code,
        name=payload.name,
        country=payload.country,
        region=payload.region,
        city=payload.city,
        lat=payload.lat,
        lon=payload.lon,
        nav_url=payload.nav_url,
        geo_hash=payload.geo_hash,
        status=payload.status,
    )
    db.add(station)
    db.commit()
    db.refresh(station)
    return FuelStationOut.model_validate(station)


@router.get("/stations", response_model=list[FuelStationOut])
def list_stations(db: Session = Depends(get_db)) -> list[FuelStationOut]:
    return [FuelStationOut.model_validate(item) for item in db.query(FuelStation).all()]


@router.post("/station-networks", response_model=FuelStationNetworkOut)
def create_station_network(
    payload: FuelStationNetworkCreate, db: Session = Depends(get_db)
) -> FuelStationNetworkOut:
    station_network = FuelStationNetwork(name=payload.name, meta=payload.meta)
    db.add(station_network)
    db.commit()
    db.refresh(station_network)
    return FuelStationNetworkOut.model_validate(station_network)


@router.get("/station-networks", response_model=list[FuelStationNetworkOut])
def list_station_networks(db: Session = Depends(get_db)) -> list[FuelStationNetworkOut]:
    return [FuelStationNetworkOut.model_validate(item) for item in db.query(FuelStationNetwork).all()]


@router.post("/card-groups", response_model=FuelCardGroupOut)
def create_card_group(payload: FuelCardGroupCreate, db: Session = Depends(get_db)) -> FuelCardGroupOut:
    group = FuelCardGroup(
        tenant_id=payload.tenant_id,
        client_id=payload.client_id,
        name=payload.name,
        status=payload.status,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return FuelCardGroupOut.model_validate(group)


@router.get("/card-groups", response_model=list[FuelCardGroupOut])
def list_card_groups(db: Session = Depends(get_db)) -> list[FuelCardGroupOut]:
    return [FuelCardGroupOut.model_validate(item) for item in db.query(FuelCardGroup).all()]


@router.post("/cards", response_model=CardOut)
def create_card(payload: CardCreate, db: Session = Depends(get_db)) -> CardOut:
    card = FuelCard(
        tenant_id=payload.tenant_id,
        client_id=payload.client_id,
        card_token=payload.card_token,
        status=payload.status,
        card_group_id=payload.card_group_id,
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
        issued_at=payload.issued_at,
        blocked_at=payload.blocked_at,
        meta=payload.meta,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return CardOut.model_validate(card)


@router.get("/cards", response_model=list[CardOut])
def list_cards(db: Session = Depends(get_db)) -> list[CardOut]:
    return [CardOut.model_validate(item) for item in db.query(FuelCard).all()]


@router.post("/vehicles", response_model=VehicleOut)
def create_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)) -> VehicleOut:
    vehicle = FleetVehicle(**payload.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return VehicleOut.model_validate(vehicle)


@router.get("/vehicles", response_model=list[VehicleOut])
def list_vehicles(db: Session = Depends(get_db)) -> list[VehicleOut]:
    return [VehicleOut.model_validate(item) for item in db.query(FleetVehicle).all()]


@router.post("/drivers", response_model=DriverOut)
def create_driver(payload: DriverCreate, db: Session = Depends(get_db)) -> DriverOut:
    driver = FleetDriver(**payload.model_dump())
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return DriverOut.model_validate(driver)


@router.get("/drivers", response_model=list[DriverOut])
def list_drivers(db: Session = Depends(get_db)) -> list[DriverOut]:
    return [DriverOut.model_validate(item) for item in db.query(FleetDriver).all()]


@router.post("/limits", response_model=LimitOut)
def create_limit(payload: LimitCreate, db: Session = Depends(get_db)) -> LimitOut:
    limit = FuelLimit(**payload.model_dump())
    db.add(limit)
    db.commit()
    db.refresh(limit)
    return LimitOut.model_validate(limit)


@router.get("/limits", response_model=list[LimitOut])
def list_limits(db: Session = Depends(get_db)) -> list[LimitOut]:
    return [LimitOut.model_validate(item) for item in db.query(FuelLimit).all()]


@router.delete("/limits/{limit_id}", response_model=dict)
def delete_limit(limit_id: str, db: Session = Depends(get_db)) -> dict:
    limit = db.query(FuelLimit).filter(FuelLimit.id == limit_id).one_or_none()
    if not limit:
        raise HTTPException(status_code=404, detail="limit not found")
    db.delete(limit)
    db.commit()
    return {"status": "deleted"}
