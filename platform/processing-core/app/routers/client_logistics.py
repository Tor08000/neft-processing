from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.security.client_auth import require_client_user

router = APIRouter(prefix="/client/logistics", tags=["client-logistics"])


@router.get("/fleet")
def list_fleet(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    token: dict = Depends(require_client_user),
) -> dict:
    _ = (status, q, token)
    return {"items": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/fleet/drivers")
def list_fleet_drivers(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    token: dict = Depends(require_client_user),
) -> dict:
    _ = (status, q, token)
    return {"items": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/trips")
def list_trips(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    vehicle_id: str | None = Query(default=None),
    driver_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    token: dict = Depends(require_client_user),
) -> dict:
    _ = (status, q, date_from, date_to, vehicle_id, driver_id, token)
    return {"items": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/trips/{trip_id}")
def get_trip(trip_id: str, token: dict = Depends(require_client_user)) -> dict:
    _ = token
    return {"id": trip_id, "status": "created", "vehicle_id": None, "driver_id": None}


@router.get("/trips/{trip_id}/route")
def get_trip_route(trip_id: str, token: dict = Depends(require_client_user)) -> dict:
    _ = token
    return {"id": trip_id, "status": "created", "vehicle_id": None, "driver_id": None}


@router.get("/trips/{trip_id}/tracking")
def get_trip_tracking(
    trip_id: str,
    since: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    token: dict = Depends(require_client_user),
) -> dict:
    _ = (since, limit, token)
    return {"trip_id": trip_id, "items": [], "last": None}


@router.get("/trips/{trip_id}/position")
def get_trip_position(trip_id: str, token: dict = Depends(require_client_user)) -> dict | None:
    _ = (trip_id, token)
    return None


@router.get("/trips/{trip_id}/eta")
def get_trip_eta(trip_id: str, token: dict = Depends(require_client_user)) -> dict:
    _ = token
    return {
        "trip_id": trip_id,
        "eta_at": None,
        "eta_minutes": None,
        "updated_at": None,
        "method": None,
        "confidence": None,
    }


@router.get("/trips/{trip_id}/deviations")
def get_trip_deviations(
    trip_id: str,
    since: str | None = Query(default=None),
    until: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    type: str | None = Query(default=None),
    token: dict = Depends(require_client_user),
) -> dict:
    _ = (since, until, limit, type, token)
    return {"trip_id": trip_id, "items": []}


@router.get("/trips/{trip_id}/sla-impact")
def get_trip_sla_impact(trip_id: str, token: dict = Depends(require_client_user)) -> dict:
    _ = token
    return {
        "trip_id": trip_id,
        "impact_level": "NONE",
        "signals": [],
        "first_response_due_at": None,
        "resolve_due_at": None,
        "updated_at": None,
        "consequence": None,
    }


@router.post("/fuel/linker:run")
def run_fuel_linker(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    token: dict = Depends(require_client_user),
) -> dict:
    _ = (date_from, date_to, token)
    return {"processed": 0, "linked": 0, "unlinked": 0, "alerts_created": 0}


@router.get("/fuel")
def list_fuel(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    token: dict = Depends(require_client_user),
) -> dict:
    _ = (date_from, date_to, token)
    return {"items": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/fuel/unlinked")
def list_unlinked_fuel(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    token: dict = Depends(require_client_user),
) -> list[dict]:
    _ = (date_from, date_to, limit, offset, token)
    return []


@router.get("/fuel/alerts")
def list_fuel_alerts(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    token: dict = Depends(require_client_user),
) -> list[dict]:
    _ = (date_from, date_to, type, severity, status, limit, offset, token)
    return []


@router.get("/reports/fuel")
def fuel_report(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    group_by: str = Query(default="trip"),
    period: str | None = Query(default=None),
    token: dict = Depends(require_client_user),
) -> list[dict]:
    _ = (date_from, date_to, group_by, period, token)
    return []


@router.get("/trips/{trip_id}/fuel")
def trip_fuel(trip_id: str, token: dict = Depends(require_client_user)) -> dict:
    _ = token
    return {
        "trip_id": trip_id,
        "items": [],
        "totals": {"liters": 0, "amount": 0},
        "alerts": [],
    }


@router.post("/trips")
def create_trip(token: dict = Depends(require_client_user)) -> dict:
    _ = token
    return {"trip_id": "trip-demo", "status": "created"}


@router.get("/fuel/consumption")
def fuel_consumption(token: dict = Depends(require_client_user)) -> dict:
    _ = token
    return {"trip_id": "trip-demo", "liters": 0.0, "method": "integration_hub"}
