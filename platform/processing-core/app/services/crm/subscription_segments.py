from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.billing_period import BillingPeriod
from app.models.crm import (
    CRMSubscription,
    CRMSubscriptionPeriodSegment,
    CRMSubscriptionSegmentReason,
    CRMSubscriptionSegmentStatus,
    CRMSubscriptionStatus,
)
from app.db.types import new_uuid_str
from app.services.crm import repository


@dataclass(frozen=True)
class SubscriptionChangeEvent:
    event_type: CRMSubscriptionSegmentReason
    effective_at: datetime
    tariff_plan_id: str | None = None


def ensure_segments_v2(
    db: Session,
    *,
    subscription: CRMSubscription,
    period: BillingPeriod,
) -> list[CRMSubscriptionPeriodSegment]:
    existing = repository.list_subscription_segments(
        db,
        subscription_id=str(subscription.id),
        billing_period_id=str(period.id),
    )
    if existing:
        return existing
    segments = build_segments_v2(subscription=subscription, period=period)
    for segment in segments:
        repository.add_subscription_segment(db, segment, auto_commit=False)
    return segments


def build_segments_v2(
    *,
    subscription: CRMSubscription,
    period: BillingPeriod,
) -> list[CRMSubscriptionPeriodSegment]:
    period_start = period.start_at
    period_end = period.end_at
    if subscription.started_at > period_end:
        return []
    if subscription.ended_at and subscription.ended_at < period_start:
        return []
    active_start = max(subscription.started_at, period_start)
    if subscription.ended_at:
        period_end = min(period_end, subscription.ended_at)
    base_status = _resolve_initial_status(subscription, active_start)
    current_tariff = subscription.tariff_plan_id
    current_status = base_status
    current_reason = CRMSubscriptionSegmentReason.START

    events = [event for event in _load_events(subscription) if period_start <= event.effective_at <= period_end]
    segments: list[CRMSubscriptionPeriodSegment] = []
    current_start = active_start

    for event in events:
        segment_end = event.effective_at - timedelta(seconds=1)
        if current_start <= segment_end and current_status is not None:
            reason = current_reason if event.event_type != CRMSubscriptionSegmentReason.CANCEL else event.event_type
            segments.append(
                _build_segment(
                    subscription=subscription,
                    period=period,
                    start=current_start,
                    end=segment_end,
                    status=current_status,
                    tariff_plan_id=current_tariff,
                    reason=reason,
                )
            )
        if event.event_type == CRMSubscriptionSegmentReason.CANCEL:
            return segments
        current_start = event.effective_at
        current_reason = event.event_type
        if event.event_type == CRMSubscriptionSegmentReason.PAUSE:
            current_status = CRMSubscriptionSegmentStatus.PAUSED
        elif event.event_type == CRMSubscriptionSegmentReason.RESUME:
            current_status = CRMSubscriptionSegmentStatus.ACTIVE
        elif event.event_type in (CRMSubscriptionSegmentReason.UPGRADE, CRMSubscriptionSegmentReason.DOWNGRADE):
            if event.tariff_plan_id:
                current_tariff = event.tariff_plan_id

    if current_start <= period_end and current_status is not None:
        segments.append(
            _build_segment(
                subscription=subscription,
                period=period,
                start=current_start,
                end=period_end,
                status=current_status,
                tariff_plan_id=current_tariff,
                reason=current_reason,
            )
        )
    return segments


def record_subscription_change(
    db: Session,
    *,
    subscription: CRMSubscription,
    event_type: CRMSubscriptionSegmentReason,
    effective_at: datetime,
    tariff_plan_id: str | None = None,
) -> CRMSubscription:
    meta = dict(subscription.meta or {})
    events = list(meta.get("v2_events") or [])
    events.append(
        {
            "type": event_type.value,
            "effective_at": effective_at.isoformat(),
            "tariff_plan_id": tariff_plan_id,
        }
    )
    meta["v2_events"] = events
    subscription.meta = meta
    if event_type == CRMSubscriptionSegmentReason.PAUSE:
        subscription.status = CRMSubscriptionStatus.PAUSED
        subscription.paused_at = effective_at
    elif event_type == CRMSubscriptionSegmentReason.RESUME:
        subscription.status = CRMSubscriptionStatus.ACTIVE
        subscription.paused_at = None
    elif event_type == CRMSubscriptionSegmentReason.CANCEL:
        subscription.status = CRMSubscriptionStatus.CANCELLED
        subscription.ended_at = effective_at
    elif event_type in (CRMSubscriptionSegmentReason.UPGRADE, CRMSubscriptionSegmentReason.DOWNGRADE):
        if tariff_plan_id:
            subscription.tariff_plan_id = tariff_plan_id
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def _load_events(subscription: CRMSubscription) -> list[SubscriptionChangeEvent]:
    raw_events: Iterable[dict] = (subscription.meta or {}).get("v2_events") or []
    parsed: list[SubscriptionChangeEvent] = []
    for raw in raw_events:
        try:
            event_type = CRMSubscriptionSegmentReason(raw.get("type"))
        except ValueError:
            continue
        effective_at = _parse_datetime(raw.get("effective_at"))
        if effective_at is None:
            continue
        parsed.append(
            SubscriptionChangeEvent(
                event_type=event_type,
                effective_at=effective_at,
                tariff_plan_id=raw.get("tariff_plan_id"),
            )
        )
    return sorted(parsed, key=lambda item: item.effective_at)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _resolve_initial_status(subscription: CRMSubscription, start_at: datetime) -> CRMSubscriptionSegmentStatus:
    if subscription.status == CRMSubscriptionStatus.PAUSED and subscription.paused_at:
        if subscription.paused_at <= start_at:
            return CRMSubscriptionSegmentStatus.PAUSED
    return CRMSubscriptionSegmentStatus.ACTIVE


def _build_segment(
    *,
    subscription: CRMSubscription,
    period: BillingPeriod,
    start: datetime,
    end: datetime,
    status: CRMSubscriptionSegmentStatus,
    tariff_plan_id: str,
    reason: CRMSubscriptionSegmentReason,
) -> CRMSubscriptionPeriodSegment:
    return CRMSubscriptionPeriodSegment(
        id=new_uuid_str(),
        subscription_id=subscription.id,
        billing_period_id=period.id,
        tariff_plan_id=tariff_plan_id,
        segment_start=start,
        segment_end=end,
        status=status,
        days_count=_count_days(start, end),
        reason=reason,
    )


def _count_days(start_at: datetime, end_at: datetime) -> int:
    return (end_at.date() - start_at.date()).days + 1


__all__ = ["SubscriptionChangeEvent", "build_segments_v2", "ensure_segments_v2", "record_subscription_change"]
