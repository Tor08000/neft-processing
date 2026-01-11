from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.notifications import NotificationWebPushSubscription
from app.schemas.notifications import WebPushSubscriptionIn, WebPushSubscriptionLookup, WebPushSubscriptionOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/push/subscribe", response_model=WebPushSubscriptionOut)
def subscribe_webpush(
    payload: WebPushSubscriptionIn,
    db: Session = Depends(get_db),
) -> WebPushSubscriptionOut:
    existing = (
        db.query(NotificationWebPushSubscription)
        .filter(NotificationWebPushSubscription.subject_type == payload.subject_type)
        .filter(NotificationWebPushSubscription.subject_id == payload.subject_id)
        .filter(NotificationWebPushSubscription.endpoint == payload.endpoint)
        .one_or_none()
    )
    if existing:
        existing.p256dh = payload.p256dh
        existing.auth = payload.auth
        existing.user_agent = payload.user_agent
        db.commit()
        db.refresh(existing)
        return WebPushSubscriptionOut.model_validate(existing)
    subscription = NotificationWebPushSubscription(**payload.model_dump())
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return WebPushSubscriptionOut.model_validate(subscription)


@router.post("/push/unsubscribe", response_model=WebPushSubscriptionOut)
def unsubscribe_webpush(
    payload: WebPushSubscriptionLookup,
    db: Session = Depends(get_db),
) -> WebPushSubscriptionOut:
    subscription = (
        db.query(NotificationWebPushSubscription)
        .filter(NotificationWebPushSubscription.subject_type == payload.subject_type)
        .filter(NotificationWebPushSubscription.subject_id == payload.subject_id)
        .filter(NotificationWebPushSubscription.endpoint == payload.endpoint)
        .one_or_none()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="subscription_not_found")
    db.delete(subscription)
    db.commit()
    return WebPushSubscriptionOut.model_validate(subscription)
