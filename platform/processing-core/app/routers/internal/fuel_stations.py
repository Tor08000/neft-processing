from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fuel import FuelStation
from app.schemas.fuel import FuelStationHeartbeatIn, FuelStationOut

router = APIRouter(prefix="/api/v1/internal/fuel/stations", tags=["internal-fuel-stations"])


@router.post("/{station_id}/heartbeat", response_model=FuelStationOut)
def station_heartbeat(station_id: str, payload: FuelStationHeartbeatIn, db: Session = Depends(get_db)) -> FuelStationOut:
    station = db.query(FuelStation).filter(FuelStation.id == station_id).one_or_none()
    if station is None:
        raise HTTPException(status_code=404, detail="station_not_found")

    station.health_status = payload.status.value
    station.health_source = payload.source.value
    station.last_heartbeat = datetime.now(timezone.utc)
    station.health_updated_at = station.last_heartbeat
    station.health_updated_by = payload.terminal_id or "integration"
    station.health_reason = None
    db.commit()
    db.refresh(station)
    return FuelStationOut.model_validate(station)
