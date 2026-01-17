from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import floor
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.email_outbox import EmailOutbox, EmailOutboxStatus
from app.models.export_jobs import ExportJob, ExportJobStatus
from app.models.report_schedules import ReportSchedule, ReportScheduleStatus
from app.models.service_slo import (
    ServiceSlo,
    ServiceSloBreach,
    ServiceSloBreachStatus,
    ServiceSloMetric,
    ServiceSloService,
    ServiceSloWindow,
)
from app.models.support_ticket import SupportTicket
from app.services.audit_service import ActorType, AuditService, RequestContext
from app.services.client_notifications import ADMIN_TARGET_ROLES, ClientNotificationSeverity, create_notification
from app.services.report_schedules import compute_next_run_at

WINDOW_DAYS = {
    ServiceSloWindow.SEVEN_DAYS: 7,
    ServiceSloWindow.THIRTY_DAYS: 30,
}

LATENCY_KIND_FIRST_RESPONSE = "first_response"
LATENCY_KIND_RESOLUTION = "resolution"


@dataclass(frozen=True)
class SloWindowBounds:
    window_start: datetime
    window_end: datetime


@dataclass(frozen=True)
class SloObservation:
    breached: bool
    observed_value: dict[str, Any]


class SloObjectiveError(ValueError):
    pass


