from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.models.fuel import FleetNotificationOutbox, FleetNotificationOutboxStatus
from app.services.fleet_notification_dispatcher import dispatch_outbox_item

router = APIRouter(prefix="/fleet/notifications", tags=["admin", "fleet-notifications"], dependencies=[Depends(require_admin_user)])


@router.post("/outbox/{outbox_id}/replay")
def replay_notification_outbox(
    outbox_id: str,
    db: Session = Depends(get_db),
) -> dict:
    outbox = db.query(FleetNotificationOutbox).filter(FleetNotificationOutbox.id == outbox_id).one_or_none()
    if not outbox:
        raise HTTPException(status_code=404, detail="outbox_not_found")
    outbox.status = FleetNotificationOutboxStatus.PENDING
    outbox.next_attempt_at = datetime.now(timezone.utc)
    outbox.attempts = 0
    outbox.last_error = None
    outbox = dispatch_outbox_item(db, outbox_id=str(outbox.id))
    db.commit()
    return {"outbox_id": str(outbox.id), "status": outbox.status.value}


__all__ = ["router"]
