from __future__ import annotations

from sqlalchemy import or_

from app.models.client_portal import ClientUserRole
from app.models.export_jobs import ExportJob
from app.models.fleet import ClientEmployee
from app.models.report_schedules import ReportSchedule
from app.services.client_notifications import ClientNotificationSeverity, create_notification, send_notification_email

_ROLE_LABELS = {"CLIENT_OWNER", "CLIENT_ADMIN"}


def _fetch_role_emails(session, org_id: str, roles: list[str]) -> list[str]:
    normalized_roles = {role for role in roles if role in _ROLE_LABELS}
    if not normalized_roles:
        return []
    role_filters = [ClientUserRole.roles.ilike(f"%{role}%") for role in normalized_roles]
    role_rows = (
        session.query(ClientUserRole)
        .filter(ClientUserRole.client_id == org_id)
        .filter(or_(*role_filters))
        .all()
    )
    user_ids = {row.user_id for row in role_rows}
    if not user_ids:
        return []
    employees = session.query(ClientEmployee).filter(ClientEmployee.id.in_(user_ids)).all()
    emails = [employee.email for employee in employees if employee.email]
    return sorted(set(emails))


def send_scheduled_report_notifications(
    session,
    *,
    schedule: ReportSchedule,
    job: ExportJob,
    success: bool,
) -> None:
    event_type = "scheduled_report_ready" if success else "scheduled_report_failed"
    severity = ClientNotificationSeverity.INFO if success else ClientNotificationSeverity.WARNING
    title = "Отчёт готов" if success else "Ошибка отчёта"
    body = (
        "Запланированный отчёт сформирован и доступен для скачивания."
        if success
        else "Не удалось сформировать запланированный отчёт."
    )
    link = "/client/exports"

    if schedule.delivery_in_app:
        create_notification(
            session,
            org_id=str(schedule.org_id),
            event_type=event_type,
            severity=severity,
            title=title,
            body=body,
            link=link,
            target_user_id=str(schedule.created_by_user_id),
            entity_type="report_schedule",
            entity_id=str(schedule.id),
            meta_json={"export_job_id": str(job.id)},
        )
        if schedule.delivery_email_to_roles:
            create_notification(
                session,
                org_id=str(schedule.org_id),
                event_type=event_type,
                severity=severity,
                title=title,
                body=body,
                link=link,
                target_roles=schedule.delivery_email_to_roles,
                entity_type="report_schedule",
                entity_id=str(schedule.id),
                meta_json={"export_job_id": str(job.id)},
            )

    if schedule.delivery_email_to_creator:
        creator = session.get(ClientEmployee, schedule.created_by_user_id)
        if creator and creator.email:
            send_notification_email(to_email=creator.email, title=title, body=body, link=link)

    if schedule.delivery_email_to_roles:
        emails = _fetch_role_emails(session, str(schedule.org_id), schedule.delivery_email_to_roles or [])
        for email in emails:
            send_notification_email(to_email=email, title=title, body=body, link=link)


__all__ = ["send_scheduled_report_notifications"]