def _coerce_float(value: Any, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise SloObjectiveError(f"invalid_{field}") from exc


def _coerce_int(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise SloObjectiveError(f"invalid_{field}") from exc


def validate_objective(metric: ServiceSloMetric, objective: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(objective, dict):
        raise SloObjectiveError("invalid_objective")

    if metric == ServiceSloMetric.LATENCY:
        p = _coerce_int(objective.get("p"), "p")
        lt_seconds = _coerce_float(objective.get("lt_seconds"), "lt_seconds")
        if p <= 0 or p > 100:
            raise SloObjectiveError("invalid_p")
        if lt_seconds <= 0:
            raise SloObjectiveError("invalid_lt_seconds")
        latency_kind = objective.get("latency_type")
        if latency_kind not in (None, LATENCY_KIND_FIRST_RESPONSE, LATENCY_KIND_RESOLUTION):
            raise SloObjectiveError("invalid_latency_type")
        normalized = {"p": p, "lt_seconds": lt_seconds}
        if latency_kind:
            normalized["latency_type"] = latency_kind
        return normalized

    if metric == ServiceSloMetric.SUCCESS_RATE:
        gte = _coerce_float(objective.get("gte"), "gte")
        if gte <= 0 or gte > 1:
            raise SloObjectiveError("invalid_gte")
        return {"gte": gte}

    raise SloObjectiveError("invalid_metric")


def resolve_window_bounds(window: ServiceSloWindow, now: datetime | None = None) -> SloWindowBounds:
    anchor = now or datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    window_end = anchor.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    days = WINDOW_DAYS[window]
    window_start = window_end - timedelta(days=days)
    return SloWindowBounds(window_start=window_start, window_end=window_end)


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * (pct / 100.0)
    lower = floor(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    if lower == upper:
        return float(sorted_values[int(rank)])
    weight = rank - lower
    return float(sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * weight)


def _latency_kind_for_slo(slo: ServiceSlo) -> str:
    if slo.service == ServiceSloService.SUPPORT:
        return str(slo.objective_json.get("latency_type") or LATENCY_KIND_RESOLUTION)
    return LATENCY_KIND_RESOLUTION


def format_objective(metric: ServiceSloMetric, objective: dict[str, Any]) -> str:
    if metric == ServiceSloMetric.LATENCY:
        p = objective.get("p")
        lt_seconds = objective.get("lt_seconds")
        label = _format_duration(lt_seconds)
        return f"p{p} < {label}"
    gte = objective.get("gte")
    if gte is None:
        return ""
    return f">= {gte * 100:.2f}%"


def format_observed(metric: ServiceSloMetric, observed: dict[str, Any]) -> str:
    if metric == ServiceSloMetric.LATENCY:
        p = observed.get("p")
        value = observed.get("value_seconds")
        label = _format_duration(value)
        return f"p{p} = {label}"
    rate = observed.get("rate")
    if rate is None:
        return ""
    return f"{rate * 100:.2f}%"


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds >= 60 and seconds % 60 == 0:
        return f"{int(seconds // 60)}m"
    if seconds >= 60:
        return f"{seconds / 60:.1f}m"
    return f"{seconds:.0f}s"


def evaluate_slo(db: Session, slo: ServiceSlo, now: datetime | None = None) -> tuple[SloWindowBounds, SloObservation]:
    bounds = resolve_window_bounds(slo.window, now)
    objective = slo.objective_json or {}
    if slo.metric == ServiceSloMetric.LATENCY:
        p = objective.get("p", 95)
        lt_seconds = float(objective.get("lt_seconds", 0))
        samples = _collect_latency_samples(db, slo, bounds)
        value = _percentile(samples, float(p))
        observed = {
            "p": p,
            "value_seconds": value,
            "sample_size": len(samples),
            "latency_type": _latency_kind_for_slo(slo),
        }
        breached = value is not None and value > lt_seconds
        return bounds, SloObservation(breached=breached, observed_value=observed)

    success, total, rate = _collect_success_rate(db, slo, bounds)
    observed = {"success": success, "total": total, "rate": rate}
    gte = float(objective.get("gte", 1))
    breached = total > 0 and rate < gte
    return bounds, SloObservation(breached=breached, observed_value=observed)


def ensure_breach_status(
    db: Session,
    slo: ServiceSlo,
    bounds: SloWindowBounds,
    observation: SloObservation,
    now: datetime | None = None,
) -> ServiceSloBreach | None:
    current_time = now or datetime.now(timezone.utc)
    existing = (
        db.query(ServiceSloBreach)
        .filter(
            ServiceSloBreach.slo_id == slo.id,
            ServiceSloBreach.window_start == bounds.window_start,
            ServiceSloBreach.window_end == bounds.window_end,
        )
        .one_or_none()
    )

    if observation.breached:
        if existing is None:
            breach = ServiceSloBreach(
                slo_id=str(slo.id),
                org_id=str(slo.org_id),
                service=slo.service,
                metric=slo.metric,
                window=slo.window,
                window_start=bounds.window_start,
                window_end=bounds.window_end,
                observed_value_json=observation.observed_value,
                breached_at=current_time,
                status=ServiceSloBreachStatus.OPEN,
            )
            db.add(breach)
            _audit_breach(db, slo, breach)
            _notify_breach(db, slo, breach, observation)
            return breach

        if existing.status != ServiceSloBreachStatus.OPEN:
            existing.status = ServiceSloBreachStatus.OPEN
            existing.breached_at = current_time
            _audit_breach(db, slo, existing)
            _notify_breach(db, slo, existing, observation)
        existing.observed_value_json = observation.observed_value
        return existing

    if existing and existing.status == ServiceSloBreachStatus.OPEN:
        existing.status = ServiceSloBreachStatus.RESOLVED
        existing.observed_value_json = observation.observed_value
        _audit_resolved(db, slo, existing)
        return existing

    if existing:
        existing.observed_value_json = observation.observed_value
    return existing


def build_slo_health(db: Session, org_id: str, now: datetime | None = None) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    summary: dict[str, Any] = {}
    status = "green"
    for window in ServiceSloWindow:
        bounds = resolve_window_bounds(window, current_time)
        total = (
            db.query(func.count())
            .filter(
                ServiceSloBreach.org_id == org_id,
                ServiceSloBreach.window == window,
                ServiceSloBreach.window_start == bounds.window_start,
                ServiceSloBreach.window_end == bounds.window_end,
            )
            .scalar()
            or 0
        )
        open_count = (
            db.query(func.count())
            .filter(
                ServiceSloBreach.org_id == org_id,
                ServiceSloBreach.window == window,
                ServiceSloBreach.window_start == bounds.window_start,
                ServiceSloBreach.window_end == bounds.window_end,
                ServiceSloBreach.status == ServiceSloBreachStatus.OPEN,
            )
            .scalar()
            or 0
        )
        summary[f"breaches_{window.value}"] = int(open_count)
        summary[f"total_{window.value}"] = int(total)
        if open_count > 0:
            status = "red"
        elif total > 0 and status != "red":
            status = "yellow"
    summary["status"] = status
    return summary


def _collect_latency_samples(db: Session, slo: ServiceSlo, bounds: SloWindowBounds) -> list[float]:
    if slo.service == ServiceSloService.EXPORTS:
        rows = (
            db.query(ExportJob.started_at, ExportJob.finished_at)
            .filter(
                ExportJob.org_id == str(slo.org_id),
                ExportJob.status == ExportJobStatus.DONE,
                ExportJob.started_at.isnot(None),
                ExportJob.finished_at.isnot(None),
                ExportJob.finished_at >= bounds.window_start,
                ExportJob.finished_at <= bounds.window_end,
            )
            .all()
        )
        return [(row.finished_at - row.started_at).total_seconds() for row in rows]

    if slo.service == ServiceSloService.EMAIL:
        rows = (
            db.query(EmailOutbox.created_at, EmailOutbox.sent_at)
            .filter(
                EmailOutbox.org_id == str(slo.org_id),
                EmailOutbox.status == EmailOutboxStatus.SENT,
                EmailOutbox.sent_at.isnot(None),
                EmailOutbox.sent_at >= bounds.window_start,
                EmailOutbox.sent_at <= bounds.window_end,
            )
            .all()
        )
        return [(row.sent_at - row.created_at).total_seconds() for row in rows]

    if slo.service == ServiceSloService.SUPPORT:
        latency_kind = _latency_kind_for_slo(slo)
        if latency_kind == LATENCY_KIND_FIRST_RESPONSE:
            rows = (
                db.query(SupportTicket.created_at, SupportTicket.first_response_at)
                .filter(
                    SupportTicket.org_id == str(slo.org_id),
                    SupportTicket.first_response_at.isnot(None),
                    SupportTicket.first_response_at >= bounds.window_start,
                    SupportTicket.first_response_at <= bounds.window_end,
                )
                .all()
            )
            return [(row.first_response_at - row.created_at).total_seconds() for row in rows]
        rows = (
            db.query(SupportTicket.created_at, SupportTicket.resolved_at)
            .filter(
                SupportTicket.org_id == str(slo.org_id),
                SupportTicket.resolved_at.isnot(None),
                SupportTicket.resolved_at >= bounds.window_start,
                SupportTicket.resolved_at <= bounds.window_end,
            )
            .all()
        )
        return [(row.resolved_at - row.created_at).total_seconds() for row in rows]

    if slo.service == ServiceSloService.SCHEDULES:
        rows = (
            db.query(ExportJob.created_at, ExportJob.started_at)
            .filter(
                ExportJob.org_id == str(slo.org_id),
                ExportJob.started_at.isnot(None),
                ExportJob.created_at >= bounds.window_start,
                ExportJob.created_at <= bounds.window_end,
                ExportJob.filters_json["schedule_id"].astext.isnot(None),
            )
            .all()
        )
        return [(row.started_at - row.created_at).total_seconds() for row in rows]

    return []


def _collect_success_rate(db: Session, slo: ServiceSlo, bounds: SloWindowBounds) -> tuple[int, int, float]:
    if slo.service == ServiceSloService.EXPORTS:
        total = (
            db.query(func.count())
            .filter(
                ExportJob.org_id == str(slo.org_id),
                ExportJob.status.in_([ExportJobStatus.DONE, ExportJobStatus.FAILED]),
                ExportJob.finished_at.isnot(None),
                ExportJob.finished_at >= bounds.window_start,
                ExportJob.finished_at <= bounds.window_end,
            )
            .scalar()
            or 0
        )
        success = (
            db.query(func.count())
            .filter(
                ExportJob.org_id == str(slo.org_id),
                ExportJob.status == ExportJobStatus.DONE,
                ExportJob.finished_at.isnot(None),
                ExportJob.finished_at >= bounds.window_start,
                ExportJob.finished_at <= bounds.window_end,
            )
            .scalar()
            or 0
        )
        rate = success / total if total else 1.0
        return int(success), int(total), rate

    if slo.service == ServiceSloService.EMAIL:
        total = (
            db.query(func.count())
            .filter(
                EmailOutbox.org_id == str(slo.org_id),
                EmailOutbox.status.in_([EmailOutboxStatus.SENT, EmailOutboxStatus.FAILED]),
                EmailOutbox.created_at >= bounds.window_start,
                EmailOutbox.created_at <= bounds.window_end,
            )
            .scalar()
            or 0
        )
        success = (
            db.query(func.count())
            .filter(
                EmailOutbox.org_id == str(slo.org_id),
                EmailOutbox.status == EmailOutboxStatus.SENT,
                EmailOutbox.created_at >= bounds.window_start,
                EmailOutbox.created_at <= bounds.window_end,
            )
            .scalar()
            or 0
        )
        rate = success / total if total else 1.0
        return int(success), int(total), rate

    if slo.service == ServiceSloService.SUPPORT:
        total = (
            db.query(func.count())
            .filter(
                SupportTicket.org_id == str(slo.org_id),
                SupportTicket.resolved_at.isnot(None),
                SupportTicket.resolution_due_at.isnot(None),
                SupportTicket.resolved_at >= bounds.window_start,
                SupportTicket.resolved_at <= bounds.window_end,
            )
            .scalar()
            or 0
        )
        success = (
            db.query(func.count())
            .filter(
                SupportTicket.org_id == str(slo.org_id),
                SupportTicket.resolved_at.isnot(None),
                SupportTicket.resolution_due_at.isnot(None),
                SupportTicket.resolved_at <= SupportTicket.resolution_due_at,
                SupportTicket.resolved_at >= bounds.window_start,
                SupportTicket.resolved_at <= bounds.window_end,
            )
            .scalar()
            or 0
        )
        rate = success / total if total else 1.0
        return int(success), int(total), rate

    if slo.service == ServiceSloService.SCHEDULES:
        triggered = (
            db.query(func.count())
            .filter(
                ExportJob.org_id == str(slo.org_id),
                ExportJob.created_at >= bounds.window_start,
                ExportJob.created_at <= bounds.window_end,
                ExportJob.filters_json["schedule_id"].astext.isnot(None),
            )
            .scalar()
            or 0
        )
        expected = _expected_schedule_runs(db, slo.org_id, bounds)
        rate = triggered / expected if expected else 1.0
        return int(triggered), int(expected), rate

    return 0, 0, 1.0


def _expected_schedule_runs(db: Session, org_id: str, bounds: SloWindowBounds) -> int:
    schedules = (
        db.query(ReportSchedule)
        .filter(ReportSchedule.org_id == str(org_id), ReportSchedule.status == ReportScheduleStatus.ACTIVE)
        .all()
    )
    total = 0
    for schedule in schedules:
        total += _count_schedule_runs(schedule, bounds)
    return total


def _count_schedule_runs(schedule: ReportSchedule, bounds: SloWindowBounds) -> int:
    anchor = bounds.window_start - timedelta(seconds=1)
    next_run = compute_next_run_at(schedule.schedule_kind, schedule.schedule_meta, schedule.timezone, anchor)
    count = 0
    while next_run <= bounds.window_end:
        count += 1
        next_run = compute_next_run_at(
            schedule.schedule_kind,
            schedule.schedule_meta,
            schedule.timezone,
            next_run + timedelta(seconds=1),
        )
    return count


def _audit_breach(db: Session, slo: ServiceSlo, breach: ServiceSloBreach) -> None:
    AuditService(db).audit(
        event_type="slo_breached",
        entity_type="service_slo",
        entity_id=str(slo.id),
        action="slo_breached",
        after={
            "breach_id": str(breach.id),
            "service": slo.service.value,
            "metric": slo.metric.value,
            "window": slo.window.value,
        },
        request_ctx=RequestContext(actor_type=ActorType.SYSTEM),
    )


def _audit_resolved(db: Session, slo: ServiceSlo, breach: ServiceSloBreach) -> None:
    AuditService(db).audit(
        event_type="slo_resolved",
        entity_type="service_slo",
        entity_id=str(slo.id),
        action="slo_resolved",
        after={"breach_id": str(breach.id), "status": breach.status.value},
        request_ctx=RequestContext(actor_type=ActorType.SYSTEM),
    )


def _notify_breach(db: Session, slo: ServiceSlo, breach: ServiceSloBreach, observation: SloObservation) -> None:
    objective = format_objective(slo.metric, slo.objective_json or {})
    observed = format_observed(slo.metric, observation.observed_value)
    title = "SLO breached"
    body = _breach_message(slo)
    create_notification(
        db,
        org_id=str(slo.org_id),
        event_type="slo_breached",
        severity=ClientNotificationSeverity.WARNING,
        title=title,
        body=body,
        link="/client/slo",
        target_roles=ADMIN_TARGET_ROLES,
        entity_type="service_slo",
        entity_id=str(slo.id),
        meta_json={
            "objective": objective,
            "observed": observed,
            "window": slo.window.value,
            "service": slo.service.value,
            "metric": slo.metric.value,
            "breach_id": str(breach.id),
        },
    )


def _breach_message(slo: ServiceSlo) -> str:
    service_label = slo.service.value.capitalize()
    if slo.metric == ServiceSloMetric.LATENCY:
        p = slo.objective_json.get("p")
        lt_seconds = slo.objective_json.get("lt_seconds")
        threshold = _format_duration(lt_seconds)
        return f"SLO breached: {service_label} latency p{p} > {threshold} ({slo.window.value})"
    gte = slo.objective_json.get("gte")
    if gte is None:
        return f"SLO breached: {service_label} success rate ({slo.window.value})"
    return f"SLO breached: {service_label} success rate < {gte * 100:.2f}% ({slo.window.value})"


__all__ = [
    "SloObservation",
    "SloObjectiveError",
    "SloWindowBounds",
    "build_slo_health",
    "ensure_breach_status",
    "evaluate_slo",
    "format_objective",
    "format_observed",
    "resolve_window_bounds",
    "validate_objective",
]
