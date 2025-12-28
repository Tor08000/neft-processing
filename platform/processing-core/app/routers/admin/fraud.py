from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fuel import FuelFraudSignalType
from app.schemas.fraud import FraudSignalOut, StationReputationDailyOut
from app.services.admin_auth import require_admin
from app.services.fuel import repository
from app.services.policy import actor_from_token

router = APIRouter(prefix="/fraud", tags=["admin", "fraud"])


def _require_compliance_role(token: dict) -> None:
    actor = actor_from_token(token)
    if not ("COMPLIANCE" in actor.roles or any(role.startswith("ADMIN") for role in actor.roles)):
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/signals", response_model=list[FraudSignalOut])
def list_signals(
    client_id: str | None = Query(default=None),
    severity_min: int | None = Query(default=None, ge=0, le=100),
    signal_type: FuelFraudSignalType | None = Query(default=None),
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> list[FraudSignalOut]:
    _require_compliance_role(token)
    signals = repository.list_fraud_signals(
        db,
        client_id=client_id,
        signal_type=signal_type,
        severity_min=severity_min,
        start_at=from_ts,
        end_at=to_ts,
        limit=limit,
    )
    return [FraudSignalOut.model_validate(signal) for signal in signals]


@router.get("/stations/outliers", response_model=list[StationReputationDailyOut])
def list_station_outliers(
    day: date = Query(...),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> list[StationReputationDailyOut]:
    _require_compliance_role(token)
    items = repository.list_station_reputation_daily(db, day=day, limit=limit)
    return [StationReputationDailyOut.model_validate(item) for item in items]


@router.get("/vehicles/{vehicle_id}/signals", response_model=list[FraudSignalOut])
def list_vehicle_signals(
    vehicle_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    token: dict = Depends(require_admin),
) -> list[FraudSignalOut]:
    _require_compliance_role(token)
    signals = repository.list_fraud_signals(db, vehicle_id=vehicle_id, limit=limit)
    return [FraudSignalOut.model_validate(signal) for signal in signals]


__all__ = ["router"]
