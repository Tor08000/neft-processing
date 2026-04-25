from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.notifications import (
    NotificationChannel,
    NotificationDelivery,
    NotificationPreference,
    NotificationTemplate,
)
from app.schemas.notifications import (
    NotificationDeliveryOut,
    NotificationMessageIn,
    NotificationMessageOut,
    NotificationPreferenceIn,
    NotificationPreferenceOut,
    NotificationTemplateIn,
    NotificationTemplateOut,
)
from app.services.notifications_v1 import dispatch_pending_notifications, enqueue_notification_message, replay_delivery

router = APIRouter(prefix="/notifications", tags=["admin-notifications"])


def _is_notification_template_code_conflict(exc: IntegrityError) -> bool:
    message = str(getattr(exc, "orig", exc)).lower()
    return (
        "uq_notification_templates_code" in message
        or "notification_templates_code_key" in message
        or "unique constraint failed: notification_templates.code" in message
    )


@router.post("/preferences", response_model=NotificationPreferenceOut)
def create_notification_preference(
    payload: NotificationPreferenceIn,
    db: Session = Depends(get_db),
) -> NotificationPreferenceOut:
    pref = NotificationPreference(**payload.model_dump())
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return NotificationPreferenceOut.model_validate(pref)


@router.get("/preferences", response_model=list[NotificationPreferenceOut])
def list_notification_preferences(
    subject_type: str | None = Query(None),
    subject_id: str | None = Query(None),
    event_type: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[NotificationPreferenceOut]:
    query = db.query(NotificationPreference)
    if subject_type:
        query = query.filter(NotificationPreference.subject_type == subject_type)
    if subject_id:
        query = query.filter(NotificationPreference.subject_id == subject_id)
    if event_type:
        query = query.filter(NotificationPreference.event_type == event_type)
    return [NotificationPreferenceOut.model_validate(pref) for pref in query.order_by(NotificationPreference.created_at)]


@router.post("/templates", response_model=NotificationTemplateOut)
def create_notification_template(
    payload: NotificationTemplateIn,
    db: Session = Depends(get_db),
) -> NotificationTemplateOut:
    template = NotificationTemplate(**payload.model_dump())
    db.add(template)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_notification_template_code_conflict(exc):
            raise HTTPException(status_code=409, detail="notification_template_code_conflict") from exc
        raise
    db.refresh(template)
    return NotificationTemplateOut.model_validate(template)


@router.get("/templates", response_model=list[NotificationTemplateOut])
def list_notification_templates(
    event_type: str | None = Query(None),
    channel: NotificationChannel | None = Query(None),
    db: Session = Depends(get_db),
) -> list[NotificationTemplateOut]:
    query = db.query(NotificationTemplate)
    if event_type:
        query = query.filter(NotificationTemplate.event_type == event_type)
    if channel:
        query = query.filter(NotificationTemplate.channel == channel)
    return [NotificationTemplateOut.model_validate(template) for template in query.order_by(NotificationTemplate.created_at)]


@router.post("/outbox", response_model=NotificationMessageOut)
def create_notification_message(
    payload: NotificationMessageIn,
    db: Session = Depends(get_db),
) -> NotificationMessageOut:
    message = enqueue_notification_message(
        db,
        event_type=payload.event_type,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        channels=payload.channels,
        template_code=payload.template_code,
        template_vars=payload.template_vars,
        priority=payload.priority,
        dedupe_key=payload.dedupe_key,
    )
    db.commit()
    db.refresh(message)
    return NotificationMessageOut.model_validate(message)


@router.post("/dispatch", response_model=list[NotificationMessageOut])
def dispatch_notifications(
    db: Session = Depends(get_db),
) -> list[NotificationMessageOut]:
    messages = dispatch_pending_notifications(db)
    db.commit()
    return [NotificationMessageOut.model_validate(message) for message in messages]


@router.get("/deliveries", response_model=list[NotificationDeliveryOut])
def list_notification_deliveries(
    event_type: str | None = Query(None),
    channel: NotificationChannel | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[NotificationDeliveryOut]:
    query = db.query(NotificationDelivery)
    if event_type:
        query = query.filter(NotificationDelivery.event_type == event_type)
    if channel:
        query = query.filter(NotificationDelivery.channel == channel)
    if status:
        query = query.filter(NotificationDelivery.status == status)
    return [NotificationDeliveryOut.model_validate(item) for item in query.order_by(NotificationDelivery.created_at)]


@router.post("/deliveries/{delivery_id}/replay", response_model=NotificationDeliveryOut | None)
def replay_notification_delivery(
    delivery_id: str,
    db: Session = Depends(get_db),
) -> NotificationDeliveryOut | None:
    delivery = replay_delivery(db, delivery_id)
    if delivery is None:
        return None
    db.commit()
    db.refresh(delivery)
    return NotificationDeliveryOut.model_validate(delivery)
