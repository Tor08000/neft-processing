from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.cases import Case, CaseEventType, CaseKind, CasePriority
from app.models.vehicle_profile import (
    VehicleProfile,
    VehicleRecommendation,
    VehicleRecommendationStatus,
    VehicleServiceType,
)
from app.models.service_bookings import (
    BookingPaymentStatus,
    BookingSlotLock,
    PartnerResource,
    PartnerResourceStatus,
    PartnerService,
    PartnerServiceCalendar,
    PartnerServiceStatus,
    ServiceAvailabilityRule,
    ServiceBooking,
    ServiceBookingActorType,
    ServiceBookingEvent,
    ServiceBookingEventType,
    ServiceBookingStatus,
    VehicleServiceRecord,
)
from app.services.audit_service import RequestContext
from app.services.case_event_redaction import redact_deep
from app.services.case_events_service import CaseEventActor, emit_case_event


class ServiceBookingServiceError(ValueError):
    def __init__(self, code: str, *, detail: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail or {}


@dataclass(frozen=True)
class BookingTransition:
    event_type: ServiceBookingEventType
    from_statuses: set[ServiceBookingStatus]
    to_status: ServiceBookingStatus | None


BOOKING_TRANSITIONS = {
    ServiceBookingEventType.CONFIRMED: BookingTransition(
        event_type=ServiceBookingEventType.CONFIRMED,
        from_statuses={ServiceBookingStatus.REQUESTED},
        to_status=ServiceBookingStatus.CONFIRMED,
    ),
    ServiceBookingEventType.DECLINED: BookingTransition(
        event_type=ServiceBookingEventType.DECLINED,
        from_statuses={ServiceBookingStatus.REQUESTED},
        to_status=ServiceBookingStatus.DECLINED,
    ),
    ServiceBookingEventType.CANCELED: BookingTransition(
        event_type=ServiceBookingEventType.CANCELED,
        from_statuses={ServiceBookingStatus.REQUESTED, ServiceBookingStatus.CONFIRMED},
        to_status=ServiceBookingStatus.CANCELED,
    ),
    ServiceBookingEventType.STARTED: BookingTransition(
        event_type=ServiceBookingEventType.STARTED,
        from_statuses={ServiceBookingStatus.CONFIRMED},
        to_status=ServiceBookingStatus.IN_PROGRESS,
    ),
    ServiceBookingEventType.COMPLETED: BookingTransition(
        event_type=ServiceBookingEventType.COMPLETED,
        from_statuses={ServiceBookingStatus.IN_PROGRESS},
        to_status=ServiceBookingStatus.COMPLETED,
    ),
    ServiceBookingEventType.NO_SHOW: BookingTransition(
        event_type=ServiceBookingEventType.NO_SHOW,
        from_statuses={ServiceBookingStatus.CONFIRMED},
        to_status=ServiceBookingStatus.NO_SHOW,
    ),
}


EVENT_CASE_EVENT_MAP = {
    ServiceBookingEventType.CREATED: CaseEventType.BOOKING_CREATED,
    ServiceBookingEventType.SLOT_LOCKED: CaseEventType.SLOT_LOCKED,
    ServiceBookingEventType.CONFIRMED: CaseEventType.BOOKING_CONFIRMED,
    ServiceBookingEventType.DECLINED: CaseEventType.BOOKING_DECLINED,
    ServiceBookingEventType.CANCELED: CaseEventType.BOOKING_CANCELED,
    ServiceBookingEventType.STARTED: CaseEventType.BOOKING_STATUS_CHANGED,
    ServiceBookingEventType.RESCHEDULED: CaseEventType.BOOKING_STATUS_CHANGED,
    ServiceBookingEventType.PAID: CaseEventType.BOOKING_STATUS_CHANGED,
    ServiceBookingEventType.REFUNDED: CaseEventType.BOOKING_STATUS_CHANGED,
    ServiceBookingEventType.NO_SHOW: CaseEventType.BOOKING_STATUS_CHANGED,
    ServiceBookingEventType.COMPLETED: CaseEventType.BOOKING_COMPLETED,
}


class ServiceBookingService:
    def __init__(self, db: Session, *, request_ctx: RequestContext | None = None) -> None:
        self.db = db
        self.request_ctx = request_ctx

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _tenant_id(self) -> int:
        return int(self.request_ctx.tenant_id) if self.request_ctx and self.request_ctx.tenant_id is not None else 0

    def _case_actor(self) -> CaseEventActor | None:
        if not self.request_ctx:
            return None
        return CaseEventActor(id=self.request_ctx.actor_id, email=self.request_ctx.actor_email)

    def _ensure_booking_case(self, *, booking: ServiceBooking) -> Case:
        existing = (
            self.db.query(Case)
            .filter(Case.kind == CaseKind.BOOKING)
            .filter(Case.entity_id == str(booking.id))
            .one_or_none()
        )
        if existing:
            return existing
        case = Case(
            id=new_uuid_str(),
            tenant_id=self._tenant_id(),
            kind=CaseKind.BOOKING,
            entity_id=str(booking.id),
            title=f"Service booking {booking.booking_number}",
            priority=CasePriority.MEDIUM,
            created_by=self.request_ctx.actor_id if self.request_ctx else None,
        )
        self.db.add(case)
        self.db.flush()
        return case

    def _emit_booking_event(
        self,
        *,
        booking: ServiceBooking,
        event_type: ServiceBookingEventType,
        payload: dict,
        actor_type: ServiceBookingActorType,
        actor_id: str | None,
    ) -> ServiceBookingEvent:
        case = self._ensure_booking_case(booking=booking)
        case_event_type = EVENT_CASE_EVENT_MAP.get(event_type, CaseEventType.BOOKING_STATUS_CHANGED)
        case_event = emit_case_event(
            self.db,
            case_id=str(case.id),
            event_type=case_event_type,
            actor=self._case_actor(),
            request_id=self.request_ctx.request_id if self.request_ctx else None,
            trace_id=self.request_ctx.trace_id if self.request_ctx else None,
            extra_payload={
                "booking_id": str(booking.id),
                "event": event_type.value,
            },
        )
        booking_event = ServiceBookingEvent(
            id=new_uuid_str(),
            tenant_id=self._tenant_id(),
            booking_id=booking.id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=redact_deep(payload, "", include_hash=True),
            audit_event_id=case_event.id,
        )
        self.db.add(booking_event)
        return booking_event

    def _ensure_transition(self, booking: ServiceBooking, event_type: ServiceBookingEventType) -> ServiceBookingStatus | None:
        transition = BOOKING_TRANSITIONS.get(event_type)
        if not transition:
            return None
        current_status = ServiceBookingStatus(booking.status)
        if current_status not in transition.from_statuses:
            raise ServiceBookingServiceError(
                "invalid_transition",
                detail={"from": current_status.value, "event": event_type.value},
            )
        return transition.to_status

    def _apply_transition(self, booking: ServiceBooking, *, event_type: ServiceBookingEventType) -> None:
        target_status = self._ensure_transition(booking, event_type)
        if target_status is not None:
            booking.status = target_status.value
            booking.updated_at = self._now()

    def _get_service(self, *, service_id: str, partner_id: str | None = None) -> PartnerService:
        query = self.db.query(PartnerService).filter(PartnerService.id == service_id)
        if partner_id:
            query = query.filter(PartnerService.partner_id == partner_id)
        service = query.one_or_none()
        if not service:
            raise ServiceBookingServiceError("service_not_found")
        if service.status != PartnerServiceStatus.ACTIVE:
            raise ServiceBookingServiceError("service_not_active")
        return service

    def _get_calendar(self, *, partner_id: str) -> PartnerServiceCalendar | None:
        return (
            self.db.query(PartnerServiceCalendar)
            .filter(PartnerServiceCalendar.partner_id == partner_id)
            .order_by(PartnerServiceCalendar.created_at.desc())
            .first()
        )

    def _get_availability_rule(self, *, service_id: str, partner_id: str) -> ServiceAvailabilityRule | None:
        return (
            self.db.query(ServiceAvailabilityRule)
            .filter(ServiceAvailabilityRule.service_id == service_id)
            .filter(ServiceAvailabilityRule.partner_id == partner_id)
            .one_or_none()
        )

    def _build_price_snapshot(self, *, service: PartnerService, coupon_code: str | None = None) -> dict:
        base_price = Decimal(str(service.base_price))
        return {
            "service_id": str(service.id),
            "base_price": str(base_price),
            "discount": "0",
            "final_price": str(base_price),
            "currency": service.currency,
            "coupon_code": coupon_code,
        }

    def _generate_booking_number(self) -> str:
        return f"BK-{new_uuid_str().replace('-', '')[:12].upper()}"

    @staticmethod
    def _day_key(date_value: datetime) -> str:
        return ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][date_value.weekday()]

    def _iter_working_intervals(self, *, date_value: datetime, calendar: PartnerServiceCalendar) -> Iterable[tuple[datetime, datetime]]:
        schedule = calendar.working_hours or {}
        day_key = self._day_key(date_value)
        intervals = schedule.get(day_key, [])
        tz = ZoneInfo(calendar.timezone)
        for interval in intervals:
            start_str = interval.get("from")
            end_str = interval.get("to")
            if not start_str or not end_str:
                continue
            start_parts = [int(part) for part in start_str.split(":")]
            end_parts = [int(part) for part in end_str.split(":")]
            start_time = time(start_parts[0], start_parts[1], tzinfo=tz)
            end_time = time(end_parts[0], end_parts[1], tzinfo=tz)
            start_dt = datetime.combine(date_value.date(), start_time)
            end_dt = datetime.combine(date_value.date(), end_time)
            if end_dt <= start_dt:
                continue
            yield start_dt, end_dt

    def _is_holiday(self, *, date_value: datetime, calendar: PartnerServiceCalendar) -> bool:
        holidays = calendar.holidays or {}
        holiday_dates = set(holidays.get("dates", []) or [])
        return date_value.date().isoformat() in holiday_dates

    def _collect_conflicts(
        self,
        *,
        partner_id: str,
        service_id: str,
        starts_at: datetime,
        ends_at: datetime,
        now: datetime,
    ) -> tuple[dict[str | None, list[tuple[datetime, datetime]]], dict[str | None, list[tuple[datetime, datetime]]]]:
        active_statuses = [
            ServiceBookingStatus.REQUESTED.value,
            ServiceBookingStatus.CONFIRMED.value,
            ServiceBookingStatus.IN_PROGRESS.value,
        ]
        bookings = (
            self.db.query(ServiceBooking)
            .filter(ServiceBooking.partner_id == partner_id)
            .filter(ServiceBooking.service_id == service_id)
            .filter(ServiceBooking.status.in_(active_statuses))
            .filter(ServiceBooking.starts_at < ends_at)
            .filter(ServiceBooking.ends_at > starts_at)
            .all()
        )
        locks = (
            self.db.query(BookingSlotLock)
            .filter(BookingSlotLock.partner_id == partner_id)
            .filter(BookingSlotLock.service_id == service_id)
            .filter(BookingSlotLock.expires_at > now)
            .filter(BookingSlotLock.starts_at < ends_at)
            .filter(BookingSlotLock.ends_at > starts_at)
            .all()
        )
        booking_map: dict[str | None, list[tuple[datetime, datetime]]] = {}
        for booking in bookings:
            key = str(booking.resource_id) if booking.resource_id else None
            booking_map.setdefault(key, []).append((booking.starts_at, booking.ends_at))
        lock_map: dict[str | None, list[tuple[datetime, datetime]]] = {}
        for lock in locks:
            key = str(lock.resource_id) if lock.resource_id else None
            lock_map.setdefault(key, []).append((lock.starts_at, lock.ends_at))
        return booking_map, lock_map

    @staticmethod
    def _overlap_count(
        intervals: Iterable[tuple[datetime, datetime]],
        *,
        starts_at: datetime,
        ends_at: datetime,
    ) -> int:
        return sum(1 for interval_start, interval_end in intervals if interval_start < ends_at and interval_end > starts_at)

    def list_partner_services(self, *, partner_id: str, category: str | None = None) -> list[PartnerService]:
        query = (
            self.db.query(PartnerService)
            .filter(PartnerService.partner_id == partner_id)
            .filter(PartnerService.status == PartnerServiceStatus.ACTIVE)
        )
        if category:
            query = query.filter(PartnerService.category_code == category)
        return query.all()

    def quote_price(self, *, service_id: str, coupon_code: str | None = None) -> dict:
        service = self._get_service(service_id=service_id)
        return self._build_price_snapshot(service=service, coupon_code=coupon_code)

    def list_slots(
        self,
        *,
        partner_id: str,
        service_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> tuple[str, int, list[dict]]:
        service = self._get_service(service_id=service_id, partner_id=partner_id)
        calendar = self._get_calendar(partner_id=partner_id)
        if not calendar:
            return "UTC", 30, []
        if date_from.tzinfo is None:
            date_from = date_from.replace(tzinfo=timezone.utc)
        if date_to.tzinfo is None:
            date_to = date_to.replace(tzinfo=timezone.utc)
        rule = self._get_availability_rule(service_id=service_id, partner_id=partner_id)
        tz = ZoneInfo(calendar.timezone)
        start_local = date_from.astimezone(tz)
        end_local = date_to.astimezone(tz)
        if end_local <= start_local:
            return calendar.timezone, calendar.slot_step_minutes, []
        now_local = self._now().astimezone(tz)
        lead_time_minutes = rule.lead_time_minutes if rule else 0
        lead_time_cutoff = now_local + timedelta(minutes=lead_time_minutes)
        max_days_ahead = rule.max_days_ahead if rule else 14
        max_date = (now_local + timedelta(days=max_days_ahead)).date()

        resources_query = self.db.query(PartnerResource).filter(PartnerResource.partner_id == partner_id)
        resources_query = resources_query.filter(PartnerResource.status == PartnerResourceStatus.ACTIVE)
        if rule and rule.resource_ids:
            resources_query = resources_query.filter(PartnerResource.id.in_(rule.resource_ids))
        resources = resources_query.all()
        resource_list: list[PartnerResource | None] = resources or [None]

        booking_map, lock_map = self._collect_conflicts(
            partner_id=partner_id,
            service_id=service_id,
            starts_at=date_from,
            ends_at=date_to,
            now=self._now(),
        )

        slots: list[dict] = []
        slot_step = calendar.slot_step_minutes
        duration = timedelta(minutes=service.duration_minutes)
        current_date = start_local.date()
        while current_date <= end_local.date():
            if current_date > max_date:
                break
            day_ref = datetime.combine(current_date, time(0, 0, tzinfo=tz))
            if self._is_holiday(date_value=day_ref, calendar=calendar):
                current_date += timedelta(days=1)
                continue
            for interval_start, interval_end in self._iter_working_intervals(date_value=day_ref, calendar=calendar):
                slot_start = max(interval_start, start_local)
                while slot_start + duration <= interval_end:
                    slot_end = slot_start + duration
                    if slot_end > end_local:
                        break
                    if slot_start < lead_time_cutoff:
                        slot_start += timedelta(minutes=slot_step)
                        continue
                    for resource in resource_list:
                        resource_key = str(resource.id) if resource else None
                        capacity = resource.capacity if resource else (rule.parallel_capacity if rule else 1)
                        booking_conflicts = self._overlap_count(
                            booking_map.get(resource_key, []),
                            starts_at=slot_start.astimezone(timezone.utc),
                            ends_at=slot_end.astimezone(timezone.utc),
                        )
                        lock_conflicts = self._overlap_count(
                            lock_map.get(resource_key, []),
                            starts_at=slot_start.astimezone(timezone.utc),
                            ends_at=slot_end.astimezone(timezone.utc),
                        )
                        if booking_conflicts + lock_conflicts >= capacity:
                            continue
                        slots.append(
                            {
                                "start": slot_start.astimezone(timezone.utc),
                                "end": slot_end.astimezone(timezone.utc),
                                "resource_id": str(resource.id) if resource else None,
                            }
                        )
                    slot_start += timedelta(minutes=slot_step)
            current_date += timedelta(days=1)
        return calendar.timezone, calendar.slot_step_minutes, slots

    def lock_slot(
        self,
        *,
        client_id: str,
        partner_id: str,
        service_id: str,
        resource_id: str | None,
        starts_at: datetime,
        ends_at: datetime,
    ) -> BookingSlotLock:
        if ends_at <= starts_at:
            raise ServiceBookingServiceError("invalid_slot_range")
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=timezone.utc)
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=timezone.utc)
        self._get_service(service_id=service_id, partner_id=partner_id)
        now = self._now()
        existing = (
            self.db.query(BookingSlotLock)
            .filter(BookingSlotLock.client_id == client_id)
            .filter(BookingSlotLock.partner_id == partner_id)
            .filter(BookingSlotLock.service_id == service_id)
            .filter(BookingSlotLock.starts_at == starts_at)
            .filter(BookingSlotLock.ends_at == ends_at)
            .filter(BookingSlotLock.expires_at > now)
            .one_or_none()
        )
        if existing:
            return existing

        booking_map, lock_map = self._collect_conflicts(
            partner_id=partner_id,
            service_id=service_id,
            starts_at=starts_at,
            ends_at=ends_at,
            now=now,
        )
        resource_key = resource_id
        rule = self._get_availability_rule(service_id=service_id, partner_id=partner_id)
        capacity = rule.parallel_capacity if rule else 1
        if resource_id:
            resource = (
                self.db.query(PartnerResource)
                .filter(PartnerResource.id == resource_id)
                .filter(PartnerResource.partner_id == partner_id)
                .one_or_none()
            )
            if resource:
                capacity = resource.capacity
            else:
                raise ServiceBookingServiceError("resource_not_found")
        booking_conflicts = self._overlap_count(
            booking_map.get(resource_key, []),
            starts_at=starts_at,
            ends_at=ends_at,
        )
        lock_conflicts = self._overlap_count(
            lock_map.get(resource_key, []),
            starts_at=starts_at,
            ends_at=ends_at,
        )
        if booking_conflicts + lock_conflicts >= capacity:
            raise ServiceBookingServiceError("slot_unavailable")

        lock = BookingSlotLock(
            id=new_uuid_str(),
            tenant_id=self._tenant_id(),
            partner_id=partner_id,
            service_id=service_id,
            resource_id=resource_id,
            starts_at=starts_at,
            ends_at=ends_at,
            client_id=client_id,
            expires_at=now + timedelta(minutes=10),
        )
        self.db.add(lock)
        return lock

    def create_booking(
        self,
        *,
        client_id: str,
        lock_id: str,
        vehicle_id: str | None,
        recommendation_id: str | None,
        client_note: str | None,
    ) -> ServiceBooking:
        lock = (
            self.db.query(BookingSlotLock)
            .filter(BookingSlotLock.id == lock_id)
            .filter(BookingSlotLock.client_id == client_id)
            .one_or_none()
        )
        if not lock:
            raise ServiceBookingServiceError("lock_not_found")
        if lock.expires_at <= self._now():
            raise ServiceBookingServiceError("lock_expired")
        if lock.booking_id:
            booking = self.db.query(ServiceBooking).filter(ServiceBooking.id == lock.booking_id).one_or_none()
            if booking:
                return booking
        service = self._get_service(service_id=str(lock.service_id))
        price_snapshot = self._build_price_snapshot(service=service)

        booking = ServiceBooking(
            id=new_uuid_str(),
            tenant_id=self._tenant_id(),
            booking_number=self._generate_booking_number(),
            client_id=client_id,
            partner_id=lock.partner_id,
            service_id=lock.service_id,
            vehicle_id=vehicle_id,
            recommendation_id=recommendation_id,
            status=ServiceBookingStatus.REQUESTED.value,
            starts_at=lock.starts_at,
            ends_at=lock.ends_at,
            resource_id=lock.resource_id,
            price_snapshot_json=price_snapshot,
            promo_applied_json=None,
            payment_status=BookingPaymentStatus.NONE.value,
            client_note=client_note,
        )
        self.db.add(booking)
        self.db.flush()
        lock.booking_id = booking.id
        self._emit_booking_event(
            booking=booking,
            event_type=ServiceBookingEventType.SLOT_LOCKED,
            payload={"lock_id": str(lock.id), "expires_at": lock.expires_at.isoformat()},
            actor_type=ServiceBookingActorType.CLIENT,
            actor_id=client_id,
        )
        self._emit_booking_event(
            booking=booking,
            event_type=ServiceBookingEventType.CREATED,
            payload={"status": booking.status},
            actor_type=ServiceBookingActorType.CLIENT,
            actor_id=client_id,
        )
        return booking

    def list_bookings_for_client(
        self,
        *,
        client_id: str,
        status: ServiceBookingStatus | None = None,
    ) -> list[ServiceBooking]:
        query = self.db.query(ServiceBooking).filter(ServiceBooking.client_id == client_id)
        if status:
            query = query.filter(ServiceBooking.status == status.value)
        return query.order_by(ServiceBooking.created_at.desc()).all()

    def list_bookings_for_partner(
        self,
        *,
        partner_id: str,
        status: ServiceBookingStatus | None = None,
    ) -> list[ServiceBooking]:
        query = self.db.query(ServiceBooking).filter(ServiceBooking.partner_id == partner_id)
        if status:
            query = query.filter(ServiceBooking.status == status.value)
        return query.order_by(ServiceBooking.starts_at.asc()).all()

    def list_booking_events(self, *, booking_id: str) -> list[ServiceBookingEvent]:
        return (
            self.db.query(ServiceBookingEvent)
            .filter(ServiceBookingEvent.booking_id == booking_id)
            .order_by(ServiceBookingEvent.created_at.asc())
            .all()
        )

    def get_booking_for_client(self, *, booking_id: str, client_id: str) -> ServiceBooking:
        booking = (
            self.db.query(ServiceBooking)
            .filter(ServiceBooking.id == booking_id)
            .filter(ServiceBooking.client_id == client_id)
            .one_or_none()
        )
        if not booking:
            raise ServiceBookingServiceError("booking_not_found")
        return booking

    def get_booking_for_partner(self, *, booking_id: str, partner_id: str) -> ServiceBooking:
        booking = (
            self.db.query(ServiceBooking)
            .filter(ServiceBooking.id == booking_id)
            .filter(ServiceBooking.partner_id == partner_id)
            .one_or_none()
        )
        if not booking:
            raise ServiceBookingServiceError("booking_not_found")
        return booking

    def cancel_booking(
        self,
        *,
        booking_id: str,
        client_id: str,
        reason: str | None,
    ) -> ServiceBooking:
        booking = self.get_booking_for_client(booking_id=booking_id, client_id=client_id)
        if booking.status == ServiceBookingStatus.CANCELED.value:
            return booking
        rule = self._get_availability_rule(service_id=str(booking.service_id), partner_id=str(booking.partner_id))
        if rule and booking.starts_at:
            cutoff = booking.starts_at - timedelta(minutes=rule.lead_time_minutes)
            if self._now() > cutoff:
                raise ServiceBookingServiceError("cancel_not_allowed")
        self._apply_transition(booking, event_type=ServiceBookingEventType.CANCELED)
        self._emit_booking_event(
            booking=booking,
            event_type=ServiceBookingEventType.CANCELED,
            payload={"reason": reason},
            actor_type=ServiceBookingActorType.CLIENT,
            actor_id=client_id,
        )
        return booking

    def confirm_booking(self, *, booking_id: str, partner_id: str) -> ServiceBooking:
        booking = self.get_booking_for_partner(booking_id=booking_id, partner_id=partner_id)
        if booking.status == ServiceBookingStatus.CONFIRMED.value:
            return booking
        self._apply_transition(booking, event_type=ServiceBookingEventType.CONFIRMED)
        self._emit_booking_event(
            booking=booking,
            event_type=ServiceBookingEventType.CONFIRMED,
            payload={},
            actor_type=ServiceBookingActorType.PARTNER,
            actor_id=partner_id,
        )
        return booking

    def decline_booking(self, *, booking_id: str, partner_id: str, reason: str | None) -> ServiceBooking:
        booking = self.get_booking_for_partner(booking_id=booking_id, partner_id=partner_id)
        if booking.status == ServiceBookingStatus.DECLINED.value:
            return booking
        self._apply_transition(booking, event_type=ServiceBookingEventType.DECLINED)
        self._emit_booking_event(
            booking=booking,
            event_type=ServiceBookingEventType.DECLINED,
            payload={"reason": reason},
            actor_type=ServiceBookingActorType.PARTNER,
            actor_id=partner_id,
        )
        return booking

    def start_booking(self, *, booking_id: str, partner_id: str) -> ServiceBooking:
        booking = self.get_booking_for_partner(booking_id=booking_id, partner_id=partner_id)
        if booking.status == ServiceBookingStatus.IN_PROGRESS.value:
            return booking
        self._apply_transition(booking, event_type=ServiceBookingEventType.STARTED)
        self._emit_booking_event(
            booking=booking,
            event_type=ServiceBookingEventType.STARTED,
            payload={},
            actor_type=ServiceBookingActorType.PARTNER,
            actor_id=partner_id,
        )
        return booking

    def mark_no_show(self, *, booking_id: str, partner_id: str) -> ServiceBooking:
        booking = self.get_booking_for_partner(booking_id=booking_id, partner_id=partner_id)
        if booking.status == ServiceBookingStatus.NO_SHOW.value:
            return booking
        self._apply_transition(booking, event_type=ServiceBookingEventType.NO_SHOW)
        self._emit_booking_event(
            booking=booking,
            event_type=ServiceBookingEventType.NO_SHOW,
            payload={},
            actor_type=ServiceBookingActorType.PARTNER,
            actor_id=partner_id,
        )
        return booking

    def complete_booking(self, *, booking_id: str, partner_id: str) -> ServiceBooking:
        booking = self.get_booking_for_partner(booking_id=booking_id, partner_id=partner_id)
        if booking.status == ServiceBookingStatus.COMPLETED.value:
            return booking
        self._apply_transition(booking, event_type=ServiceBookingEventType.COMPLETED)
        self._emit_booking_event(
            booking=booking,
            event_type=ServiceBookingEventType.COMPLETED,
            payload={},
            actor_type=ServiceBookingActorType.PARTNER,
            actor_id=partner_id,
        )
        vehicle = None
        if booking.vehicle_id:
            vehicle = (
                self.db.query(VehicleProfile)
                .filter(VehicleProfile.id == booking.vehicle_id)
                .one_or_none()
            )
        service = self._get_service(service_id=str(booking.service_id))
        if vehicle:
            allowed_types = {item.value for item in VehicleServiceType}
            service_type = service.category_code if service.category_code in allowed_types else VehicleServiceType.OTHER.value
            record = VehicleServiceRecord(
                id=new_uuid_str(),
                tenant_id=self._tenant_id(),
                vehicle_id=vehicle.id,
                booking_id=booking.id,
                partner_id=booking.partner_id,
                service_type=service_type,
                service_at_km=vehicle.current_odometer_km,
                service_at=self._now(),
            )
            self.db.add(record)
            self.db.flush()
            case = self._ensure_booking_case(booking=booking)
            case_event = emit_case_event(
                self.db,
                case_id=str(case.id),
                event_type=CaseEventType.SERVICE_RECORD_CREATED,
                actor=self._case_actor(),
                request_id=self.request_ctx.request_id if self.request_ctx else None,
                trace_id=self.request_ctx.trace_id if self.request_ctx else None,
                extra_payload={"booking_id": str(booking.id), "record_id": str(record.id)},
            )
            _ = case_event
        if booking.recommendation_id:
            recommendation = (
                self.db.query(VehicleRecommendation)
                .filter(VehicleRecommendation.id == booking.recommendation_id)
                .one_or_none()
            )
            if recommendation:
                recommendation.status = VehicleRecommendationStatus.DONE.value
        return booking

    def get_booking_admin(self, *, booking_id: str) -> ServiceBooking:
        booking = self.db.query(ServiceBooking).filter(ServiceBooking.id == booking_id).one_or_none()
        if not booking:
            raise ServiceBookingServiceError("booking_not_found")
        return booking

    def cancel_booking_admin(self, *, booking_id: str, reason: str | None) -> ServiceBooking:
        booking = self.get_booking_admin(booking_id=booking_id)
        if booking.status == ServiceBookingStatus.CANCELED.value:
            return booking
        self._apply_transition(booking, event_type=ServiceBookingEventType.CANCELED)
        self._emit_booking_event(
            booking=booking,
            event_type=ServiceBookingEventType.CANCELED,
            payload={"reason": reason, "override": True},
            actor_type=ServiceBookingActorType.ADMIN,
            actor_id=self.request_ctx.actor_id if self.request_ctx else None,
        )
        return booking

    def update_partner_calendar(
        self,
        *,
        partner_id: str,
        timezone_name: str,
        working_hours: dict,
        holidays: dict | None,
        slot_step_minutes: int,
    ) -> PartnerServiceCalendar:
        calendar = self._get_calendar(partner_id=partner_id)
        if not calendar:
            calendar = PartnerServiceCalendar(
                id=new_uuid_str(),
                tenant_id=self._tenant_id(),
                partner_id=partner_id,
                timezone=timezone_name,
                working_hours=working_hours,
                holidays=holidays,
                slot_step_minutes=slot_step_minutes,
            )
            self.db.add(calendar)
        else:
            calendar.timezone = timezone_name
            calendar.working_hours = working_hours
            calendar.holidays = holidays
            calendar.slot_step_minutes = slot_step_minutes
        return calendar

    def create_resource(self, *, partner_id: str, payload: dict) -> PartnerResource:
        resource = PartnerResource(
            id=new_uuid_str(),
            tenant_id=self._tenant_id(),
            partner_id=partner_id,
            title=payload["title"],
            resource_type=payload["resource_type"],
            capacity=payload.get("capacity", 1),
            status=payload.get("status", PartnerResourceStatus.ACTIVE.value),
            meta=payload.get("meta"),
        )
        self.db.add(resource)
        return resource

    def update_resource(self, *, partner_id: str, resource_id: str, payload: dict) -> PartnerResource:
        resource = (
            self.db.query(PartnerResource)
            .filter(PartnerResource.id == resource_id)
            .filter(PartnerResource.partner_id == partner_id)
            .one_or_none()
        )
        if not resource:
            raise ServiceBookingServiceError("resource_not_found")
        resource.title = payload["title"]
        resource.resource_type = payload["resource_type"]
        resource.capacity = payload.get("capacity", resource.capacity)
        resource.status = payload.get("status", resource.status)
        resource.meta = payload.get("meta")
        return resource

    def list_resources(self, *, partner_id: str) -> list[PartnerResource]:
        return (
            self.db.query(PartnerResource)
            .filter(PartnerResource.partner_id == partner_id)
            .order_by(PartnerResource.title.asc())
            .all()
        )

    def delete_resource(self, *, partner_id: str, resource_id: str) -> None:
        resource = (
            self.db.query(PartnerResource)
            .filter(PartnerResource.id == resource_id)
            .filter(PartnerResource.partner_id == partner_id)
            .one_or_none()
        )
        if not resource:
            raise ServiceBookingServiceError("resource_not_found")
        self.db.delete(resource)

    def upsert_availability_rule(self, *, partner_id: str, payload: dict) -> ServiceAvailabilityRule:
        rule = (
            self.db.query(ServiceAvailabilityRule)
            .filter(ServiceAvailabilityRule.partner_id == partner_id)
            .filter(ServiceAvailabilityRule.service_id == payload["service_id"])
            .one_or_none()
        )
        if not rule:
            rule = ServiceAvailabilityRule(
                id=new_uuid_str(),
                tenant_id=self._tenant_id(),
                partner_id=partner_id,
                service_id=payload["service_id"],
            )
            self.db.add(rule)
        rule.resource_ids = payload.get("resource_ids")
        rule.lead_time_minutes = payload.get("lead_time_minutes", rule.lead_time_minutes)
        rule.max_days_ahead = payload.get("max_days_ahead", rule.max_days_ahead)
        rule.parallel_capacity = payload.get("parallel_capacity", rule.parallel_capacity)
        rule.meta = payload.get("meta")
        return rule
