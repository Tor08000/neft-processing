from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.models.marketplace_catalog import (
    MarketplaceService,
    MarketplaceServiceLocation,
    MarketplaceServiceMedia,
    MarketplaceServiceScheduleException,
    MarketplaceServiceScheduleRule,
    MarketplaceServiceStatus,
)
from app.schemas.marketplace.services import assert_editable, assert_transition


def _parse_time(value: str) -> time:
    try:
        parts = value.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return time(hour=hour, minute=minute)
    except Exception as exc:
        raise ValueError("time_format_invalid") from exc


def _time_to_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _validate_time_range(time_from: str, time_to: str) -> tuple[int, int]:
    start = _parse_time(time_from)
    end = _parse_time(time_to)
    start_min = _time_to_minutes(start)
    end_min = _time_to_minutes(end)
    if end_min <= start_min:
        raise ValueError("time_range_invalid")
    return start_min, end_min


class MarketplaceServicesService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_partner_services(
        self,
        *,
        partner_id: str,
        status: MarketplaceServiceStatus | None = None,
        category: str | None = None,
        query_text: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MarketplaceService], int]:
        query = self.db.query(MarketplaceService).filter(MarketplaceService.partner_id == partner_id)
        if status:
            query = query.filter(MarketplaceService.status == status)
        if category:
            query = query.filter(MarketplaceService.category == category)
        if query_text:
            like = f"%{query_text}%"
            query = query.filter(
                or_(MarketplaceService.title.ilike(like), MarketplaceService.description.ilike(like))
            )
        total = query.count()
        items = (
            query.order_by(MarketplaceService.updated_at.desc().nullslast(), MarketplaceService.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def list_active_services(
        self,
        *,
        category: str | None = None,
        query_text: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[MarketplaceService], int]:
        query = self.db.query(MarketplaceService).filter(MarketplaceService.status == MarketplaceServiceStatus.ACTIVE)
        if category:
            query = query.filter(MarketplaceService.category == category)
        if query_text:
            like = f"%{query_text}%"
            query = query.filter(
                or_(MarketplaceService.title.ilike(like), MarketplaceService.description.ilike(like))
            )
        total = query.count()
        items = (
            query.order_by(MarketplaceService.updated_at.desc().nullslast(), MarketplaceService.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def get_service(self, *, service_id: str) -> MarketplaceService | None:
        return self.db.query(MarketplaceService).filter(MarketplaceService.id == service_id).one_or_none()

    def create_service(self, *, partner_id: str, payload: dict) -> MarketplaceService:
        service = MarketplaceService(
            id=new_uuid_str(),
            partner_id=partner_id,
            title=payload["title"],
            description=payload.get("description"),
            category=payload["category"],
            status=MarketplaceServiceStatus.DRAFT.value,
            tags=payload.get("tags") or [],
            attributes=payload.get("attributes") or {},
            duration_min=payload["duration_min"],
            requirements=payload.get("requirements"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(service)
        self.db.flush()
        return service

    def update_service(self, *, service: MarketplaceService, payload: dict) -> MarketplaceService:
        assert_editable(service.status)
        for field in ("title", "description", "category", "tags", "attributes", "duration_min", "requirements"):
            if field in payload:
                setattr(service, field, payload[field])
        service.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return service

    def submit_service(self, *, service: MarketplaceService) -> MarketplaceService:
        assert_transition(service.status, MarketplaceServiceStatus.PENDING_REVIEW, actor_role="partner")
        service.status = MarketplaceServiceStatus.PENDING_REVIEW
        service.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return service

    def archive_service(self, *, service: MarketplaceService) -> MarketplaceService:
        assert_transition(service.status, MarketplaceServiceStatus.ARCHIVED, actor_role="partner")
        service.status = MarketplaceServiceStatus.ARCHIVED
        service.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return service

    def list_service_media(self, *, service_id: str) -> list[MarketplaceServiceMedia]:
        return (
            self.db.query(MarketplaceServiceMedia)
            .filter(MarketplaceServiceMedia.service_id == service_id)
            .order_by(MarketplaceServiceMedia.sort_index.asc(), MarketplaceServiceMedia.created_at.asc())
            .all()
        )

    def add_service_media(self, *, service_id: str, payload: dict) -> MarketplaceServiceMedia:
        media = MarketplaceServiceMedia(
            id=new_uuid_str(),
            service_id=service_id,
            attachment_id=payload["attachment_id"],
            bucket=payload["bucket"],
            path=payload["path"],
            checksum=payload.get("checksum"),
            size=payload.get("size"),
            mime=payload.get("mime"),
            sort_index=payload.get("sort_index") or 0,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(media)
        self.db.flush()
        return media

    def remove_service_media(self, *, service_id: str, attachment_id: str) -> bool:
        deleted = (
            self.db.query(MarketplaceServiceMedia)
            .filter(MarketplaceServiceMedia.service_id == service_id)
            .filter(MarketplaceServiceMedia.attachment_id == attachment_id)
            .delete()
        )
        return bool(deleted)

    def list_service_locations(self, *, service_id: str) -> list[MarketplaceServiceLocation]:
        return (
            self.db.query(MarketplaceServiceLocation)
            .filter(MarketplaceServiceLocation.service_id == service_id)
            .order_by(MarketplaceServiceLocation.created_at.asc())
            .all()
        )

    def add_service_location(self, *, service_id: str, payload: dict) -> MarketplaceServiceLocation:
        location = MarketplaceServiceLocation(
            id=new_uuid_str(),
            service_id=service_id,
            location_id=payload["location_id"],
            address=payload.get("address"),
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            is_active=payload.get("is_active", True),
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(location)
        self.db.flush()
        return location

    def remove_service_location(self, *, service_id: str, service_location_id: str) -> bool:
        deleted = (
            self.db.query(MarketplaceServiceLocation)
            .filter(MarketplaceServiceLocation.service_id == service_id)
            .filter(MarketplaceServiceLocation.id == service_location_id)
            .delete()
        )
        return bool(deleted)

    def get_service_location(self, *, service_location_id: str) -> MarketplaceServiceLocation | None:
        return (
            self.db.query(MarketplaceServiceLocation)
            .filter(MarketplaceServiceLocation.id == service_location_id)
            .one_or_none()
        )

    def list_schedule_rules(self, *, service_location_id: str) -> list[MarketplaceServiceScheduleRule]:
        return (
            self.db.query(MarketplaceServiceScheduleRule)
            .filter(MarketplaceServiceScheduleRule.service_location_id == service_location_id)
            .order_by(MarketplaceServiceScheduleRule.weekday.asc(), MarketplaceServiceScheduleRule.time_from.asc())
            .all()
        )

    def list_schedule_exceptions(self, *, service_location_id: str) -> list[MarketplaceServiceScheduleException]:
        return (
            self.db.query(MarketplaceServiceScheduleException)
            .filter(MarketplaceServiceScheduleException.service_location_id == service_location_id)
            .order_by(MarketplaceServiceScheduleException.date.asc())
            .all()
        )

    def add_schedule_rule(
        self,
        *,
        service_location_id: str,
        payload: dict,
        service_duration: int,
    ) -> MarketplaceServiceScheduleRule:
        slot_duration = payload.get("slot_duration_min") or service_duration
        if slot_duration <= 0:
            raise ValueError("slot_duration_invalid")
        start_min, end_min = _validate_time_range(payload["time_from"], payload["time_to"])
        existing = (
            self.db.query(MarketplaceServiceScheduleRule)
            .filter(MarketplaceServiceScheduleRule.service_location_id == service_location_id)
            .filter(MarketplaceServiceScheduleRule.weekday == payload["weekday"])
            .all()
        )
        for rule in existing:
            rule_start, rule_end = _validate_time_range(rule.time_from, rule.time_to)
            if start_min < rule_end and end_min > rule_start:
                raise ValueError("schedule_overlap")
        rule = MarketplaceServiceScheduleRule(
            id=new_uuid_str(),
            service_location_id=service_location_id,
            weekday=payload["weekday"],
            time_from=payload["time_from"],
            time_to=payload["time_to"],
            slot_duration_min=slot_duration,
            capacity=payload["capacity"],
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(rule)
        self.db.flush()
        return rule

    def remove_schedule_rule(self, *, service_location_id: str, rule_id: str) -> bool:
        deleted = (
            self.db.query(MarketplaceServiceScheduleRule)
            .filter(MarketplaceServiceScheduleRule.service_location_id == service_location_id)
            .filter(MarketplaceServiceScheduleRule.id == rule_id)
            .delete()
        )
        return bool(deleted)

    def add_schedule_exception(
        self,
        *,
        service_location_id: str,
        payload: dict,
    ) -> MarketplaceServiceScheduleException:
        if payload.get("time_from") and payload.get("time_to"):
            _validate_time_range(payload["time_from"], payload["time_to"])
        exception = MarketplaceServiceScheduleException(
            id=new_uuid_str(),
            service_location_id=service_location_id,
            date=payload["date"],
            is_closed=payload.get("is_closed", False),
            time_from=payload.get("time_from"),
            time_to=payload.get("time_to"),
            capacity_override=payload.get("capacity_override"),
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(exception)
        self.db.flush()
        return exception

    def remove_schedule_exception(self, *, service_location_id: str, exception_id: str) -> bool:
        deleted = (
            self.db.query(MarketplaceServiceScheduleException)
            .filter(MarketplaceServiceScheduleException.service_location_id == service_location_id)
            .filter(MarketplaceServiceScheduleException.id == exception_id)
            .delete()
        )
        return bool(deleted)

    def generate_availability(
        self,
        *,
        service: MarketplaceService,
        locations: Iterable[MarketplaceServiceLocation],
        date_from: date,
        date_to: date,
        public_only: bool = False,
    ) -> list[dict]:
        results: list[dict] = []
        location_ids = [location.id for location in locations if not public_only or location.is_active]
        if not location_ids:
            return results
        rules = (
            self.db.query(MarketplaceServiceScheduleRule)
            .filter(MarketplaceServiceScheduleRule.service_location_id.in_(location_ids))
            .all()
        )
        exceptions = (
            self.db.query(MarketplaceServiceScheduleException)
            .filter(MarketplaceServiceScheduleException.service_location_id.in_(location_ids))
            .all()
        )
        rules_by_location: dict[str, list[MarketplaceServiceScheduleRule]] = {}
        for rule in rules:
            rules_by_location.setdefault(str(rule.service_location_id), []).append(rule)
        exceptions_by_location_date: dict[tuple[str, date], MarketplaceServiceScheduleException] = {}
        for exception in exceptions:
            exceptions_by_location_date[(str(exception.service_location_id), exception.date)] = exception

        days = (date_to - date_from).days
        for location in locations:
            if public_only and not location.is_active:
                continue
            location_rules = rules_by_location.get(str(location.id), [])
            for offset in range(days + 1):
                current_day = date_from + timedelta(days=offset)
                exception = exceptions_by_location_date.get((str(location.id), current_day))
                if exception and exception.is_closed:
                    continue
                weekday = current_day.weekday()
                day_rules = [rule for rule in location_rules if rule.weekday == weekday]
                if exception and exception.time_from and exception.time_to:
                    day_rules = []
                    time_ranges = [
                        {
                            "time_from": exception.time_from,
                            "time_to": exception.time_to,
                            "slot_duration": service.duration_min,
                            "capacity": exception.capacity_override or 1,
                        }
                    ]
                else:
                    time_ranges = [
                        {
                            "time_from": rule.time_from,
                            "time_to": rule.time_to,
                            "slot_duration": rule.slot_duration_min or service.duration_min,
                            "capacity": rule.capacity,
                        }
                        for rule in day_rules
                    ]
                for time_range in time_ranges:
                    start_min, end_min = _validate_time_range(time_range["time_from"], time_range["time_to"])
                    slot_duration = time_range["slot_duration"]
                    slot_start = start_min
                    while slot_start + slot_duration <= end_min:
                        slot_end = slot_start + slot_duration
                        capacity = (
                            exception.capacity_override
                            if exception and exception.capacity_override
                            else time_range["capacity"]
                        )
                        results.append(
                            {
                                "service_location_id": str(location.id),
                                "location_id": str(location.location_id),
                                "date": current_day,
                                "time_from": f"{slot_start // 60:02d}:{slot_start % 60:02d}",
                                "time_to": f"{slot_end // 60:02d}:{slot_end % 60:02d}",
                                "capacity": capacity,
                            }
                        )
                        slot_start += slot_duration
        results.sort(key=lambda item: (item["date"], item["time_from"]))
        return results
