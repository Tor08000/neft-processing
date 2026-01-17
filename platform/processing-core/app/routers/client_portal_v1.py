from __future__ import annotations

import csv
import logging
import math
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from hashlib import sha256
from io import StringIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, RedirectResponse
from sqlalchemy import Date, String, and_, cast, desc, func, or_
from sqlalchemy.orm import Query, Session

from app.db import get_db
from app.models.client import Client
from app.models.crm import CRMClient
from app.models.client_onboarding import ClientOnboarding, ClientOnboardingContract
from app.models.client_portal import (
    CardAccess,
    CardAccessScope,
    CardLimit,
    ClientOperation,
    ClientUserRole,
    LimitTemplate,
)
from app.models.export_jobs import ExportJob, ExportJobFormat, ExportJobReportType, ExportJobStatus
from app.models.report_schedules import ReportSchedule, ReportScheduleKind, ReportScheduleStatus
from app.models.fleet import ClientEmployee, EmployeeStatus, FleetDriver
from app.models.card import Card
from app.models.email_outbox import EmailOutbox, EmailOutboxStatus
from app.models.documents import Document, DocumentFile, DocumentFileType, DocumentStatus, DocumentType
from app.models.fuel import (
    FuelCard,
    FuelCardStatus,
    FuelLimit,
    FuelLimitPeriod,
    FuelLimitScopeType,
    FuelLimitType,
    FuelStation,
    FuelTransaction,
    FuelTransactionStatus,
)
from app.models.operation import Operation
from app.models.helpdesk import (
    HelpdeskIntegrationStatus,
    HelpdeskOutboxEventType,
    HelpdeskOutboxStatus,
    HelpdeskTicketLink,
)
from app.models.service_slo import (
    ServiceSlo,
    ServiceSloBreach,
    ServiceSloService,
    ServiceSloWindow,
)
from app.models.support_ticket import (
    SupportTicket,
    SupportTicketAttachment,
    SupportTicketComment,
    SupportTicketSlaStatus,
    SupportTicketStatus,
)
from app.models.user_notification_preferences import UserNotificationChannel, UserNotificationPreference
from app.models.subscriptions_v1 import SubscriptionPlan, SubscriptionPlanModule
from app.schemas.client_cards_v1 import (
    BulkApplyTemplateRequest,
    BulkCardAccessRequest,
    BulkCardRequest,
    BulkCardResponse,
    CardAccessGrantRequest,
    CardAccessListResponse,
    CardAccessOut,
    CardCreateRequest,
    CardLimitRequest,
    CardLimitOut,
    CardListResponse,
    CardOut,
    CardTransactionOut,
    CardUpdateRequest,
    LimitTemplateCreateRequest,
    LimitTemplateListResponse,
    LimitTemplateOut,
    LimitTemplateUpdateRequest,
    UserRoleUpdateRequest,
)
from app.schemas.client_portal_v1 import (
    ClientAuditEventSummary,
    ClientAuditEventsResponse,
    ClientOrgIn,
    ClientOrgOut,
    ClientDocSummary,
    ClientDocsListResponse,
    ClientAnalyticsSummaryResponse,
    ClientAnalyticsPeriod,
    ClientAnalyticsSummary,
    ClientAnalyticsTimeseriesPoint,
    ClientAnalyticsTopCard,
    ClientAnalyticsTopDriver,
    ClientAnalyticsTopLists,
    ClientAnalyticsTopStation,
    ClientAnalyticsSupport,
    ClientAnalyticsDrillResponse,
    ClientAnalyticsDrillTransaction,
    ClientAnalyticsSupportDrillItem,
    ClientAnalyticsSupportDrillResponse,
    ClientDashboardResponse,
    ClientDashboardWidget,
    ExportJobCreateRequest,
    ExportJobCreateResponse,
    ExportJobListResponse,
    ExportJobOut,
    ReportScheduleCreateRequest,
    ReportScheduleDelivery,
    ReportScheduleListResponse,
    ReportScheduleOut,
    ReportScheduleUpdateRequest,
    ClientSubscriptionOut,
    ClientSubscriptionSelectRequest,
    ClientUserInviteRequest,
    ClientUserSummary,
    ClientUsersResponse,
    ContractInfo,
    ContractSignRequest,
)
from app.schemas.service_slo import (
    ServiceSloBreachListResponse,
    ServiceSloBreachOut,
    ServiceSloCreateRequest,
    ServiceSloListResponse,
    ServiceSloOut,
    ServiceSloUpdateRequest,
)
from app.schemas.support_tickets import (
    SupportTicketAttachmentComplete,
    SupportTicketAttachmentInit,
    SupportTicketAttachmentInitResponse,
    SupportTicketAttachmentListResponse,
    SupportTicketAttachmentOut,
    SupportTicketCommentCreate,
    SupportTicketCommentOut,
    SupportTicketCreate,
    SupportTicketDetail,
    SupportTicketListResponse,
    SupportTicketOut,
)
from app.schemas.helpdesk import (
    HelpdeskIntegrationOut,
    HelpdeskIntegrationPatch,
    HelpdeskIntegrationResponse,
    HelpdeskIntegrationUpsert,
    HelpdeskTicketLinkOut,
    HelpdeskTicketLinkResponse,
)
from app.schemas.subscriptions import SubscriptionPlanOut
from app.schemas.user_notification_preferences import (
    UserNotificationEventType,
    UserNotificationPreferenceOut,
    UserNotificationPreferencesPatch,
    UserNotificationPreferencesResponse,
)
from app.services import client_auth
from app.api.dependencies.client import client_portal_user
from app.services.subscription_service import (
    DEFAULT_TENANT_ID,
    assign_plan_to_client,
    ensure_free_subscription,
    get_client_subscription,
    list_plans,
)
from app.routers.subscriptions_v1 import _build_plan_out
from app.services.s3_storage import S3Storage
from app.services.documents_storage import DocumentsStorage
from app.services.audit_service import AuditService, request_context_from_request
from app.models.audit_log import AuditLog, AuditVisibility
from app.celery_client import celery_client
from app.services.email_service import build_idempotency_key, enqueue_templated_email
from app.services.email_templates import build_portal_url
from app.services.entitlements_service import assert_module_enabled
from app.services.export_metrics import metrics as export_metrics
from app.services.report_schedule_metrics import metrics as report_schedule_metrics
from app.services.reports_render import ExportRenderValidationError, normalize_filters
from app.services.report_schedules import (
    ReportScheduleValidationError,
    compute_next_run_at,
    normalize_delivery_roles,
    normalize_schedule_meta,
    validate_timezone,
)
from app.services.service_slo import (
    SloObjectiveError,
    build_slo_health,
    format_objective,
    format_observed,
    resolve_window_bounds,
    validate_objective,
)
from app.services.timezones import format_datetime_for_user, resolve_user_timezone_info
from app.services.timezones import resolve_user_timezone
from app.services.support_attachment_storage import SupportAttachmentStorage
from app.services.support_ticket_sla import (
    initialize_support_ticket_sla,
    load_support_ticket_sla_config,
    mark_first_response,
    mark_resolution,
    refresh_sla_breaches,
    sla_remaining_minutes,
)
from app.services.helpdesk_service import (
    HELPDESK_INBOUND_SOURCE,
    build_close_payload,
    build_comment_payload,
    build_idempotency_for_close,
    build_idempotency_for_comment,
    build_idempotency_for_ticket,
    build_ticket_payload,
    enqueue_helpdesk_event,
    get_active_integration,
    get_integration,
    get_integration_last_error,
    integration_payload_from_config,
    schedule_helpdesk_outbox,
)
from neft_shared.settings import get_settings

router = APIRouter(prefix="/client", tags=["client-portal-v1"])
settings = get_settings()
logger = logging.getLogger(__name__)

_CONTRACT_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "assets" / "client_onboarding_contract_v1.pdf"
_DOC_TYPE_ALIASES = {
    "CONTRACT": DocumentType.OFFER,
    "INVOICE": DocumentType.INVOICE,
    "ACT": DocumentType.ACT,
    "RECONCILIATION_ACT": DocumentType.RECONCILIATION_ACT,
}
_LIMIT_TEMPLATE_TYPES = {"AMOUNT", "LITERS", "COUNT"}
_LIMIT_TEMPLATE_WINDOWS = {"DAY", "WEEK", "MONTH"}
_LIMIT_TEMPLATE_WINDOW_PREFIX = {"DAY": "DAILY", "WEEK": "WEEKLY", "MONTH": "MONTHLY"}
MAX_EXPORT_ROWS = 5000
SUPPORT_ATTACHMENT_MAX_SIZE = 10 * 1024 * 1024
SUPPORT_ATTACHMENT_ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/jpeg",
    "image/png",
    "text/csv",
    "text/plain",
}
USER_NOTIFICATION_EVENTS = [
    UserNotificationEventType.EXPORT_READY,
    UserNotificationEventType.EXPORT_FAILED,
    UserNotificationEventType.SCHEDULED_REPORT_READY,
    UserNotificationEventType.SUPPORT_TICKET_COMMENTED,
    UserNotificationEventType.SUPPORT_SLA_BREACHED,
    UserNotificationEventType.SECURITY_EVENTS,
]
USER_NOTIFICATION_CHANNELS = [UserNotificationChannel.EMAIL, UserNotificationChannel.IN_APP]
DASHBOARD_WIDGETS_BY_ROLE = {
    "OWNER": [
        {"type": "kpi", "key": "total_spend_30d"},
        {"type": "kpi", "key": "transactions_30d"},
        {"type": "chart", "key": "spend_timeseries_30d"},
        {"type": "list", "key": "top_cards"},
        {"type": "health", "key": "health_exports_email"},
        {"type": "health", "key": "support_overview"},
        {"type": "health", "key": "slo_health"},
        {"type": "cta", "key": "owner_actions"},
    ],
    "ACCOUNTANT": [
        {"type": "kpi", "key": "total_spend_30d"},
        {"type": "kpi", "key": "invoices_count_30d"},
        {"type": "list", "key": "recent_documents"},
        {"type": "list", "key": "exports_recent"},
        {"type": "health", "key": "slo_health"},
        {"type": "cta", "key": "accountant_actions"},
    ],
    "FLEET_MANAGER": [
        {"type": "kpi", "key": "active_cards"},
        {"type": "kpi", "key": "blocked_cards"},
        {"type": "chart", "key": "spend_timeseries_30d"},
        {"type": "list", "key": "top_drivers_cards"},
        {"type": "list", "key": "alerts"},
        {"type": "cta", "key": "fleet_actions"},
    ],
    "DRIVER": [
        {"type": "kpi", "key": "my_cards_count"},
        {"type": "list", "key": "recent_transactions"},
        {"type": "list", "key": "card_limits"},
        {"type": "cta", "key": "driver_actions"},
    ],
}


def _load_contract_template() -> bytes:
    if not _CONTRACT_TEMPLATE_PATH.exists():
        raise HTTPException(status_code=500, detail="contract_template_missing")
    return _CONTRACT_TEMPLATE_PATH.read_bytes()


def _store_contract_pdf(client_id: str, contract_id: str, payload: bytes) -> str:
    storage = S3Storage()
    key = f"client-onboarding/{client_id}/{contract_id}/contract_v1.pdf"
    storage.put_object(key, payload, content_type="application/pdf")
    return storage.get_url(key)


def _get_or_create_onboarding(db: Session, *, owner_id: str, client: Client) -> ClientOnboarding:
    onboarding = (
        db.query(ClientOnboarding)
        .filter(ClientOnboarding.client_id == str(client.id), ClientOnboarding.owner_user_id == owner_id)
        .one_or_none()
    )
    if onboarding:
        return onboarding
    onboarding = ClientOnboarding(
        client_id=str(client.id),
        owner_user_id=owner_id,
        step="CONTRACT",
        status="DRAFT",
    )
    db.add(onboarding)
    db.flush()
    return onboarding


def _resolve_owner_id(token: dict) -> str:
    owner_id = str(token.get("user_id") or token.get("sub") or "").strip()
    if not owner_id:
        raise HTTPException(status_code=403, detail="missing_owner")
    return owner_id


def _resolve_client(db: Session, token: dict) -> Client | None:
    client_id = token.get("client_id")
    if not client_id:
        owner_id = str(token.get("user_id") or token.get("sub") or "").strip()
        if not owner_id:
            return None
        onboarding = (
            db.query(ClientOnboarding)
            .filter(ClientOnboarding.owner_user_id == owner_id)
            .order_by(ClientOnboarding.created_at.desc())
            .first()
        )
        if not onboarding:
            return None
        return db.query(Client).filter(Client.id == onboarding.client_id).one_or_none()
    return db.query(Client).filter(Client.id == str(client_id)).one_or_none()


def _plan_modules_map(db: Session, *, plan_id: str) -> tuple[dict[str, dict], dict[str, dict]]:
    modules: dict[str, dict] = {}
    limits: dict[str, dict] = {}
    items = (
        db.query(SubscriptionPlanModule)
        .filter(SubscriptionPlanModule.plan_id == plan_id)
        .order_by(SubscriptionPlanModule.module_code.asc())
        .all()
    )
    for item in items:
        modules[str(item.module_code)] = {
            "enabled": bool(item.enabled),
            "tier": item.tier,
            "limits": item.limits or {},
        }
        if item.limits:
            limits[str(item.module_code)] = item.limits
    return modules, limits


def _normalize_roles(token: dict) -> list[str]:
    roles = token.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    if token.get("role"):
        roles.append(token["role"])
    return [str(item).upper() for item in roles]


def _resolve_dashboard_role(token: dict) -> str:
    roles = set(_normalize_roles(token))
    if roles.intersection({"CLIENT_OWNER", "CLIENT_ADMIN", "OWNER", "ADMIN"}):
        return "OWNER"
    if "CLIENT_ACCOUNTANT" in roles:
        return "ACCOUNTANT"
    if "CLIENT_FLEET_MANAGER" in roles:
        return "FLEET_MANAGER"
    if roles.intersection({"CLIENT_USER", "DRIVER"}):
        return "DRIVER"
    return "OWNER"


def _notification_preferences_from_db(
    user_id: str,
    org_id: str,
    preferences: list[UserNotificationPreference],
) -> list[UserNotificationPreferenceOut]:
    pref_map = {(pref.event_type, UserNotificationChannel(pref.channel)): pref for pref in preferences}
    items: list[UserNotificationPreferenceOut] = []
    for event_type in USER_NOTIFICATION_EVENTS:
        event_key = event_type.value
        for channel in USER_NOTIFICATION_CHANNELS:
            pref = pref_map.get((event_key, channel))
            enabled = bool(pref.enabled) if pref else True
            if channel == UserNotificationChannel.IN_APP:
                enabled = True
            items.append(
                UserNotificationPreferenceOut(
                    user_id=user_id,
                    org_id=org_id,
                    event_type=event_type,
                    channel=channel,
                    enabled=enabled,
                    updated_at=pref.updated_at if pref else None,
                )
            )
    return items


def _notification_preferences_snapshot(items: list[UserNotificationPreferenceOut]) -> list[dict[str, object]]:
    return [
        {
            "event_type": item.event_type.value,
            "channel": item.channel.value,
            "enabled": item.enabled,
        }
        for item in items
    ]


def _is_card_admin(token: dict) -> bool:
    roles = set(_normalize_roles(token))
    return bool(roles.intersection({"CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_FLEET_MANAGER"}))


def _is_user_admin(token: dict) -> bool:
    roles = set(_normalize_roles(token))
    return bool(roles.intersection({"CLIENT_OWNER", "CLIENT_ADMIN"}))


def _is_driver(token: dict) -> bool:
    roles = set(_normalize_roles(token))
    return bool(roles.intersection({"CLIENT_USER", "DRIVER"}))


def _ensure_analytics_access(token: dict) -> None:
    roles = set(_normalize_roles(token))
    allowed_roles = {
        "CLIENT_OWNER",
        "CLIENT_ADMIN",
        "CLIENT_ACCOUNTANT",
        "CLIENT_FLEET_MANAGER",
        "OWNER",
        "ADMIN",
    }
    if not roles.intersection(allowed_roles):
        raise HTTPException(status_code=403, detail="forbidden")


def _support_ticket_org_id(token: dict) -> str:
    org_id = token.get("client_id") or token.get("org_id")
    if not org_id:
        raise HTTPException(status_code=403, detail="missing_org")
    return str(org_id)


def _support_ticket_user_id(token: dict) -> str:
    user_id = str(token.get("user_id") or token.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=403, detail="missing_user")
    return user_id


def _notification_user_email(token: dict) -> str | None:
    email = token.get("email")
    if email:
        return str(email)
    return None


def _resolve_employee_email(db: Session, *, org_id: str, user_id: str) -> str | None:
    employee = (
        db.query(ClientEmployee)
        .filter(ClientEmployee.client_id == org_id)
        .filter(ClientEmployee.id == user_id)
        .one_or_none()
    )
    if employee and employee.email:
        return employee.email
    return None


def _email_idempotency_key(*, event_type: str, org_id: str, user_id: str, request_id: str | None) -> str | None:
    if not request_id:
        return build_idempotency_key(event_type, org_id, user_id, uuid4().hex)
    return build_idempotency_key(event_type, org_id, user_id, request_id)


def _drill_transaction_cursor(tx: FuelTransaction) -> str:
    return f"{tx.occurred_at.isoformat()}|{tx.id}"


def _support_ticket_cursor(ticket: SupportTicket) -> str:
    return f"{ticket.created_at.isoformat()}|{ticket.id}"


def _build_drill_transactions_query(
    db: Session,
    *,
    client_id: str,
    start_dt: datetime,
    end_dt: datetime,
) -> Query:
    return (
        db.query(FuelTransaction, FuelCard, FleetDriver, FuelStation)
        .join(FuelCard, FuelCard.id == FuelTransaction.card_id)
        .join(FuelStation, FuelStation.id == FuelTransaction.station_id)
        .outerjoin(FleetDriver, FleetDriver.id == FuelTransaction.driver_id)
        .filter(
            FuelTransaction.client_id == client_id,
            FuelTransaction.occurred_at >= start_dt,
            FuelTransaction.occurred_at < end_dt,
            FuelTransaction.status == FuelTransactionStatus.SETTLED,
        )
    )


def _notify_support_ticket(
    db: Session,
    *,
    ticket: SupportTicket,
    event_type: str,
    title: str,
    body: str,
    target_user_id: str | None,
    email_to: str | None = None,
    email_idempotency_key: str | None = None,
) -> None:
    link = f"/client/support/{ticket.id}"
    create_notification(
        db,
        org_id=str(ticket.org_id),
        event_type=event_type,
        severity=ClientNotificationSeverity.INFO,
        title=title,
        body=body,
        link=link,
        target_user_id=target_user_id,
        target_roles=ADMIN_TARGET_ROLES,
        entity_type="support_ticket",
        entity_id=str(ticket.id),
    )
    if event_type == "support_ticket_commented" and email_to:
        enqueue_templated_email(
            db,
            template_key="support_ticket_commented",
            to=[email_to],
            idempotency_key=email_idempotency_key
            or build_idempotency_key(event_type, str(ticket.org_id), str(ticket.id)),
            org_id=str(ticket.org_id),
            user_id=target_user_id,
            context={
                "body": body,
                "link": build_portal_url(link),
                "title": title,
            },
        )


def _notify_support_sla_breaches(db: Session, *, ticket: SupportTicket, events: list[str]) -> None:
    if not events:
        return
    email_to = _resolve_employee_email(db, org_id=str(ticket.org_id), user_id=str(ticket.created_by_user_id))
    if not email_to:
        return
    link = build_portal_url(f"/client/support/{ticket.id}")
    employee = (
        db.query(ClientEmployee)
        .filter(ClientEmployee.id == str(ticket.created_by_user_id), ClientEmployee.client_id == str(ticket.org_id))
        .one_or_none()
    )
    org = db.query(CRMClient).filter(CRMClient.id == str(ticket.org_id)).one_or_none()
    template_map = {
        "support_sla_first_response_breached": "support_sla_first_response_breached",
        "support_sla_resolution_breached": "support_sla_resolution_breached",
    }
    for event_type in events:
        template_key = template_map.get(event_type)
        if not template_key:
            continue
        deadline = (
            ticket.resolution_due_at
            if event_type == "support_sla_resolution_breached"
            else ticket.first_response_due_at
        )
        formatted_deadline, tz_name = format_datetime_for_user(
            db,
            value=deadline,
            user=employee,
            org=org,
        )
        body = "Нарушен SLA по тикету поддержки." if "resolution" in event_type else "Нарушен SLA первого ответа."
        enqueue_templated_email(
            db,
            template_key=template_key,
            to=[email_to],
            idempotency_key=build_idempotency_key(event_type, str(ticket.org_id), str(ticket.id), event_type),
            org_id=str(ticket.org_id),
            user_id=str(ticket.created_by_user_id),
            context={
                "body": body,
                "link": link,
                "title": ticket.subject,
                "deadline_at": formatted_deadline,
                "timezone": tz_name,
            },
        )


def _notify_export_ready(
    db: Session,
    *,
    org_id: str,
    user_id: str,
    title: str,
    body: str,
    email_to: str | None,
    export_format: str = "CSV",
    email_idempotency_key: str | None = None,
) -> None:
    employee = (
        db.query(ClientEmployee)
        .filter(ClientEmployee.id == str(user_id), ClientEmployee.client_id == str(org_id))
        .one_or_none()
    )
    org = db.query(CRMClient).filter(CRMClient.id == str(org_id)).one_or_none()
    generated_at, tz_name = format_datetime_for_user(
        db,
        value=datetime.now(timezone.utc),
        user=employee,
        org=org,
    )
    create_notification(
        db,
        org_id=org_id,
        event_type="export_ready",
        severity=ClientNotificationSeverity.INFO,
        title=f"{title} ({export_format})",
        body=f"{body} ({export_format}).",
        link="/client/reports",
        target_user_id=user_id,
        entity_type="report_export",
        entity_id=user_id,
        email_to=email_to,
        email_idempotency_key=email_idempotency_key,
        email_context={"generated_at": generated_at, "timezone": tz_name},
    )


def _notify_export_failed(
    db: Session,
    *,
    org_id: str,
    user_id: str,
    title: str,
    body: str,
    email_to: str | None,
    email_idempotency_key: str | None = None,
) -> None:
    create_notification(
        db,
        org_id=org_id,
        event_type="export_failed",
        severity=ClientNotificationSeverity.WARNING,
        title=title,
        body=body,
        link="/client/reports",
        target_user_id=user_id,
        entity_type="report_export",
        entity_id=user_id,
        email_to=email_to,
        email_idempotency_key=email_idempotency_key,
    )


def _is_support_ticket_admin(token: dict) -> bool:
    roles = set(_normalize_roles(token))
    return bool(roles.intersection({"CLIENT_OWNER", "CLIENT_ADMIN", "OWNER", "ADMIN"}))


def _is_support_ticket_staff(token: dict) -> bool:
    roles = set(_normalize_roles(token))
    return bool(roles.intersection({"OWNER", "ADMIN"}))


def _ensure_slo_admin(token: dict) -> None:
    roles = set(_normalize_roles(token))
    if not roles.intersection({"CLIENT_OWNER", "CLIENT_ADMIN", "OWNER", "ADMIN"}):
        raise HTTPException(status_code=403, detail="forbidden")


def _serialize_support_ticket(ticket: SupportTicket) -> SupportTicketOut:
    now = datetime.now(timezone.utc)
    first_response_reference = ticket.first_response_at or now
    resolution_reference = ticket.resolved_at or now
    return SupportTicketOut(
        id=str(ticket.id),
        org_id=str(ticket.org_id),
        created_by_user_id=str(ticket.created_by_user_id),
        subject=ticket.subject,
        message=ticket.message,
        status=ticket.status,
        priority=ticket.priority,
        first_response_due_at=ticket.first_response_due_at,
        first_response_at=ticket.first_response_at,
        resolution_due_at=ticket.resolution_due_at,
        resolved_at=ticket.resolved_at,
        sla_first_response_status=ticket.sla_first_response_status or SupportTicketSlaStatus.PENDING,
        sla_resolution_status=ticket.sla_resolution_status or SupportTicketSlaStatus.PENDING,
        sla_first_response_remaining_minutes=sla_remaining_minutes(
            due_at=ticket.first_response_due_at,
            reference_time=first_response_reference,
        ),
        sla_resolution_remaining_minutes=sla_remaining_minutes(
            due_at=ticket.resolution_due_at,
            reference_time=resolution_reference,
        ),
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def _serialize_support_ticket_comment(comment: SupportTicketComment) -> SupportTicketCommentOut:
    return SupportTicketCommentOut(
        user_id=str(comment.user_id),
        message=comment.message,
        created_at=comment.created_at,
    )


def _serialize_support_ticket_attachment(attachment: SupportTicketAttachment) -> SupportTicketAttachmentOut:
    return SupportTicketAttachmentOut(
        id=str(attachment.id),
        ticket_id=str(attachment.ticket_id),
        org_id=str(attachment.org_id),
        uploaded_by_user_id=str(attachment.uploaded_by_user_id),
        file_name=attachment.file_name,
        content_type=attachment.content_type,
        size=attachment.size,
        object_key=attachment.object_key,
        created_at=attachment.created_at,
    )


def _serialize_helpdesk_integration(
    integration: HelpdeskIntegration,
    *,
    last_error: str | None,
) -> HelpdeskIntegrationOut:
    payload = integration_payload_from_config(integration.config_json or {})
    return HelpdeskIntegrationOut(
        id=str(integration.id),
        org_id=str(integration.org_id),
        provider=integration.provider,
        status=integration.status,
        base_url=payload.get("base_url"),
        project_id=payload.get("project_id"),
        brand_id=payload.get("brand_id"),
        last_error=last_error,
        created_at=integration.created_at,
        updated_at=integration.updated_at,
    )


def _serialize_helpdesk_ticket_link(link: HelpdeskTicketLink) -> HelpdeskTicketLinkOut:
    return HelpdeskTicketLinkOut(
        id=str(link.id),
        org_id=str(link.org_id),
        internal_ticket_id=str(link.internal_ticket_id),
        provider=link.provider,
        external_ticket_id=link.external_ticket_id,
        external_url=link.external_url,
        status=link.status,
        last_sync_at=link.last_sync_at,
    )


def _enqueue_helpdesk_outbox(
    db: Session,
    *,
    ticket: SupportTicket,
    event_type: HelpdeskOutboxEventType,
    payload: dict,
    idempotency_key: str,
) -> HelpdeskOutbox | None:
    integration = get_active_integration(db, org_id=str(ticket.org_id))
    if not integration:
        return None
    outbox = enqueue_helpdesk_event(
        db,
        org_id=str(ticket.org_id),
        provider=integration.provider,
        internal_ticket_id=str(ticket.id),
        event_type=event_type,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    db.flush()
    try:
        schedule_helpdesk_outbox(outbox)
    except Exception as exc:  # noqa: BLE001
        outbox.status = HelpdeskOutboxStatus.FAILED
        outbox.last_error = "celery_not_available"
        outbox.next_retry_at = None
        logger.warning(
            "helpdesk_outbox.enqueue_failed",
            extra={
                "outbox_id": str(outbox.id),
                "org_id": str(ticket.org_id),
                "error": str(exc),
            },
        )
    return outbox


def _load_support_ticket(db: Session, *, ticket_id: str, token: dict) -> SupportTicket:
    org_id = _support_ticket_org_id(token)
    user_id = _support_ticket_user_id(token)
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).one_or_none()
    if not ticket or str(ticket.org_id) != org_id:
        raise HTTPException(status_code=404, detail="support_ticket_not_found")
    if not _is_support_ticket_admin(token) and str(ticket.created_by_user_id) != user_id:
        raise HTTPException(status_code=403, detail="forbidden")
    return ticket


def _validate_support_attachment(*, size: int, content_type: str) -> None:
    if size > SUPPORT_ATTACHMENT_MAX_SIZE:
        raise HTTPException(status_code=413, detail="attachment_too_large")
    if content_type.lower() not in SUPPORT_ATTACHMENT_ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="attachment_type_not_allowed")


def _validate_helpdesk_config(provider: str, config: dict) -> None:
    if provider == "zendesk":
        if not config.get("base_url"):
            raise HTTPException(status_code=422, detail="helpdesk_base_url_required")
        if not config.get("api_email") or not config.get("api_token"):
            raise HTTPException(status_code=422, detail="helpdesk_credentials_required")


def _ensure_report_access(token: dict, allowed_roles: set[str]) -> None:
    roles = set(_normalize_roles(token))
    if not roles.intersection(allowed_roles):
        raise HTTPException(status_code=403, detail="forbidden")


_EXPORT_JOB_ROLES: dict[ExportJobReportType, set[str]] = {
    ExportJobReportType.CARDS: {"CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_FLEET_MANAGER"},
    ExportJobReportType.USERS: {"CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT"},
    ExportJobReportType.TRANSACTIONS: {
        "CLIENT_OWNER",
        "CLIENT_ADMIN",
        "CLIENT_ACCOUNTANT",
        "CLIENT_FLEET_MANAGER",
    },
    ExportJobReportType.DOCUMENTS: {"CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT"},
    ExportJobReportType.AUDIT: {"CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT"},
    ExportJobReportType.SUPPORT: {"CLIENT_OWNER", "CLIENT_ADMIN"},
}


def _ensure_export_job_access(token: dict, report_type: ExportJobReportType) -> None:
    allowed_roles = _EXPORT_JOB_ROLES.get(report_type)
    if not allowed_roles:
        raise HTTPException(status_code=422, detail="report_type_not_supported")
    _ensure_report_access(token, allowed_roles)


def _ensure_schedule_admin(token: dict) -> None:
    if not _is_user_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")


def _schedule_delivery_from_request(delivery: ReportScheduleDelivery) -> tuple[bool, bool, list[str]]:
    roles = normalize_delivery_roles(delivery.email_to_roles)
    return delivery.in_app, delivery.email_to_creator, roles


def _schedule_out(schedule: ReportSchedule, *, tzinfo: ZoneInfo) -> ReportScheduleOut:
    next_run_at_local = schedule.next_run_at.astimezone(tzinfo) if schedule.next_run_at else None
    return ReportScheduleOut(
        id=str(schedule.id),
        org_id=str(schedule.org_id),
        created_by_user_id=str(schedule.created_by_user_id),
        report_type=schedule.report_type,
        format=schedule.format,
        filters=schedule.filters_json or {},
        schedule_kind=schedule.schedule_kind,
        schedule_meta=schedule.schedule_meta or {},
        timezone=schedule.timezone,
        delivery=ReportScheduleDelivery(
            in_app=bool(schedule.delivery_in_app),
            email_to_creator=bool(schedule.delivery_email_to_creator),
            email_to_roles=schedule.delivery_email_to_roles or [],
        ),
        status=schedule.status,
        last_run_at=schedule.last_run_at,
        next_run_at=schedule.next_run_at,
        next_run_at_local=next_run_at_local,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


def _export_job_cursor(job: ExportJob) -> str:
    return f"{job.created_at.isoformat()}|{job.id}"


def _parse_export_job_cursor(cursor: str | None) -> tuple[datetime | None, str | None]:
    if not cursor:
        return None, None
    parts = cursor.split("|", maxsplit=1)
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="invalid_cursor")
    try:
        created_at = datetime.fromisoformat(parts[0])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid_cursor") from exc
    return created_at, parts[1]


def _parse_datetime_cursor(cursor: str | None) -> tuple[datetime | None, str | None]:
    if not cursor:
        return None, None
    parts = cursor.split("|", maxsplit=1)
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="invalid_cursor")
    try:
        cursor_dt = datetime.fromisoformat(parts[0])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid_cursor") from exc
    return cursor_dt, parts[1]


def _export_job_eta(job: ExportJob) -> tuple[int | None, datetime | None]:
    if (
        job.estimated_total_rows is None
        or job.started_at is None
        or job.progress_updated_at is None
        or not job.avg_rows_per_sec
        or job.avg_rows_per_sec <= 0
    ):
        return None, None
    remaining = job.estimated_total_rows - job.processed_rows
    if remaining <= 0:
        return 0, datetime.now(timezone.utc)
    eta_seconds = max(0, math.ceil(remaining / job.avg_rows_per_sec))
    return eta_seconds, datetime.now(timezone.utc) + timedelta(seconds=eta_seconds)


def _export_job_to_out(job: ExportJob) -> ExportJobOut:
    eta_seconds, eta_at = _export_job_eta(job)
    return ExportJobOut(
        id=str(job.id),
        org_id=str(job.org_id),
        created_by_user_id=str(job.created_by_user_id),
        report_type=job.report_type,
        format=job.format,
        status=job.status,
        filters=job.filters_json or {},
        file_name=job.file_name,
        content_type=job.content_type,
        row_count=job.row_count,
        processed_rows=job.processed_rows,
        estimated_total_rows=job.estimated_total_rows,
        progress_percent=job.progress_percent,
        avg_rows_per_sec=job.avg_rows_per_sec,
        eta_seconds=eta_seconds,
        eta_at=eta_at,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        expires_at=job.expires_at,
    )


@router.get("/dashboard", response_model=ClientDashboardResponse)
def get_client_dashboard(
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientDashboardResponse:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")

    role = _resolve_dashboard_role(token)
    widgets_config = DASHBOARD_WIDGETS_BY_ROLE.get(role, [])
    tz_name = resolve_user_timezone(db, token=token)
    user_id = str(token.get("user_id") or token.get("sub") or "").strip()

    analytics_keys = {
        "total_spend_30d",
        "transactions_30d",
        "spend_timeseries_30d",
        "top_cards",
        "top_drivers_cards",
        "support_overview",
        "active_cards",
        "blocked_cards",
    }
    analytics_summary: ClientAnalyticsSummaryResponse | None = None
    if role != "DRIVER" and any(widget["key"] in analytics_keys for widget in widgets_config):
        tzinfo = ZoneInfo(tz_name)
        date_to = datetime.now(tzinfo).date()
        date_from = date_to - timedelta(days=29)
        analytics_summary = get_client_analytics_summary(
            request=request,
            date_from=date_from,
            date_to=date_to,
            scope=None,
            timezone_name=tz_name,
            token=token,
            db=db,
        )

    widgets: list[ClientDashboardWidget] = []
    for config in widgets_config:
        key = config["key"]
        data: dict | list | None = None

        if key == "total_spend_30d" and analytics_summary:
            data = {"value": analytics_summary.summary.total_spend, "currency": "RUB"}
        elif key == "transactions_30d" and analytics_summary:
            data = {"value": analytics_summary.summary.transactions_count}
        elif key == "active_cards" and analytics_summary:
            data = {"value": analytics_summary.summary.active_cards}
        elif key == "blocked_cards" and analytics_summary:
            data = {"value": analytics_summary.summary.blocked_cards}
        elif key == "spend_timeseries_30d" and analytics_summary:
            data = [
                {"date": point.date.isoformat(), "value": point.spend} for point in analytics_summary.timeseries
            ]
        elif key == "top_cards" and analytics_summary:
            data = [
                {
                    "id": item.card_id,
                    "label": item.label,
                    "spend": item.spend,
                    "count": item.count,
                }
                for item in analytics_summary.tops.cards
            ]
        elif key == "top_drivers_cards" and analytics_summary:
            data = {
                "drivers": [
                    {
                        "id": item.user_id,
                        "label": item.label,
                        "spend": item.spend,
                        "count": item.count,
                    }
                    for item in analytics_summary.tops.drivers
                ],
                "cards": [
                    {
                        "id": item.card_id,
                        "label": item.label,
                        "spend": item.spend,
                        "count": item.count,
                    }
                    for item in analytics_summary.tops.cards
                ],
            }
        elif key == "support_overview" and analytics_summary:
            data = {
                "open_tickets": analytics_summary.summary.open_tickets,
                "sla_breaches_first": analytics_summary.summary.sla_breaches_first,
                "sla_breaches_resolution": analytics_summary.summary.sla_breaches_resolution,
            }
        elif key == "health_exports_email":
            exports_running = (
                db.query(func.count())
                .filter(ExportJob.org_id == str(client.id), ExportJob.status == ExportJobStatus.RUNNING)
                .scalar()
                or 0
            )
            exports_failed = (
                db.query(func.count())
                .filter(ExportJob.org_id == str(client.id), ExportJob.status == ExportJobStatus.FAILED)
                .scalar()
                or 0
            )
            since = datetime.now(timezone.utc) - timedelta(hours=24)
            email_failures = (
                db.query(func.count())
                .filter(
                    EmailOutbox.org_id == str(client.id),
                    EmailOutbox.status == EmailOutboxStatus.FAILED,
                    EmailOutbox.created_at >= since,
                )
                .scalar()
                or 0
            )
            data = {
                "exports_running": int(exports_running),
                "exports_failed": int(exports_failed),
                "email_failures_24h": int(email_failures),
            }
        elif key == "slo_health":
            data = build_slo_health(db, str(client.id))
        elif key == "invoices_count_30d":
            tzinfo = ZoneInfo(tz_name)
            date_to = datetime.now(tzinfo).date()
            date_from = date_to - timedelta(days=29)
            doc_types = {DocumentType.INVOICE, DocumentType.SUBSCRIPTION_INVOICE, DocumentType.ACT}
            invoices_count = (
                db.query(func.count())
                .filter(
                    Document.client_id == str(client.id),
                    Document.document_type.in_(doc_types),
                    Document.period_to >= date_from,
                    Document.period_to <= date_to,
                )
                .scalar()
                or 0
            )
            data = {"value": int(invoices_count)}
        elif key == "recent_documents":
            doc_types = {DocumentType.INVOICE, DocumentType.SUBSCRIPTION_INVOICE, DocumentType.ACT}
            documents = (
                db.query(Document)
                .filter(Document.client_id == str(client.id), Document.document_type.in_(doc_types))
                .order_by(Document.period_to.desc())
                .limit(5)
                .all()
            )
            data = [
                {
                    "id": str(doc.id),
                    "type": doc.document_type.value,
                    "status": doc.status.value,
                    "date": doc.period_to.isoformat(),
                }
                for doc in documents
            ]
        elif key == "exports_recent":
            if not user_id:
                data = []
            else:
                query = db.query(ExportJob).filter(ExportJob.org_id == str(client.id))
                if not _is_user_admin(token):
                    query = query.filter(ExportJob.created_by_user_id == user_id)
                jobs = query.order_by(ExportJob.created_at.desc()).limit(5).all()
                data = [
                    {
                        "id": item.id,
                        "report_type": item.report_type.value,
                        "status": item.status.value,
                        "created_at": item.created_at.isoformat(),
                        "eta_at": item.eta_at.isoformat() if item.eta_at else None,
                    }
                    for item in (_export_job_to_out(job) for job in jobs)
                ]
        elif key == "my_cards_count":
            card_ids = _accessible_card_ids(db, token=token, client_id=str(client.id))
            data = {"value": len(card_ids)}
        elif key == "recent_transactions":
            card_ids = _accessible_card_ids(db, token=token, client_id=str(client.id))
            if card_ids:
                rows = (
                    db.query(FuelTransaction, FuelCard.masked_pan, FuelCard.card_alias)
                    .join(FuelCard, FuelCard.id == FuelTransaction.card_id)
                    .filter(
                        FuelTransaction.client_id == str(client.id),
                        FuelTransaction.card_id.in_(card_ids),
                        FuelTransaction.status == FuelTransactionStatus.SETTLED,
                    )
                    .order_by(FuelTransaction.occurred_at.desc())
                    .limit(5)
                    .all()
                )
                data = [
                    {
                        "id": str(tx.id),
                        "occurred_at": tx.occurred_at.isoformat(),
                        "amount": int(tx.amount_total_minor) / 100,
                        "currency": tx.currency,
                        "card_label": masked_pan or card_alias or str(tx.card_id),
                    }
                    for tx, masked_pan, card_alias in rows
                ]
            else:
                data = []
        elif key == "card_limits":
            card_ids = _accessible_card_ids(db, token=token, client_id=str(client.id))
            if not card_ids:
                data = []
            else:
                cards = db.query(Card).filter(Card.id.in_(card_ids)).all()
                card_labels = {card.id: card.pan_masked or card.id for card in cards}
                limits = db.query(CardLimit).filter(CardLimit.card_id.in_(card_ids)).all()
                limits_map: dict[str, list[dict]] = {}
                for limit in limits:
                    limits_map.setdefault(limit.card_id, []).append(
                        {
                            "type": limit.limit_type,
                            "amount": float(limit.amount),
                            "currency": limit.currency,
                        }
                    )
                data = [
                    {
                        "card_id": card_id,
                        "label": card_labels.get(card_id, card_id),
                        "limits": limits_map.get(card_id, []),
                    }
                    for card_id in card_ids
                ]
        elif key == "alerts":
            data = []

        widgets.append(ClientDashboardWidget(type=config["type"], key=key, data=data))

    return ClientDashboardResponse(role=role, timezone=tz_name, widgets=widgets)


@router.get("/slo", response_model=ServiceSloListResponse)
def list_service_slos(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ServiceSloListResponse:
    _ensure_slo_admin(token)
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")

    slos = (
        db.query(ServiceSlo)
        .filter(ServiceSlo.org_id == str(client.id))
        .order_by(ServiceSlo.created_at.desc())
        .all()
    )
    now = datetime.now(timezone.utc)
    items: list[ServiceSloOut] = []
    for slo in slos:
        bounds = resolve_window_bounds(slo.window, now)
        breach = (
            db.query(ServiceSloBreach)
            .filter(
                ServiceSloBreach.slo_id == slo.id,
                ServiceSloBreach.window_start == bounds.window_start,
                ServiceSloBreach.window_end == bounds.window_end,
            )
            .one_or_none()
        )
        items.append(
            ServiceSloOut(
                id=str(slo.id),
                org_id=str(slo.org_id),
                service=slo.service,
                metric=slo.metric,
                objective_json=slo.objective_json or {},
                objective=format_objective(slo.metric, slo.objective_json or {}),
                window=slo.window,
                enabled=bool(slo.enabled),
                breach_status=breach.status if breach else None,
                breached_at=breach.breached_at if breach else None,
                window_start=bounds.window_start,
                window_end=bounds.window_end,
                created_at=slo.created_at,
                updated_at=slo.updated_at,
            )
        )
    return ServiceSloListResponse(items=items)


@router.post("/slo", response_model=ServiceSloOut, status_code=201)
def create_service_slo(
    request: Request,
    payload: ServiceSloCreateRequest,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ServiceSloOut:
    _ensure_slo_admin(token)
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")

    try:
        objective = validate_objective(payload.metric, payload.objective_json)
    except SloObjectiveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    slo = ServiceSlo(
        org_id=str(client.id),
        service=payload.service,
        metric=payload.metric,
        objective_json=objective,
        window=payload.window,
        enabled=payload.enabled,
    )
    db.add(slo)
    db.flush()

    request_ctx = request_context_from_request(request, token=token)
    AuditService(db).audit(
        event_type="slo_created",
        entity_type="service_slo",
        entity_id=str(slo.id),
        action="slo_created",
        after={
            "service": slo.service.value,
            "metric": slo.metric.value,
            "window": slo.window.value,
            "enabled": slo.enabled,
        },
        request_ctx=request_ctx,
    )
    db.commit()

    return ServiceSloOut(
        id=str(slo.id),
        org_id=str(slo.org_id),
        service=slo.service,
        metric=slo.metric,
        objective_json=slo.objective_json or {},
        objective=format_objective(slo.metric, slo.objective_json or {}),
        window=slo.window,
        enabled=bool(slo.enabled),
        breach_status=None,
        breached_at=None,
        window_start=None,
        window_end=None,
        created_at=slo.created_at,
        updated_at=slo.updated_at,
    )


@router.patch("/slo/{slo_id}", response_model=ServiceSloOut)
def update_service_slo(
    request: Request,
    slo_id: str,
    payload: ServiceSloUpdateRequest,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ServiceSloOut:
    _ensure_slo_admin(token)
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")

    slo = (
        db.query(ServiceSlo)
        .filter(ServiceSlo.id == slo_id, ServiceSlo.org_id == str(client.id))
        .one_or_none()
    )
    if slo is None:
        raise HTTPException(status_code=404, detail="slo_not_found")

    before = {"objective_json": slo.objective_json, "window": slo.window.value, "enabled": slo.enabled}

    if payload.objective_json is not None:
        try:
            slo.objective_json = validate_objective(slo.metric, payload.objective_json)
        except SloObjectiveError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.window is not None:
        slo.window = payload.window
    if payload.enabled is not None:
        slo.enabled = payload.enabled

    request_ctx = request_context_from_request(request, token=token)
    AuditService(db).audit(
        event_type="slo_updated",
        entity_type="service_slo",
        entity_id=str(slo.id),
        action="slo_updated",
        before=before,
        after={"objective_json": slo.objective_json, "window": slo.window.value, "enabled": slo.enabled},
        request_ctx=request_ctx,
    )
    db.commit()

    bounds = resolve_window_bounds(slo.window)
    breach = (
        db.query(ServiceSloBreach)
        .filter(
            ServiceSloBreach.slo_id == slo.id,
            ServiceSloBreach.window_start == bounds.window_start,
            ServiceSloBreach.window_end == bounds.window_end,
        )
        .one_or_none()
    )
    return ServiceSloOut(
        id=str(slo.id),
        org_id=str(slo.org_id),
        service=slo.service,
        metric=slo.metric,
        objective_json=slo.objective_json or {},
        objective=format_objective(slo.metric, slo.objective_json or {}),
        window=slo.window,
        enabled=bool(slo.enabled),
        breach_status=breach.status if breach else None,
        breached_at=breach.breached_at if breach else None,
        window_start=bounds.window_start,
        window_end=bounds.window_end,
        created_at=slo.created_at,
        updated_at=slo.updated_at,
    )


@router.post("/slo/{slo_id}/disable", response_model=ServiceSloOut)
def disable_service_slo(
    request: Request,
    slo_id: str,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ServiceSloOut:
    _ensure_slo_admin(token)
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")

    slo = (
        db.query(ServiceSlo)
        .filter(ServiceSlo.id == slo_id, ServiceSlo.org_id == str(client.id))
        .one_or_none()
    )
    if slo is None:
        raise HTTPException(status_code=404, detail="slo_not_found")

    slo.enabled = False
    request_ctx = request_context_from_request(request, token=token)
    AuditService(db).audit(
        event_type="slo_disabled",
        entity_type="service_slo",
        entity_id=str(slo.id),
        action="slo_disabled",
        after={"enabled": False},
        request_ctx=request_ctx,
    )
    db.commit()

    bounds = resolve_window_bounds(slo.window)
    breach = (
        db.query(ServiceSloBreach)
        .filter(
            ServiceSloBreach.slo_id == slo.id,
            ServiceSloBreach.window_start == bounds.window_start,
            ServiceSloBreach.window_end == bounds.window_end,
        )
        .one_or_none()
    )
    return ServiceSloOut(
        id=str(slo.id),
        org_id=str(slo.org_id),
        service=slo.service,
        metric=slo.metric,
        objective_json=slo.objective_json or {},
        objective=format_objective(slo.metric, slo.objective_json or {}),
        window=slo.window,
        enabled=bool(slo.enabled),
        breach_status=breach.status if breach else None,
        breached_at=breach.breached_at if breach else None,
        window_start=bounds.window_start,
        window_end=bounds.window_end,
        created_at=slo.created_at,
        updated_at=slo.updated_at,
    )


@router.get("/slo/breaches", response_model=ServiceSloBreachListResponse)
def list_slo_breaches(
    service: ServiceSloService | None = Query(None),
    window: ServiceSloWindow | None = Query(None),
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ServiceSloBreachListResponse:
    _ensure_slo_admin(token)
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")

    query = db.query(ServiceSloBreach, ServiceSlo).join(ServiceSlo, ServiceSlo.id == ServiceSloBreach.slo_id)
    query = query.filter(ServiceSloBreach.org_id == str(client.id))
    if service:
        query = query.filter(ServiceSloBreach.service == service)
    if window:
        query = query.filter(ServiceSloBreach.window == window)
    breaches = query.order_by(ServiceSloBreach.breached_at.desc()).all()

    items: list[ServiceSloBreachOut] = []
    for breach, slo in breaches:
        observed = format_observed(slo.metric, breach.observed_value_json or {}) or "—"
        items.append(
            ServiceSloBreachOut(
                service=breach.service,
                metric=breach.metric,
                objective=format_objective(slo.metric, slo.objective_json or {}),
                window=breach.window,
                observed=observed,
                status=breach.status,
                breached_at=breach.breached_at,
            )
        )
    return ServiceSloBreachListResponse(items=items)


@router.get("/notification-preferences", response_model=UserNotificationPreferencesResponse)
def list_notification_preferences(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> UserNotificationPreferencesResponse:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    user_id = _resolve_owner_id(token)
    preferences = (
        db.query(UserNotificationPreference)
        .filter(UserNotificationPreference.org_id == str(client.id))
        .filter(UserNotificationPreference.user_id == user_id)
        .all()
    )
    items = _notification_preferences_from_db(user_id, str(client.id), preferences)
    return UserNotificationPreferencesResponse(items=items)


@router.patch("/notification-preferences", response_model=UserNotificationPreferencesResponse)
def update_notification_preferences(
    payload: UserNotificationPreferencesPatch,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> UserNotificationPreferencesResponse:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    user_id = _resolve_owner_id(token)
    org_id = str(client.id)
    existing = (
        db.query(UserNotificationPreference)
        .filter(UserNotificationPreference.org_id == org_id)
        .filter(UserNotificationPreference.user_id == user_id)
        .all()
    )
    existing_map = {(pref.event_type, UserNotificationChannel(pref.channel)): pref for pref in existing}
    before_items = _notification_preferences_from_db(user_id, org_id, existing)

    for item in payload.items:
        event_type = item.event_type.value
        channel = item.channel
        enabled = bool(item.enabled)
        if channel == UserNotificationChannel.IN_APP:
            enabled = True
        pref = existing_map.get((event_type, channel))
        if pref:
            pref.enabled = enabled
        else:
            pref = UserNotificationPreference(
                user_id=user_id,
                org_id=org_id,
                event_type=event_type,
                channel=channel,
                enabled=enabled,
            )
            db.add(pref)
            existing_map[(event_type, channel)] = pref

    db.commit()
    items = _notification_preferences_from_db(user_id, org_id, list(existing_map.values()))

    AuditService(db).audit(
        event_type="CLIENT_NOTIFICATION_PREFERENCES_UPDATED",
        entity_type="user_notification_preferences",
        entity_id=f"{org_id}:{user_id}",
        action="update",
        visibility=AuditVisibility.INTERNAL,
        before={"items": _notification_preferences_snapshot(before_items)},
        after={"items": _notification_preferences_snapshot(items)},
        request_ctx=request_context_from_request(request, token=token),
    )
    db.commit()
    return UserNotificationPreferencesResponse(items=items)


@router.post("/reports/schedules", response_model=ReportScheduleOut, status_code=201)
def create_report_schedule(
    payload: ReportScheduleCreateRequest,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ReportScheduleOut:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    _ensure_schedule_admin(token)
    _ensure_export_job_access(token, payload.report_type)
    if payload.report_type == ExportJobReportType.SUPPORT and not _is_support_ticket_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")

    try:
        filters = normalize_filters(payload.report_type, payload.filters or {})
    except ExportRenderValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if payload.report_type == ExportJobReportType.AUDIT:
        tenant_id = token.get("tenant_id")
        if tenant_id is None:
            raise HTTPException(status_code=403, detail="missing_tenant")
        filters["tenant_id"] = int(tenant_id)
        allowed_entity_types = _audit_allowed_entity_types(token)
        if allowed_entity_types is not None:
            filters["allowed_entity_types"] = list(allowed_entity_types)

    try:
        schedule_meta = normalize_schedule_meta(payload.schedule_kind, payload.schedule_meta)
    except ReportScheduleValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        delivery_in_app, delivery_email_to_creator, delivery_email_to_roles = _schedule_delivery_from_request(
            payload.delivery
        )
    except ReportScheduleValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    timezone_name = payload.timezone or "Europe/Moscow"
    try:
        validate_timezone(timezone_name)
    except ReportScheduleValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    next_run_at = compute_next_run_at(payload.schedule_kind, schedule_meta, timezone_name)
    user_id = _support_ticket_user_id(token)

    schedule = ReportSchedule(
        org_id=str(client.id),
        created_by_user_id=user_id,
        report_type=payload.report_type,
        format=payload.format,
        filters_json=filters,
        schedule_kind=payload.schedule_kind,
        schedule_meta=schedule_meta,
        timezone=timezone_name,
        delivery_in_app=delivery_in_app,
        delivery_email_to_creator=delivery_email_to_creator,
        delivery_email_to_roles=delivery_email_to_roles,
        status=ReportScheduleStatus.ACTIVE,
        next_run_at=next_run_at,
    )
    db.add(schedule)
    db.flush()
    db.commit()

    _audit_event(
        db,
        request=request,
        token=token,
        event_type="report_schedule_created",
        entity_type="report_schedule",
        entity_id=str(schedule.id),
        action="report_schedule_created",
        after={
            "report_type": schedule.report_type.value,
            "format": schedule.format.value,
            "schedule_kind": schedule.schedule_kind.value,
            "timezone": schedule.timezone,
        },
    )

    tzinfo = resolve_user_timezone_info(db, token=token, schedule=schedule)
    return _schedule_out(schedule, tzinfo=tzinfo)


@router.get("/reports/schedules", response_model=ReportScheduleListResponse)
def list_report_schedules(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ReportScheduleListResponse:
    _ensure_schedule_admin(token)
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    schedules = (
        db.query(ReportSchedule)
        .filter(ReportSchedule.org_id == str(client.id))
        .filter(ReportSchedule.status != ReportScheduleStatus.DISABLED)
        .order_by(ReportSchedule.created_at.desc())
        .all()
    )
    items = [
        _schedule_out(schedule, tzinfo=resolve_user_timezone_info(db, token=token, schedule=schedule))
        for schedule in schedules
    ]
    return ReportScheduleListResponse(items=items)


@router.get("/reports/schedules/{schedule_id}", response_model=ReportScheduleOut)
def get_report_schedule(
    schedule_id: str,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ReportScheduleOut:
    _ensure_schedule_admin(token)
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    schedule = (
        db.query(ReportSchedule)
        .filter(ReportSchedule.id == schedule_id, ReportSchedule.org_id == str(client.id))
        .one_or_none()
    )
    if not schedule or schedule.status == ReportScheduleStatus.DISABLED:
        raise HTTPException(status_code=404, detail="report_schedule_not_found")
    tzinfo = resolve_user_timezone_info(db, token=token, schedule=schedule)
    return _schedule_out(schedule, tzinfo=tzinfo)


@router.patch("/reports/schedules/{schedule_id}", response_model=ReportScheduleOut)
def update_report_schedule(
    schedule_id: str,
    payload: ReportScheduleUpdateRequest,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ReportScheduleOut:
    _ensure_schedule_admin(token)
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    schedule = (
        db.query(ReportSchedule)
        .filter(ReportSchedule.id == schedule_id, ReportSchedule.org_id == str(client.id))
        .one_or_none()
    )
    if not schedule or schedule.status == ReportScheduleStatus.DISABLED:
        raise HTTPException(status_code=404, detail="report_schedule_not_found")

    if payload.schedule_kind is not None and payload.schedule_meta is None:
        raise HTTPException(status_code=422, detail="schedule_meta_required")

    schedule_kind = payload.schedule_kind or schedule.schedule_kind
    schedule_meta_raw = payload.schedule_meta or schedule.schedule_meta or {}
    try:
        schedule_meta = normalize_schedule_meta(schedule_kind, schedule_meta_raw)
    except ReportScheduleValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    filters = schedule.filters_json or {}
    if payload.filters is not None:
        try:
            filters = normalize_filters(schedule.report_type, payload.filters or {})
        except ExportRenderValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if schedule.report_type == ExportJobReportType.AUDIT:
            tenant_id = token.get("tenant_id")
            if tenant_id is None:
                raise HTTPException(status_code=403, detail="missing_tenant")
            filters["tenant_id"] = int(tenant_id)
            allowed_entity_types = _audit_allowed_entity_types(token)
            if allowed_entity_types is not None:
                filters["allowed_entity_types"] = list(allowed_entity_types)
    if payload.format is not None:
        schedule.format = payload.format
    schedule.filters_json = filters
    schedule.schedule_kind = schedule_kind
    schedule.schedule_meta = schedule_meta
    if payload.timezone is not None:
        try:
            validate_timezone(payload.timezone)
        except ReportScheduleValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        schedule.timezone = payload.timezone

    if payload.delivery is not None:
        try:
            delivery_in_app, delivery_email_to_creator, delivery_email_to_roles = _schedule_delivery_from_request(
                payload.delivery
            )
        except ReportScheduleValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        schedule.delivery_in_app = delivery_in_app
        schedule.delivery_email_to_creator = delivery_email_to_creator
        schedule.delivery_email_to_roles = delivery_email_to_roles

    if schedule.status == ReportScheduleStatus.ACTIVE:
        schedule.next_run_at = compute_next_run_at(schedule.schedule_kind, schedule.schedule_meta, schedule.timezone)

    db.add(schedule)
    db.commit()

    _audit_event(
        db,
        request=request,
        token=token,
        event_type="report_schedule_updated",
        entity_type="report_schedule",
        entity_id=str(schedule.id),
        action="report_schedule_updated",
        after={
            "report_type": schedule.report_type.value,
            "format": schedule.format.value,
            "schedule_kind": schedule.schedule_kind.value,
            "timezone": schedule.timezone,
        },
    )

    tzinfo = resolve_user_timezone_info(db, token=token, schedule=schedule)
    return _schedule_out(schedule, tzinfo=tzinfo)


@router.post("/reports/schedules/{schedule_id}/pause", response_model=ReportScheduleOut)
def pause_report_schedule(
    schedule_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ReportScheduleOut:
    _ensure_schedule_admin(token)
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    schedule = (
        db.query(ReportSchedule)
        .filter(ReportSchedule.id == schedule_id, ReportSchedule.org_id == str(client.id))
        .one_or_none()
    )
    if not schedule or schedule.status == ReportScheduleStatus.DISABLED:
        raise HTTPException(status_code=404, detail="report_schedule_not_found")
    schedule.status = ReportScheduleStatus.PAUSED
    schedule.next_run_at = None
    db.add(schedule)
    report_schedule_metrics.mark_skipped("paused")
    db.commit()

    _audit_event(
        db,
        request=request,
        token=token,
        event_type="report_schedule_paused",
        entity_type="report_schedule",
        entity_id=str(schedule.id),
        action="report_schedule_paused",
    )

    tzinfo = resolve_user_timezone_info(db, token=token, schedule=schedule)
    return _schedule_out(schedule, tzinfo=tzinfo)


@router.post("/reports/schedules/{schedule_id}/resume", response_model=ReportScheduleOut)
def resume_report_schedule(
    schedule_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ReportScheduleOut:
    _ensure_schedule_admin(token)
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    schedule = (
        db.query(ReportSchedule)
        .filter(ReportSchedule.id == schedule_id, ReportSchedule.org_id == str(client.id))
        .one_or_none()
    )
    if not schedule or schedule.status == ReportScheduleStatus.DISABLED:
        raise HTTPException(status_code=404, detail="report_schedule_not_found")
    schedule.status = ReportScheduleStatus.ACTIVE
    schedule.next_run_at = compute_next_run_at(schedule.schedule_kind, schedule.schedule_meta, schedule.timezone)
    db.add(schedule)
    db.commit()

    _audit_event(
        db,
        request=request,
        token=token,
        event_type="report_schedule_resumed",
        entity_type="report_schedule",
        entity_id=str(schedule.id),
        action="report_schedule_resumed",
    )

    tzinfo = resolve_user_timezone_info(db, token=token, schedule=schedule)
    return _schedule_out(schedule, tzinfo=tzinfo)


@router.delete("/reports/schedules/{schedule_id}", status_code=204)
def delete_report_schedule(
    schedule_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> None:
    _ensure_schedule_admin(token)
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    schedule = (
        db.query(ReportSchedule)
        .filter(ReportSchedule.id == schedule_id, ReportSchedule.org_id == str(client.id))
        .one_or_none()
    )
    if not schedule or schedule.status == ReportScheduleStatus.DISABLED:
        raise HTTPException(status_code=404, detail="report_schedule_not_found")
    schedule.status = ReportScheduleStatus.DISABLED
    schedule.next_run_at = None
    db.add(schedule)
    report_schedule_metrics.mark_skipped("disabled")
    db.commit()

    _audit_event(
        db,
        request=request,
        token=token,
        event_type="report_schedule_deleted",
        entity_type="report_schedule",
        entity_id=str(schedule.id),
        action="report_schedule_deleted",
    )


def _date_range_bounds(date_from: date | None, date_to: date | None) -> tuple[datetime | None, datetime | None]:
    start = datetime.combine(date_from, time.min) if date_from else None
    end = datetime.combine(date_to, time.max) if date_to else None
    return start, end


def _format_csv_value(value: object | None) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _csv_response(filename: str, headers: list[str], rows: list[list[object | None]]) -> Response:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_format_csv_value(value) for value in row])
    payload = output.getvalue()
    response_headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=payload, media_type="text/csv", headers=response_headers)


def _extract_token_tail(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(char for char in value if char.isdigit())
    if digits:
        return digits[-4:]
    return value[-4:] if len(value) >= 4 else value


def _limits_summary(limits: list[FuelLimit]) -> str | None:
    if not limits:
        return None
    parts: list[str] = []
    for limit in limits:
        period = limit.period.value if isinstance(limit.period, FuelLimitPeriod) else str(limit.period)
        limit_type = limit.limit_type.value if isinstance(limit.limit_type, FuelLimitType) else str(limit.limit_type)
        value = limit.value
        suffix = ""
        if limit.limit_type == FuelLimitType.VOLUME:
            suffix = " L"
        elif limit.currency:
            suffix = f" {limit.currency}"
        parts.append(f"{limit_type}/{period}: {value}{suffix}")
    return "; ".join(parts)


def _audit_export(
    db: Session,
    *,
    request: Request,
    token: dict,
    client_id: str,
    action: str,
    filters: dict[str, object | None],
    row_count: int,
) -> None:
    AuditService(db).audit(
        event_type="CLIENT_REPORT_EXPORT",
        entity_type="report_export",
        entity_id=f"{client_id}:{action}",
        action=action,
        visibility=AuditVisibility.INTERNAL,
        after={"filters": filters, "row_count": row_count},
        request_ctx=request_context_from_request(request, token=token),
    )


_AUDIT_ACCOUNTANT_ENTITY_TYPES = {
    "document",
    "contract",
    "invoice",
    "invoice_thread",
    "document_acknowledgement",
    "closing_package",
    "legal_document",
    "support_ticket",
}


def _audit_allowed_entity_types(token: dict) -> set[str] | None:
    roles = set(_normalize_roles(token))
    if roles.intersection({"CLIENT_OWNER", "CLIENT_ADMIN"}):
        return None
    if "CLIENT_ACCOUNTANT" in roles:
        return _AUDIT_ACCOUNTANT_ENTITY_TYPES
    raise HTTPException(status_code=403, detail="forbidden")


def _audit_actor_label(log: AuditLog) -> str | None:
    return log.actor_email or log.actor_id


def _audit_entity_label(log: AuditLog) -> str | None:
    refs = log.external_refs
    if not isinstance(refs, dict):
        return None
    for key in ("masked_pan", "card_masked_pan", "card_tail", "pan_tail", "token_tail", "label", "number_tail"):
        value = refs.get(key)
        if value:
            return str(value)
    return None


def _audit_summary(log: AuditLog) -> str | None:
    return log.reason or log.action or log.event_type


def _normalize_template_limits(limits: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for item in limits:
        limit_type = str(item.get("type", "")).upper().strip()
        window = str(item.get("window", "")).upper().strip()
        value = item.get("value")
        if limit_type not in _LIMIT_TEMPLATE_TYPES:
            raise HTTPException(status_code=422, detail="invalid_limit_type")
        if window not in _LIMIT_TEMPLATE_WINDOWS:
            raise HTTPException(status_code=422, detail="invalid_limit_window")
        try:
            value_num = float(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="invalid_limit_value") from exc
        if value is None or value_num <= 0:
            raise HTTPException(status_code=422, detail="invalid_limit_value")
        normalized.append({"type": limit_type, "window": window, "value": value_num})
    return normalized


def _limit_type_for_template(limit_type: str, window: str) -> str:
    prefix = _LIMIT_TEMPLATE_WINDOW_PREFIX.get(window.upper().strip())
    if not prefix:
        raise HTTPException(status_code=422, detail="invalid_limit_window")
    return f"{prefix}_{limit_type.upper().strip()}"


def _audit_bulk_payload(card_ids: list[str]) -> dict:
    if len(card_ids) <= 25:
        return {"count": len(card_ids), "card_ids": card_ids}
    digest = sha256(",".join(card_ids).encode("utf-8")).hexdigest()
    return {"count": len(card_ids), "card_ids_hash": digest}


def _build_audit_query(
    db: Session,
    *,
    tenant_id: int,
    allowed_entity_types: set[str] | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
    action: list[str] | None,
    actor: str | None,
    entity_type: str | None,
    entity_id: str | None,
    request_id: str | None,
):
    query = db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id)
    if allowed_entity_types is not None:
        if entity_type and entity_type not in allowed_entity_types:
            return query.filter(AuditLog.id.is_(None))
        query = query.filter(AuditLog.entity_type.in_(allowed_entity_types))
    if from_dt:
        query = query.filter(AuditLog.ts >= from_dt)
    if to_dt:
        query = query.filter(AuditLog.ts <= to_dt)
    if action:
        query = query.filter(AuditLog.action.in_(action))
    if actor:
        like = f"%{actor}%"
        query = query.filter(or_(AuditLog.actor_email.ilike(like), AuditLog.actor_id.ilike(like)))
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        entity_like = f"%{entity_id}%"
        external_refs = cast(AuditLog.external_refs, String)
        query = query.filter(
            or_(AuditLog.entity_id == entity_id, AuditLog.entity_id.ilike(entity_like), external_refs.ilike(entity_like))
        )
    if request_id:
        query = query.filter(AuditLog.request_id == request_id)
    return query


def _ensure_card_access(db: Session, *, token: dict, card_id: str) -> None:
    if _is_card_admin(token):
        return
    if not _is_driver(token):
        raise HTTPException(status_code=403, detail="forbidden")
    user_id = str(token.get("user_id") or token.get("sub") or "")
    if not user_id:
        raise HTTPException(status_code=403, detail="forbidden")
    access = (
        db.query(CardAccess)
        .filter(CardAccess.card_id == card_id, CardAccess.user_id == user_id)
        .filter(CardAccess.effective_to.is_(None))
        .one_or_none()
    )
    if not access:
        raise HTTPException(status_code=403, detail="forbidden")


def _accessible_card_ids(db: Session, *, token: dict, client_id: str) -> list[str]:
    if _is_card_admin(token):
        return [card.id for card in db.query(Card.id).filter(Card.client_id == client_id).all()]
    user_id = str(token.get("user_id") or token.get("sub") or "")
    if not user_id:
        return []
    rows = (
        db.query(CardAccess.card_id)
        .filter(CardAccess.client_id == client_id, CardAccess.user_id == user_id)
        .filter(CardAccess.effective_to.is_(None))
        .all()
    )
    return [row[0] for row in rows]


def _resolve_bulk_cards(
    db: Session,
    *,
    token: dict,
    client_id: str,
    card_ids: list[str],
) -> tuple[dict[str, Card], dict[str, str]]:
    cards = db.query(Card).filter(Card.client_id == client_id, Card.id.in_(card_ids)).all()
    card_map = {card.id: card for card in cards}
    failed: dict[str, str] = {}
    for card_id in card_ids:
        if card_id not in card_map:
            failed[card_id] = "not_found"
    if not _is_card_admin(token):
        allowed = set(_accessible_card_ids(db, token=token, client_id=client_id))
        for card_id in list(card_map):
            if card_id not in allowed:
                failed[card_id] = "forbidden"
                card_map.pop(card_id, None)
    return card_map, failed


def _ensure_driver_user(db: Session, *, client_id: str, user_id: str) -> None:
    employee = (
        db.query(ClientEmployee)
        .filter(ClientEmployee.client_id == client_id, ClientEmployee.id == user_id)
        .one_or_none()
    )
    if not employee:
        raise HTTPException(status_code=404, detail="user_not_found")
    role_row = (
        db.query(ClientUserRole)
        .filter(ClientUserRole.client_id == client_id, ClientUserRole.user_id == user_id)
        .one_or_none()
    )
    roles = role_row.roles.split(",") if role_row else []
    if "DRIVER" not in roles and "CLIENT_USER" not in roles:
        raise HTTPException(status_code=409, detail="user_not_driver")


def _audit_event(
    db: Session,
    *,
    request: Request | None,
    token: dict,
    event_type: str,
    entity_type: str,
    entity_id: str,
    before: dict | None = None,
    after: dict | None = None,
    action: str,
    external_refs: dict | None = None,
    reason: str | None = None,
) -> None:
    ctx = request_context_from_request(request, token=token)
    AuditService(db).audit(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before=before,
        after=after,
        visibility=AuditVisibility.INTERNAL,
        request_ctx=ctx,
        external_refs=external_refs,
        reason=reason,
    )


def _export_job_duration_ms(job: ExportJob) -> int | None:
    if job.started_at and job.finished_at:
        return int((job.finished_at - job.started_at).total_seconds() * 1000)
    return None


@router.get("/audit/events", response_model=ClientAuditEventsResponse)
def list_audit_events(
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
    action: list[str] | None = Query(None),
    actor: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    request_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    cursor: int | None = Query(None, ge=0),
) -> ClientAuditEventsResponse:
    _ = request
    allowed_entity_types = _audit_allowed_entity_types(token)
    tenant_id = token.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="missing_tenant")
    query = _build_audit_query(
        db,
        tenant_id=int(tenant_id),
        allowed_entity_types=allowed_entity_types,
        from_dt=from_dt,
        to_dt=to_dt,
        action=action,
        actor=actor,
        entity_type=entity_type,
        entity_id=entity_id,
        request_id=request_id,
    )
    offset = cursor or 0
    logs = query.order_by(AuditLog.ts.desc(), AuditLog.id.desc()).offset(offset).limit(limit + 1).all()
    has_more = len(logs) > limit
    if has_more:
        logs = logs[:limit]
    next_cursor = str(offset + limit) if has_more else None
    org_id = token.get("client_id") or token.get("org_id") or tenant_id

    items = [
        ClientAuditEventSummary(
            id=str(log.id),
            created_at=log.ts,
            org_id=str(org_id) if org_id is not None else None,
            actor_user_id=log.actor_id,
            actor_label=_audit_actor_label(log),
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            entity_label=_audit_entity_label(log),
            request_id=log.request_id,
            ip=str(log.ip) if log.ip else None,
            ua=log.user_agent,
            result=None,
            summary=_audit_summary(log),
        )
        for log in logs
    ]
    return ClientAuditEventsResponse(items=items, next_cursor=next_cursor)


@router.get("/audit/events/export")
def export_audit_events(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
    action: list[str] | None = Query(None),
    actor: str | None = Query(None),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    request_id: str | None = Query(None),
) -> Response:
    allowed_entity_types = _audit_allowed_entity_types(token)
    tenant_id = token.get("tenant_id")
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="missing_tenant")
    query = _build_audit_query(
        db,
        tenant_id=int(tenant_id),
        allowed_entity_types=allowed_entity_types,
        from_dt=from_dt,
        to_dt=to_dt,
        action=action,
        actor=actor,
        entity_type=entity_type,
        entity_id=entity_id,
        request_id=request_id,
    )
    max_rows = 5000
    logs = query.order_by(AuditLog.ts.desc(), AuditLog.id.desc()).limit(max_rows + 1).all()
    if len(logs) > max_rows:
        raise HTTPException(status_code=400, detail="export_limit_exceeded")
    org_id = token.get("client_id") or token.get("org_id") or tenant_id
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "created_at",
            "org_id",
            "actor_user_id",
            "actor_label",
            "action",
            "entity_type",
            "entity_id",
            "entity_label",
            "request_id",
            "ip",
            "ua",
            "result",
            "summary",
        ]
    )
    for log in logs:
        writer.writerow(
            [
                str(log.id),
                log.ts.isoformat(),
                str(org_id) if org_id is not None else "",
                log.actor_id or "",
                _audit_actor_label(log) or "",
                log.action or "",
                log.entity_type or "",
                log.entity_id or "",
                _audit_entity_label(log) or "",
                log.request_id or "",
                str(log.ip) if log.ip else "",
                log.user_agent or "",
                "",
                _audit_summary(log) or "",
            ]
        )
    filename = f"audit_events_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/exports/jobs", response_model=ExportJobCreateResponse, status_code=201)
def create_export_job(
    payload: ExportJobCreateRequest,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ExportJobCreateResponse:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    _ensure_export_job_access(token, payload.report_type)
    user_id = str(token.get("user_id") or token.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=403, detail="missing_user")

    request_id = request.headers.get("x-request-id")
    try:
        filters = normalize_filters(payload.report_type, payload.filters or {})
    except ExportRenderValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if payload.report_type == ExportJobReportType.AUDIT:
        tenant_id = token.get("tenant_id")
        if tenant_id is None:
            raise HTTPException(status_code=403, detail="missing_tenant")
        filters["tenant_id"] = int(tenant_id)
        allowed_entity_types = _audit_allowed_entity_types(token)
        if allowed_entity_types is not None:
            filters["allowed_entity_types"] = list(allowed_entity_types)
    if payload.report_type == ExportJobReportType.SUPPORT and not _is_support_ticket_admin(token):
        filters["created_by_user_id"] = user_id
    if request_id:
        filters["request_id"] = request_id

    job = ExportJob(
        org_id=str(client.id),
        created_by_user_id=user_id,
        report_type=payload.report_type,
        format=payload.format,
        filters_json=filters,
        status=ExportJobStatus.QUEUED,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(job)
    db.flush()
    db.commit()
    export_metrics.mark_created(job.report_type.value, job.format.value)

    try:
        celery_client.send_task("exports.generate_export_job", args=[str(job.id)])
    except Exception as exc:  # noqa: BLE001
        job.status = ExportJobStatus.FAILED
        job.error_message = "celery_not_available"
        db.add(job)
        db.commit()
        export_metrics.mark_completed(job.report_type.value, job.format.value, job.status.value)
        export_metrics.mark_failure("celery")
        raise HTTPException(status_code=503, detail="celery_not_available") from exc

    _audit_event(
        db,
        request=request,
        token=token,
        event_type="export_job_created",
        entity_type="export_job",
        entity_id=str(job.id),
        action="export_job_created",
        after={
            "report_type": job.report_type.value,
            "format": job.format.value,
            "row_count": job.row_count,
            "duration_ms": _export_job_duration_ms(job),
        },
    )

    return ExportJobCreateResponse(id=str(job.id), status=job.status)


@router.get("/exports/jobs", response_model=ExportJobListResponse)
def list_export_jobs(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    status: ExportJobStatus | None = Query(None),
    report_type: ExportJobReportType | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    only_my: bool = Query(False),
) -> ExportJobListResponse:
    if _is_driver(token):
        raise HTTPException(status_code=403, detail="forbidden")
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")

    query = db.query(ExportJob).filter(ExportJob.org_id == str(client.id))
    if status:
        query = query.filter(ExportJob.status == status)
    if report_type:
        query = query.filter(ExportJob.report_type == report_type)

    user_id = str(token.get("user_id") or token.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=403, detail="missing_user")
    if not _is_user_admin(token) or only_my:
        query = query.filter(ExportJob.created_by_user_id == user_id)

    cursor_created_at, cursor_id = _parse_export_job_cursor(cursor)
    if cursor_created_at and cursor_id:
        query = query.filter(
            or_(
                ExportJob.created_at < cursor_created_at,
                and_(ExportJob.created_at == cursor_created_at, ExportJob.id < cursor_id),
            )
        )

    jobs = query.order_by(ExportJob.created_at.desc(), ExportJob.id.desc()).limit(limit + 1).all()
    has_more = len(jobs) > limit
    if has_more:
        jobs = jobs[:limit]
    next_cursor = _export_job_cursor(jobs[-1]) if has_more and jobs else None
    return ExportJobListResponse(items=[_export_job_to_out(job) for job in jobs], next_cursor=next_cursor)


@router.get("/exports/jobs/{job_id}", response_model=ExportJobOut)
def get_export_job(
    job_id: str,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ExportJobOut:
    if _is_driver(token):
        raise HTTPException(status_code=403, detail="forbidden")
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    job = db.query(ExportJob).filter(ExportJob.id == job_id).one_or_none()
    if not job or str(job.org_id) != str(client.id):
        raise HTTPException(status_code=404, detail="export_job_not_found")
    user_id = str(token.get("user_id") or token.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=403, detail="missing_user")
    if not _is_user_admin(token) and job.created_by_user_id != user_id:
        raise HTTPException(status_code=403, detail="forbidden")
    return _export_job_to_out(job)


@router.get("/exports/jobs/{job_id}/download")
def download_export_job(
    job_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> Response:
    if _is_driver(token):
        raise HTTPException(status_code=403, detail="forbidden")
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    job = db.query(ExportJob).filter(ExportJob.id == job_id).one_or_none()
    if not job or str(job.org_id) != str(client.id):
        raise HTTPException(status_code=404, detail="export_job_not_found")
    user_id = str(token.get("user_id") or token.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=403, detail="missing_user")
    if not _is_user_admin(token) and job.created_by_user_id != user_id:
        raise HTTPException(status_code=403, detail="forbidden")
    if job.expires_at and job.expires_at < datetime.now(timezone.utc):
        if job.status != ExportJobStatus.EXPIRED:
            job.status = ExportJobStatus.EXPIRED
            job.file_object_key = None
            job.content_type = None
            db.add(job)
            AuditService(db).audit(
                event_type="export_expired",
                entity_type="export_job",
                entity_id=str(job.id),
                action="export_expired",
                after={
                    "report_type": job.report_type.value,
                    "format": job.format.value,
                    "expired_at": job.expires_at.isoformat() if job.expires_at else None,
                },
            )
            db.commit()
        raise HTTPException(status_code=410, detail="export_expired")
    if job.status == ExportJobStatus.EXPIRED:
        raise HTTPException(status_code=410, detail="export_expired")
    if job.status != ExportJobStatus.DONE or not job.file_object_key:
        raise HTTPException(status_code=400, detail="export_not_ready")

    storage = S3Storage(bucket=settings.NEFT_EXPORTS_BUCKET)
    signed_url = storage.presign(job.file_object_key, expires=settings.S3_SIGNED_URL_TTL_SECONDS)
    if not signed_url:
        raise HTTPException(status_code=503, detail="download_unavailable")

    _audit_event(
        db,
        request=request,
        token=token,
        event_type="export_job_downloaded",
        entity_type="export_job",
        entity_id=str(job.id),
        action="export_job_downloaded",
        after={
            "report_type": job.report_type.value,
            "format": job.format.value,
            "row_count": job.row_count,
            "duration_ms": _export_job_duration_ms(job),
        },
    )

    return RedirectResponse(url=signed_url)


@router.get("/helpdesk/integration", response_model=HelpdeskIntegrationResponse)
def get_helpdesk_integration(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> HelpdeskIntegrationResponse:
    if not _is_support_ticket_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    org_id = _support_ticket_org_id(token)
    integration = get_integration(db, org_id=org_id)
    if not integration:
        return HelpdeskIntegrationResponse(integration=None)
    last_error = get_integration_last_error(db, org_id=org_id)
    return HelpdeskIntegrationResponse(integration=_serialize_helpdesk_integration(integration, last_error=last_error))


@router.post("/helpdesk/integration", response_model=HelpdeskIntegrationResponse)
def enable_helpdesk_integration(
    payload: HelpdeskIntegrationUpsert,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> HelpdeskIntegrationResponse:
    if not _is_support_ticket_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    org_id = _support_ticket_org_id(token)
    config = payload.config.model_dump(exclude_none=True)
    if "base_url" in config:
        config["base_url"] = str(config["base_url"]).strip().rstrip("/")
    _validate_helpdesk_config(payload.provider.value, config)
    integration = upsert_integration(
        db,
        org_id=org_id,
        provider=payload.provider,
        config=config,
        status=HelpdeskIntegrationStatus.ACTIVE,
    )
    db.add(integration)
    db.commit()
    db.refresh(integration)
    _audit_event(
        db,
        request=request,
        token=token,
        event_type="helpdesk_integration_enabled",
        entity_type="helpdesk_integration",
        entity_id=str(integration.id),
        action="helpdesk_integration_enabled",
        after={"provider": integration.provider.value, "status": integration.status.value},
    )
    last_error = get_integration_last_error(db, org_id=org_id)
    return HelpdeskIntegrationResponse(integration=_serialize_helpdesk_integration(integration, last_error=last_error))


@router.patch("/helpdesk/integration", response_model=HelpdeskIntegrationResponse)
def update_helpdesk_integration(
    payload: HelpdeskIntegrationPatch,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> HelpdeskIntegrationResponse:
    if not _is_support_ticket_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    org_id = _support_ticket_org_id(token)
    integration = get_integration(db, org_id=org_id)
    if not integration:
        raise HTTPException(status_code=404, detail="integration_not_found")
    if payload.provider:
        integration.provider = payload.provider
    if payload.config:
        existing = integration.config_json or {}
        updates = payload.config.model_dump(exclude_none=True)
        if "base_url" in updates:
            updates["base_url"] = str(updates["base_url"]).strip().rstrip("/")
        existing.update(updates)
        integration.config_json = existing
    _validate_helpdesk_config(integration.provider.value, integration.config_json or {})
    integration.updated_at = datetime.now(timezone.utc)
    db.add(integration)
    db.commit()
    db.refresh(integration)
    _audit_event(
        db,
        request=request,
        token=token,
        event_type="helpdesk_integration_updated",
        entity_type="helpdesk_integration",
        entity_id=str(integration.id),
        action="helpdesk_integration_updated",
        after={"provider": integration.provider.value, "status": integration.status.value},
    )
    last_error = get_integration_last_error(db, org_id=org_id)
    return HelpdeskIntegrationResponse(integration=_serialize_helpdesk_integration(integration, last_error=last_error))


@router.post("/helpdesk/integration/disable", response_model=HelpdeskIntegrationResponse)
def disable_helpdesk_integration(
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> HelpdeskIntegrationResponse:
    if not _is_support_ticket_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    org_id = _support_ticket_org_id(token)
    integration = get_integration(db, org_id=org_id)
    if not integration:
        raise HTTPException(status_code=404, detail="integration_not_found")
    integration.status = HelpdeskIntegrationStatus.DISABLED
    integration.updated_at = datetime.now(timezone.utc)
    db.add(integration)
    db.commit()
    db.refresh(integration)
    _audit_event(
        db,
        request=request,
        token=token,
        event_type="helpdesk_integration_disabled",
        entity_type="helpdesk_integration",
        entity_id=str(integration.id),
        action="helpdesk_integration_disabled",
        after={"provider": integration.provider.value, "status": integration.status.value},
    )
    last_error = get_integration_last_error(db, org_id=org_id)
    return HelpdeskIntegrationResponse(integration=_serialize_helpdesk_integration(integration, last_error=last_error))


@router.get("/helpdesk/tickets/{ticket_id}/link", response_model=HelpdeskTicketLinkResponse)
def get_helpdesk_ticket_link(
    ticket_id: str,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> HelpdeskTicketLinkResponse:
    ticket = _load_support_ticket(db, ticket_id=ticket_id, token=token)
    link = (
        db.query(HelpdeskTicketLink)
        .filter(HelpdeskTicketLink.internal_ticket_id == str(ticket.id))
        .filter(HelpdeskTicketLink.org_id == str(ticket.org_id))
        .one_or_none()
    )
    if not link:
        return HelpdeskTicketLinkResponse(link=None)
    return HelpdeskTicketLinkResponse(link=_serialize_helpdesk_ticket_link(link))


@router.post("/support/tickets", response_model=SupportTicketDetail)
def create_support_ticket(
    payload: SupportTicketCreate,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> SupportTicketDetail:
    org_id = _support_ticket_org_id(token)
    user_id = _support_ticket_user_id(token)
    ticket = SupportTicket(
        org_id=org_id,
        created_by_user_id=user_id,
        subject=payload.subject,
        message=payload.message,
        status=SupportTicketStatus.OPEN,
        priority=payload.priority,
    )
    sla_config = load_support_ticket_sla_config(db, org_id=org_id)
    initialize_support_ticket_sla(ticket, sla_config)
    db.add(ticket)
    db.flush()
    AuditService(db).audit(
        event_type="support_ticket_created",
        entity_type="support_ticket",
        entity_id=str(ticket.id),
        action="support_ticket_created",
        visibility=AuditVisibility.INTERNAL,
        after={
            "status": ticket.status.value,
            "priority": ticket.priority.value,
            "subject": ticket.subject,
        },
        request_ctx=request_context_from_request(request, token=token),
    )
    db.refresh(ticket)
    creator_is_admin = _is_support_ticket_admin(token)
    _notify_support_ticket(
        db,
        ticket=ticket,
        event_type="support_ticket_created",
        title="Тикет создан",
        body=f"Мы получили запрос \"{ticket.subject}\".",
        target_user_id=None if creator_is_admin else user_id,
    )
    created_by_email = _resolve_employee_email(db, org_id=org_id, user_id=user_id) or _notification_user_email(token)
    outbox = _enqueue_helpdesk_outbox(
        db,
        ticket=ticket,
        event_type=HelpdeskOutboxEventType.TICKET_CREATED,
        payload=build_ticket_payload(ticket=ticket, created_by_email=created_by_email, attachments=[]),
        idempotency_key=build_idempotency_for_ticket(HelpdeskOutboxEventType.TICKET_CREATED, str(ticket.id), org_id),
    )
    if outbox:
        _audit_event(
            db,
            request=request,
            token=token,
            event_type="helpdesk_sync_enqueued",
            entity_type="helpdesk_outbox",
            entity_id=str(outbox.id),
            action="helpdesk_sync_enqueued",
            after={
                "event_type": outbox.event_type.value,
                "provider": outbox.provider.value,
                "internal_ticket_id": str(outbox.internal_ticket_id),
            },
        )
        if outbox.status == HelpdeskOutboxStatus.FAILED:
            _audit_event(
                db,
                request=request,
                token=token,
                event_type="helpdesk_sync_failed",
                entity_type="helpdesk_outbox",
                entity_id=str(outbox.id),
                action="helpdesk_sync_failed",
                after={
                    "event_type": outbox.event_type.value,
                    "provider": outbox.provider.value,
                    "internal_ticket_id": str(outbox.internal_ticket_id),
                    "error": outbox.last_error,
                },
            )
    return SupportTicketDetail(**_serialize_support_ticket(ticket).model_dump(), comments=[])


@router.get("/support/tickets", response_model=SupportTicketListResponse)
def list_support_tickets(
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    status: SupportTicketStatus | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    cursor: int | None = Query(None, ge=0),
) -> SupportTicketListResponse:
    org_id = _support_ticket_org_id(token)
    user_id = _support_ticket_user_id(token)
    query = db.query(SupportTicket).filter(SupportTicket.org_id == org_id)
    if status:
        query = query.filter(SupportTicket.status == status)
    if not _is_support_ticket_admin(token):
        query = query.filter(SupportTicket.created_by_user_id == user_id)
    offset = cursor or 0
    rows = query.order_by(SupportTicket.created_at.desc()).offset(offset).limit(limit + 1).all()
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    now = datetime.now(timezone.utc)
    request_ctx = request_context_from_request(request, token=token)
    audit_service = AuditService(db)
    updated = False
    for ticket in rows:
        events = refresh_sla_breaches(ticket, now=now, audit=audit_service, request_ctx=request_ctx)
        if events:
            _notify_support_sla_breaches(db, ticket=ticket, events=events)
            updated = True
    if updated:
        db.flush()
    next_cursor = str(offset + limit) if has_more else None
    items = [_serialize_support_ticket(ticket) for ticket in rows]
    return SupportTicketListResponse(items=items, next_cursor=next_cursor)


@router.get("/support/tickets/{ticket_id}", response_model=SupportTicketDetail)
def get_support_ticket(
    ticket_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> SupportTicketDetail:
    ticket = _load_support_ticket(db, ticket_id=ticket_id, token=token)
    now = datetime.now(timezone.utc)
    request_ctx = request_context_from_request(request, token=token)
    events = refresh_sla_breaches(ticket, now=now, audit=AuditService(db), request_ctx=request_ctx)
    if events:
        _notify_support_sla_breaches(db, ticket=ticket, events=events)
        db.flush()
    comments = (
        db.query(SupportTicketComment)
        .filter(SupportTicketComment.ticket_id == ticket.id)
        .order_by(SupportTicketComment.created_at.asc())
        .all()
    )
    return SupportTicketDetail(
        **_serialize_support_ticket(ticket).model_dump(),
        comments=[_serialize_support_ticket_comment(comment) for comment in comments],
    )


@router.post("/support/tickets/{ticket_id}/comments", response_model=SupportTicketDetail)
def add_support_ticket_comment(
    ticket_id: str,
    payload: SupportTicketCommentCreate,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> SupportTicketDetail:
    user_id = _support_ticket_user_id(token)
    ticket = _load_support_ticket(db, ticket_id=ticket_id, token=token)
    comment = SupportTicketComment(
        ticket_id=str(ticket.id),
        user_id=user_id,
        message=payload.message,
        source="PORTAL",
    )
    ticket.updated_at = datetime.now(timezone.utc)
    audit_service = AuditService(db)
    request_ctx = request_context_from_request(request, token=token)
    if _is_support_ticket_staff(token):
        mark_first_response(ticket, audit=audit_service, request_ctx=request_ctx)
    db.add(comment)
    db.add(ticket)
    db.flush()
    audit_service.audit(
        event_type="support_ticket_commented",
        entity_type="support_ticket",
        entity_id=str(ticket.id),
        action="support_ticket_commented",
        visibility=AuditVisibility.INTERNAL,
        after={"comment_id": str(comment.id)},
        request_ctx=request_ctx,
    )
    db.refresh(ticket)
    email_to = _resolve_employee_email(db, org_id=str(ticket.org_id), user_id=str(ticket.created_by_user_id))
    _notify_support_ticket(
        db,
        ticket=ticket,
        event_type="support_ticket_commented",
        title="Новый комментарий",
        body=f"В тикете \"{ticket.subject}\" появился комментарий.",
        target_user_id=str(ticket.created_by_user_id),
        email_to=email_to,
        email_idempotency_key=build_idempotency_key(
            "support_ticket_commented",
            str(ticket.org_id),
            str(ticket.id),
            str(comment.id),
        ),
    )
    author_email = _resolve_employee_email(db, org_id=str(ticket.org_id), user_id=user_id) or _notification_user_email(
        token
    )
    outbox = None
    if comment.source != HELPDESK_INBOUND_SOURCE:
        outbox = _enqueue_helpdesk_outbox(
            db,
            ticket=ticket,
            event_type=HelpdeskOutboxEventType.COMMENT_ADDED,
            payload=build_comment_payload(ticket=ticket, comment=comment, author_email=author_email),
            idempotency_key=build_idempotency_for_comment(
                HelpdeskOutboxEventType.COMMENT_ADDED,
                str(ticket.id),
                str(ticket.org_id),
                str(comment.id),
            ),
        )
    if outbox:
        _audit_event(
            db,
            request=request,
            token=token,
            event_type="helpdesk_sync_enqueued",
            entity_type="helpdesk_outbox",
            entity_id=str(outbox.id),
            action="helpdesk_sync_enqueued",
            after={
                "event_type": outbox.event_type.value,
                "provider": outbox.provider.value,
                "internal_ticket_id": str(outbox.internal_ticket_id),
            },
        )
        if outbox.status == HelpdeskOutboxStatus.FAILED:
            _audit_event(
                db,
                request=request,
                token=token,
                event_type="helpdesk_sync_failed",
                entity_type="helpdesk_outbox",
                entity_id=str(outbox.id),
                action="helpdesk_sync_failed",
                after={
                    "event_type": outbox.event_type.value,
                    "provider": outbox.provider.value,
                    "internal_ticket_id": str(outbox.internal_ticket_id),
                    "error": outbox.last_error,
                },
            )
    comments = (
        db.query(SupportTicketComment)
        .filter(SupportTicketComment.ticket_id == ticket.id)
        .order_by(SupportTicketComment.created_at.asc())
        .all()
    )
    return SupportTicketDetail(
        **_serialize_support_ticket(ticket).model_dump(),
        comments=[_serialize_support_ticket_comment(item) for item in comments],
    )


@router.post("/support/tickets/{ticket_id}/close", response_model=SupportTicketDetail)
def close_support_ticket(
    ticket_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> SupportTicketDetail:
    user_id = _support_ticket_user_id(token)
    ticket = _load_support_ticket(db, ticket_id=ticket_id, token=token)
    audit_service = AuditService(db)
    request_ctx = request_context_from_request(request, token=token)
    if ticket.status != SupportTicketStatus.CLOSED:
        ticket.status = SupportTicketStatus.CLOSED
        ticket.last_changed_by = user_id
        ticket.updated_at = datetime.now(timezone.utc)
        mark_resolution(ticket, audit=audit_service, request_ctx=request_ctx)
        db.add(ticket)
        db.flush()
        audit_service.audit(
            event_type="support_ticket_closed",
            entity_type="support_ticket",
            entity_id=str(ticket.id),
            action="support_ticket_closed",
            visibility=AuditVisibility.INTERNAL,
            after={"status": ticket.status.value},
            request_ctx=request_ctx,
        )
        db.refresh(ticket)
        _notify_support_ticket(
            db,
            ticket=ticket,
            event_type="support_ticket_closed",
            title="Тикет закрыт",
            body=f"Тикет \"{ticket.subject}\" закрыт.",
            target_user_id=str(ticket.created_by_user_id),
        )
        outbox = None
        if ticket.last_changed_by != HELPDESK_INBOUND_SOURCE:
            outbox = _enqueue_helpdesk_outbox(
                db,
                ticket=ticket,
                event_type=HelpdeskOutboxEventType.TICKET_CLOSED,
                payload=build_close_payload(ticket=ticket),
                idempotency_key=build_idempotency_for_close(
                    HelpdeskOutboxEventType.TICKET_CLOSED,
                    str(ticket.id),
                    str(ticket.org_id),
                ),
            )
        if outbox:
            _audit_event(
                db,
                request=request,
                token=token,
                event_type="helpdesk_sync_enqueued",
                entity_type="helpdesk_outbox",
                entity_id=str(outbox.id),
                action="helpdesk_sync_enqueued",
                after={
                    "event_type": outbox.event_type.value,
                    "provider": outbox.provider.value,
                    "internal_ticket_id": str(outbox.internal_ticket_id),
                },
            )
            if outbox.status == HelpdeskOutboxStatus.FAILED:
                _audit_event(
                    db,
                    request=request,
                    token=token,
                    event_type="helpdesk_sync_failed",
                    entity_type="helpdesk_outbox",
                    entity_id=str(outbox.id),
                    action="helpdesk_sync_failed",
                    after={
                        "event_type": outbox.event_type.value,
                        "provider": outbox.provider.value,
                        "internal_ticket_id": str(outbox.internal_ticket_id),
                        "error": outbox.last_error,
                    },
                )
    comments = (
        db.query(SupportTicketComment)
        .filter(SupportTicketComment.ticket_id == ticket.id)
        .order_by(SupportTicketComment.created_at.asc())
        .all()
    )
    return SupportTicketDetail(
        **_serialize_support_ticket(ticket).model_dump(),
        comments=[_serialize_support_ticket_comment(item) for item in comments],
    )


@router.post("/support/tickets/{ticket_id}/attachments/init", response_model=SupportTicketAttachmentInitResponse)
def init_support_ticket_attachment(
    ticket_id: str,
    payload: SupportTicketAttachmentInit,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> SupportTicketAttachmentInitResponse:
    _load_support_ticket(db, ticket_id=ticket_id, token=token)
    content_type = payload.content_type.lower()
    _validate_support_attachment(size=payload.size, content_type=content_type)
    storage = SupportAttachmentStorage()
    attachment_id = str(uuid4())
    object_key = storage.build_object_key(
        ticket_id=ticket_id,
        attachment_id=attachment_id,
        file_name=payload.file_name,
    )
    upload_url = storage.presign_upload(
        object_key=object_key,
        content_type=content_type,
        expires=settings.S3_SIGNED_URL_TTL_SECONDS,
    )
    if not upload_url:
        raise HTTPException(status_code=500, detail="presign_failed")
    return SupportTicketAttachmentInitResponse(upload_url=upload_url, object_key=object_key)


@router.post("/support/tickets/{ticket_id}/attachments/complete", response_model=SupportTicketAttachmentOut)
def complete_support_ticket_attachment(
    ticket_id: str,
    payload: SupportTicketAttachmentComplete,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> SupportTicketAttachmentOut:
    user_id = _support_ticket_user_id(token)
    ticket = _load_support_ticket(db, ticket_id=ticket_id, token=token)
    content_type = payload.content_type.lower()
    _validate_support_attachment(size=payload.size, content_type=content_type)
    if not payload.object_key.startswith(f"support-tickets/{ticket_id}/"):
        raise HTTPException(status_code=400, detail="attachment_object_key_invalid")
    storage = SupportAttachmentStorage()
    file_name = storage.normalize_filename(payload.file_name)
    attachment = SupportTicketAttachment(
        ticket_id=str(ticket.id),
        org_id=str(ticket.org_id),
        uploaded_by_user_id=user_id,
        file_name=file_name,
        content_type=content_type,
        size=payload.size,
        object_key=payload.object_key,
    )
    db.add(attachment)
    db.flush()
    AuditService(db).audit(
        event_type="support_ticket_attachment_uploaded",
        entity_type="support_ticket_attachment",
        entity_id=str(attachment.id),
        action="support_ticket_attachment_uploaded",
        visibility=AuditVisibility.INTERNAL,
        after={
            "ticket_id": str(ticket.id),
            "file_name": attachment.file_name,
            "content_type": attachment.content_type,
            "size": attachment.size,
        },
        request_ctx=request_context_from_request(request, token=token),
    )
    db.refresh(attachment)
    return _serialize_support_ticket_attachment(attachment)


@router.get("/support/tickets/{ticket_id}/attachments", response_model=SupportTicketAttachmentListResponse)
def list_support_ticket_attachments(
    ticket_id: str,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> SupportTicketAttachmentListResponse:
    ticket = _load_support_ticket(db, ticket_id=ticket_id, token=token)
    rows = (
        db.query(SupportTicketAttachment)
        .filter(SupportTicketAttachment.ticket_id == str(ticket.id))
        .order_by(SupportTicketAttachment.created_at.asc())
        .all()
    )
    return SupportTicketAttachmentListResponse(items=[_serialize_support_ticket_attachment(item) for item in rows])


@router.get("/support/attachments/{attachment_id}/download")
def download_support_ticket_attachment(
    attachment_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> dict:
    attachment = db.query(SupportTicketAttachment).filter(SupportTicketAttachment.id == attachment_id).one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="attachment_not_found")
    _load_support_ticket(db, ticket_id=str(attachment.ticket_id), token=token)
    storage = SupportAttachmentStorage()
    url = storage.presign_download(
        object_key=attachment.object_key,
        expires=settings.S3_SIGNED_URL_TTL_SECONDS,
    )
    if not url:
        raise HTTPException(status_code=500, detail="presign_failed")
    AuditService(db).audit(
        event_type="support_ticket_attachment_downloaded",
        entity_type="support_ticket_attachment",
        entity_id=str(attachment.id),
        action="support_ticket_attachment_downloaded",
        visibility=AuditVisibility.INTERNAL,
        after={"ticket_id": str(attachment.ticket_id), "file_name": attachment.file_name},
        request_ctx=request_context_from_request(request, token=token),
        attachment_key=attachment.object_key,
    )
    return {"url": url}


@router.post("/org", response_model=ClientOrgOut)
def create_org(
    payload: ClientOrgIn,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> ClientOrgOut:
    client = _resolve_client(db, token)
    if client is None:
        client = Client(id=uuid4(), name=payload.name, inn=payload.inn, status="ONBOARDING")
        db.add(client)
        db.flush()
    else:
        client.name = payload.name
        client.inn = payload.inn
        if client.status in {"ACTIVE", "SUSPENDED"}:
            client.status = "ONBOARDING"

    onboarding = _get_or_create_onboarding(db, owner_id=_resolve_owner_id(token), client=client)
    onboarding.profile_json = {
        "org_type": payload.org_type,
        "name": payload.name,
        "inn": payload.inn,
        "kpp": payload.kpp,
        "ogrn": payload.ogrn,
        "address": payload.address,
    }
    onboarding.step = "PLAN"
    onboarding.status = "DRAFT"
    db.commit()

    return ClientOrgOut(
        id=str(client.id),
        org_type=payload.org_type,
        name=client.name,
        inn=client.inn,
        kpp=payload.kpp,
        ogrn=payload.ogrn,
        address=payload.address,
        status=client.status,
    )


@router.patch("/org", response_model=ClientOrgOut)
def update_org(
    payload: ClientOrgIn,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> ClientOrgOut:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")

    client.name = payload.name
    client.inn = payload.inn
    db.commit()

    return ClientOrgOut(
        id=str(client.id),
        org_type=payload.org_type,
        name=client.name,
        inn=client.inn,
        kpp=payload.kpp,
        ogrn=payload.ogrn,
        address=payload.address,
        status=client.status,
    )


@router.get("/contracts/current", response_model=ContractInfo)
def get_current_contract(
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> ContractInfo:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")

    onboarding = (
        db.query(ClientOnboarding)
        .filter(ClientOnboarding.client_id == str(client.id), ClientOnboarding.owner_user_id == _resolve_owner_id(token))
        .one_or_none()
    )
    if not onboarding or not onboarding.contract_id:
        raise HTTPException(status_code=404, detail="contract_not_found")

    contract = db.query(ClientOnboardingContract).filter(ClientOnboardingContract.id == onboarding.contract_id).one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="contract_not_found")

    return ContractInfo(
        contract_id=str(contract.id),
        status=contract.status,
        pdf_url=contract.pdf_url,
        version=int(contract.version or 1),
    )


@router.post("/contracts/generate", response_model=ContractInfo)
def generate_contract(
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> ContractInfo:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")

    onboarding = _get_or_create_onboarding(db, owner_id=_resolve_owner_id(token), client=client)
    if onboarding.contract_id:
        existing = (
            db.query(ClientOnboardingContract)
            .filter(ClientOnboardingContract.id == onboarding.contract_id)
            .one_or_none()
        )
        if existing:
            return ContractInfo(
                contract_id=str(existing.id),
                status=existing.status,
                pdf_url=existing.pdf_url,
                version=int(existing.version or 1),
            )

    payload = _load_contract_template()
    contract = ClientOnboardingContract(
        client_id=str(client.id),
        status="DRAFT",
        pdf_url="",
        version=1,
    )
    db.add(contract)
    db.flush()

    pdf_url = _store_contract_pdf(str(client.id), str(contract.id), payload)
    contract.pdf_url = pdf_url
    onboarding.contract_id = str(contract.id)
    onboarding.step = "CONTRACT"
    onboarding.status = "DRAFT"
    db.commit()

    return ContractInfo(
        contract_id=str(contract.id),
        status=contract.status,
        pdf_url=pdf_url,
        version=int(contract.version or 1),
    )


@router.post("/contracts/sign-simple", response_model=ContractInfo)
def sign_contract(
    payload: ContractSignRequest,
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> ContractInfo:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")

    onboarding = _get_or_create_onboarding(db, owner_id=_resolve_owner_id(token), client=client)
    if not onboarding.contract_id:
        raise HTTPException(status_code=404, detail="contract_not_found")

    contract = db.query(ClientOnboardingContract).filter(ClientOnboardingContract.id == onboarding.contract_id).one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="contract_not_found")

    payload_bytes = _load_contract_template()
    now = datetime.now(timezone.utc)
    signature_meta = {
        "otp": payload.otp,
        "ip": getattr(request.client, "host", None),
        "user_agent": request.headers.get("user-agent"),
        "timestamp": now.isoformat(),
        "doc_hash": sha256(payload_bytes).hexdigest(),
    }
    contract.status = "SIGNED_SIMPLE"
    contract.signed_at = now
    contract.signature_meta = signature_meta

    client.status = "ACTIVE"
    onboarding.step = "ACTIVATION"
    onboarding.status = client.status
    db.commit()

    _audit_event(
        db,
        request=request,
        token=token,
        event_type="contract_sign",
        entity_type="contract",
        entity_id=str(contract.id),
        before=None,
        after={"status": contract.status},
        action="sign_simple",
    )

    return ContractInfo(
        contract_id=str(contract.id),
        status=contract.status,
        pdf_url=contract.pdf_url,
        version=int(contract.version or 1),
    )


@router.get("/cards", response_model=CardListResponse)
def list_cards(
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> CardListResponse:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    card_ids = _accessible_card_ids(db, token=token, client_id=str(client.id))
    if not card_ids and not _is_card_admin(token):
        return CardListResponse(items=[])
    query = db.query(Card).filter(Card.client_id == str(client.id))
    if not _is_card_admin(token):
        query = query.filter(Card.id.in_(card_ids))
    cards = query.all()
    limits = db.query(CardLimit).filter(CardLimit.client_id == str(client.id)).all()
    limits_map: dict[str, list[CardLimitOut]] = {}
    for item in limits:
        limits_map.setdefault(item.card_id, []).append(
            CardLimitOut(limit_type=item.limit_type, amount=float(item.amount), currency=item.currency)
        )
    return CardListResponse(
        items=[
            CardOut(id=card.id, status=card.status, pan_masked=card.pan_masked, limits=limits_map.get(card.id, []))
            for card in cards
        ]
    )


@router.post("/cards", response_model=CardOut)
def create_card(
    payload: CardCreateRequest,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> CardOut:
    if not _is_card_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    card_id = f"card-{uuid4()}"
    card = Card(id=card_id, client_id=str(client.id), status="ACTIVE", pan_masked=payload.pan_masked)
    db.add(card)
    db.commit()
    return CardOut(id=card.id, status=card.status, pan_masked=card.pan_masked, limits=[])


@router.patch("/cards/{card_id}", response_model=CardOut)
def update_card(
    card_id: str,
    payload: CardUpdateRequest,
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> CardOut:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    card = db.query(Card).filter(Card.id == card_id, Card.client_id == str(client.id)).one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="card_not_found")
    if not _is_card_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    before = {"status": card.status}
    card.status = payload.status
    db.commit()
    _audit_event(
        db,
        request=request,
        token=token,
        event_type="card_block",
        entity_type="card",
        entity_id=card.id,
        before=before,
        after={"status": card.status},
        action="update_status",
    )
    limits = db.query(CardLimit).filter(CardLimit.card_id == card.id).all()
    limit_out = [CardLimitOut(limit_type=item.limit_type, amount=float(item.amount), currency=item.currency) for item in limits]
    return CardOut(id=card.id, status=card.status, pan_masked=card.pan_masked, limits=limit_out)


@router.post("/cards/bulk/block", response_model=BulkCardResponse)
def bulk_block_cards(
    payload: BulkCardRequest,
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> BulkCardResponse:
    if not _is_card_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    card_map, failed = _resolve_bulk_cards(db, token=token, client_id=str(client.id), card_ids=payload.card_ids)
    success: list[str] = []
    for card_id, card in card_map.items():
        if card.status == "BLOCKED":
            failed[card_id] = "already_blocked"
            continue
        card.status = "BLOCKED"
        success.append(card_id)
    db.commit()
    _audit_event(
        db,
        request=request,
        token=token,
        event_type="card_block_bulk",
        entity_type="card_bulk",
        entity_id=str(client.id),
        action="card_block_bulk",
        external_refs=_audit_bulk_payload(payload.card_ids),
        reason=f"Массовая блокировка карт ({len(payload.card_ids)})",
    )
    return BulkCardResponse(success=success, failed=failed)


@router.post("/cards/bulk/unblock", response_model=BulkCardResponse)
def bulk_unblock_cards(
    payload: BulkCardRequest,
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> BulkCardResponse:
    if not _is_card_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    card_map, failed = _resolve_bulk_cards(db, token=token, client_id=str(client.id), card_ids=payload.card_ids)
    success: list[str] = []
    for card_id, card in card_map.items():
        if card.status == "ACTIVE":
            failed[card_id] = "already_active"
            continue
        card.status = "ACTIVE"
        success.append(card_id)
    db.commit()
    _audit_event(
        db,
        request=request,
        token=token,
        event_type="card_unblock_bulk",
        entity_type="card_bulk",
        entity_id=str(client.id),
        action="card_unblock_bulk",
        external_refs=_audit_bulk_payload(payload.card_ids),
        reason=f"Массовая разблокировка карт ({len(payload.card_ids)})",
    )
    return BulkCardResponse(success=success, failed=failed)


@router.post("/cards/bulk/access/grant", response_model=BulkCardResponse)
def bulk_grant_card_access(
    payload: BulkCardAccessRequest,
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> BulkCardResponse:
    if not _is_card_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    _ensure_driver_user(db, client_id=str(client.id), user_id=payload.user_id)
    try:
        scope_value = CardAccessScope(payload.scope)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_scope") from exc
    card_map, failed = _resolve_bulk_cards(db, token=token, client_id=str(client.id), card_ids=payload.card_ids)
    success: list[str] = []
    for card_id, card in card_map.items():
        access = (
            db.query(CardAccess)
            .filter(CardAccess.client_id == str(client.id), CardAccess.card_id == card.id, CardAccess.user_id == payload.user_id)
            .one_or_none()
        )
        if access:
            access.scope = scope_value
            access.effective_to = None
        else:
            access = CardAccess(
                client_id=str(client.id),
                card_id=card.id,
                user_id=payload.user_id,
                scope=scope_value,
                created_by=str(token.get("user_id") or token.get("sub") or ""),
            )
            db.add(access)
        success.append(card_id)
    db.commit()
    external_refs = {"user_id": payload.user_id, "scope": payload.scope}
    external_refs.update(_audit_bulk_payload(payload.card_ids))
    _audit_event(
        db,
        request=request,
        token=token,
        event_type="card_access_grant_bulk",
        entity_type="card_bulk",
        entity_id=str(client.id),
        action="card_access_grant_bulk",
        external_refs=external_refs,
        reason=f"Массовая выдача доступа к картам ({len(payload.card_ids)})",
    )
    return BulkCardResponse(success=success, failed=failed)


@router.post("/cards/bulk/access/revoke", response_model=BulkCardResponse)
def bulk_revoke_card_access(
    payload: BulkCardAccessRequest,
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> BulkCardResponse:
    if not _is_card_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    _ensure_driver_user(db, client_id=str(client.id), user_id=payload.user_id)
    card_map, failed = _resolve_bulk_cards(db, token=token, client_id=str(client.id), card_ids=payload.card_ids)
    success: list[str] = []
    now = datetime.now(timezone.utc)
    for card_id, card in card_map.items():
        access = (
            db.query(CardAccess)
            .filter(CardAccess.client_id == str(client.id), CardAccess.card_id == card.id, CardAccess.user_id == payload.user_id)
            .one_or_none()
        )
        if not access or access.effective_to is not None:
            failed[card_id] = "not_granted"
            continue
        access.effective_to = now
        success.append(card_id)
    db.commit()
    external_refs = {"user_id": payload.user_id, "scope": payload.scope}
    external_refs.update(_audit_bulk_payload(payload.card_ids))
    _audit_event(
        db,
        request=request,
        token=token,
        event_type="card_access_revoke_bulk",
        entity_type="card_bulk",
        entity_id=str(client.id),
        action="card_access_revoke_bulk",
        external_refs=external_refs,
        reason=f"Массовый отзыв доступа к картам ({len(payload.card_ids)})",
    )
    return BulkCardResponse(success=success, failed=failed)


@router.post("/cards/bulk/limits/apply-template", response_model=BulkCardResponse)
def bulk_apply_limit_template(
    payload: BulkApplyTemplateRequest,
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> BulkCardResponse:
    if not _is_card_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    template = (
        db.query(LimitTemplate)
        .filter(LimitTemplate.client_id == str(client.id), LimitTemplate.id == payload.template_id)
        .one_or_none()
    )
    if not template:
        raise HTTPException(status_code=404, detail="template_not_found")
    if template.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="template_disabled")
    card_map, failed = _resolve_bulk_cards(db, token=token, client_id=str(client.id), card_ids=payload.card_ids)
    template_limits = template.limits if isinstance(template.limits, list) else []
    success: list[str] = []
    for card_id, card in card_map.items():
        for item in template_limits:
            limit_type = _limit_type_for_template(str(item.get("type")), str(item.get("window")))
            value = float(item.get("value"))
            existing = (
                db.query(CardLimit)
                .filter(CardLimit.card_id == card.id, CardLimit.limit_type == limit_type)
                .one_or_none()
            )
            if existing:
                existing.amount = value
                existing.currency = "RUB"
            else:
                db.add(
                    CardLimit(
                        client_id=str(client.id),
                        card_id=card.id,
                        limit_type=limit_type,
                        amount=value,
                        currency="RUB",
                    )
                )
        success.append(card_id)
    db.commit()
    external_refs = {"template_id": str(template.id)}
    external_refs.update(_audit_bulk_payload(payload.card_ids))
    _audit_event(
        db,
        request=request,
        token=token,
        event_type="limit_template_apply_bulk",
        entity_type="limit_template",
        entity_id=str(template.id),
        action="limit_template_apply_bulk",
        external_refs=external_refs,
        reason=f"Применён шаблон лимитов '{template.name}' к {len(payload.card_ids)} картам",
    )
    return BulkCardResponse(success=success, failed=failed)


@router.get("/cards/{card_id}", response_model=CardOut)
def get_card(
    card_id: str,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> CardOut:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    card = db.query(Card).filter(Card.id == card_id, Card.client_id == str(client.id)).one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="card_not_found")
    _ensure_card_access(db, token=token, card_id=card.id)
    limits = db.query(CardLimit).filter(CardLimit.card_id == card.id).all()
    limit_out = [CardLimitOut(limit_type=item.limit_type, amount=float(item.amount), currency=item.currency) for item in limits]
    return CardOut(id=card.id, status=card.status, pan_masked=card.pan_masked, limits=limit_out)


@router.patch("/cards/{card_id}/limits", response_model=CardOut)
def update_card_limits(
    card_id: str,
    payload: CardLimitRequest,
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> CardOut:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    card = db.query(Card).filter(Card.id == card_id, Card.client_id == str(client.id)).one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="card_not_found")
    if not _is_card_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    existing = (
        db.query(CardLimit)
        .filter(CardLimit.card_id == card.id, CardLimit.limit_type == payload.limit_type)
        .one_or_none()
    )
    before = None
    if existing:
        before = {"limit_type": existing.limit_type, "amount": float(existing.amount), "currency": existing.currency}
        existing.amount = payload.amount
        existing.currency = payload.currency
    else:
        db.add(
            CardLimit(
                client_id=str(client.id),
                card_id=card.id,
                limit_type=payload.limit_type,
                amount=payload.amount,
                currency=payload.currency,
            )
        )
    db.commit()
    _audit_event(
        db,
        request=request,
        token=token,
        event_type="limit_change",
        entity_type="card",
        entity_id=card.id,
        before=before,
        after={"limit_type": payload.limit_type, "amount": payload.amount, "currency": payload.currency},
        action="limit_update",
    )
    limits = db.query(CardLimit).filter(CardLimit.card_id == card.id).all()
    limit_out = [CardLimitOut(limit_type=item.limit_type, amount=float(item.amount), currency=item.currency) for item in limits]
    return CardOut(id=card.id, status=card.status, pan_masked=card.pan_masked, limits=limit_out)


@router.get("/cards/{card_id}/transactions", response_model=list[CardTransactionOut])
def list_card_transactions(
    card_id: str,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> list[CardTransactionOut]:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    _ensure_card_access(db, token=token, card_id=card_id)
    operations = (
        db.query(ClientOperation)
        .filter(ClientOperation.client_id == str(client.id), ClientOperation.card_id == card_id)
        .order_by(ClientOperation.performed_at.desc())
        .all()
    )
    return [
        CardTransactionOut(
            id=str(item.id),
            card_id=item.card_id,
            operation_type=item.operation_type,
            status=item.status,
            amount=item.amount,
            currency=item.currency,
            performed_at=item.performed_at,
        )
        for item in operations
    ]


@router.get("/cards/{card_id}/access", response_model=CardAccessListResponse)
def list_card_access(
    card_id: str,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> CardAccessListResponse:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    if not _is_card_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    items = (
        db.query(CardAccess)
        .filter(CardAccess.client_id == str(client.id), CardAccess.card_id == card_id)
        .all()
    )
    return CardAccessListResponse(
        items=[
            CardAccessOut(
                user_id=item.user_id,
                scope=str(item.scope),
                effective_from=item.effective_from,
                effective_to=item.effective_to,
            )
            for item in items
        ]
    )


@router.post("/cards/{card_id}/access", response_model=CardAccessOut)
def grant_card_access(
    card_id: str,
    payload: CardAccessGrantRequest,
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> CardAccessOut:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    if not _is_card_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    card = db.query(Card).filter(Card.id == card_id, Card.client_id == str(client.id)).one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="card_not_found")
    access = (
        db.query(CardAccess)
        .filter(CardAccess.card_id == card.id, CardAccess.user_id == payload.user_id)
        .one_or_none()
    )
    try:
        scope_value = CardAccessScope(payload.scope)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_scope") from exc
    if access:
        before = {"scope": str(access.scope)}
        access.scope = scope_value
        access.effective_to = None
    else:
        before = None
        access = CardAccess(
            client_id=str(client.id),
            card_id=card.id,
            user_id=payload.user_id,
            scope=scope_value,
            created_by=str(token.get("user_id") or token.get("sub") or ""),
        )
        db.add(access)
    db.commit()
    _audit_event(
        db,
        request=request,
        token=token,
        event_type="role_change",
        entity_type="card_access",
        entity_id=str(access.id),
        before=before,
        after={"user_id": access.user_id, "scope": str(access.scope)},
        action="grant_access",
    )
    return CardAccessOut(
        user_id=access.user_id,
        scope=str(access.scope),
        effective_from=access.effective_from,
        effective_to=access.effective_to,
    )


@router.delete("/cards/{card_id}/access/{user_id}")
def revoke_card_access(
    card_id: str,
    user_id: str,
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> dict:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    if not _is_card_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    access = (
        db.query(CardAccess)
        .filter(CardAccess.client_id == str(client.id), CardAccess.card_id == card_id, CardAccess.user_id == user_id)
        .one_or_none()
    )
    if not access:
        raise HTTPException(status_code=404, detail="access_not_found")
    before = {"scope": str(access.scope)}
    access.effective_to = datetime.now(timezone.utc)
    db.commit()
    _audit_event(
        db,
        request=request,
        token=token,
        event_type="role_change",
        entity_type="card_access",
        entity_id=str(access.id),
        before=before,
        after={"revoked": True},
        action="revoke_access",
    )
    return {"status": "revoked"}


def _template_to_out(template: LimitTemplate) -> LimitTemplateOut:
    limits = template.limits if isinstance(template.limits, list) else []
    return LimitTemplateOut(
        id=str(template.id),
        org_id=str(template.client_id),
        name=template.name,
        description=template.description,
        limits=[{"type": item.get("type"), "window": item.get("window"), "value": item.get("value")} for item in limits],
        status=template.status,
        created_at=template.created_at,
    )


@router.get("/limits/templates", response_model=LimitTemplateListResponse)
def list_limit_templates(
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> LimitTemplateListResponse:
    if not _is_card_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    items = (
        db.query(LimitTemplate)
        .filter(LimitTemplate.client_id == str(client.id))
        .order_by(LimitTemplate.created_at.desc())
        .all()
    )
    return LimitTemplateListResponse(items=[_template_to_out(item) for item in items])


@router.post("/limits/templates", response_model=LimitTemplateOut, status_code=201)
def create_limit_template(
    payload: LimitTemplateCreateRequest,
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> LimitTemplateOut:
    if not _is_card_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name_required")
    limits = _normalize_template_limits([limit.model_dump() for limit in payload.limits])
    template = LimitTemplate(
        client_id=str(client.id),
        name=name,
        description=payload.description,
        limits=limits,
        status="ACTIVE",
    )
    db.add(template)
    db.commit()
    _audit_event(
        db,
        request=request,
        token=token,
        event_type="limit_template_create",
        entity_type="limit_template",
        entity_id=str(template.id),
        action="limit_template_create",
        external_refs={"template_id": str(template.id), "name": name},
        reason=f"Создан шаблон лимитов '{name}'",
    )
    return _template_to_out(template)


@router.patch("/limits/templates/{template_id}", response_model=LimitTemplateOut)
def update_limit_template(
    template_id: str,
    payload: LimitTemplateUpdateRequest,
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> LimitTemplateOut:
    if not _is_card_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    template = (
        db.query(LimitTemplate)
        .filter(LimitTemplate.client_id == str(client.id), LimitTemplate.id == template_id)
        .one_or_none()
    )
    if not template:
        raise HTTPException(status_code=404, detail="template_not_found")
    before = {"name": template.name, "description": template.description, "status": template.status}
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="name_required")
        template.name = name
    if payload.description is not None:
        template.description = payload.description
    if payload.limits is not None:
        template.limits = _normalize_template_limits([limit.model_dump() for limit in payload.limits])
    if payload.status is not None:
        status = payload.status.upper().strip()
        if status not in {"ACTIVE", "DISABLED"}:
            raise HTTPException(status_code=422, detail="invalid_status")
        template.status = status
    db.commit()
    _audit_event(
        db,
        request=request,
        token=token,
        event_type="limit_template_update",
        entity_type="limit_template",
        entity_id=str(template.id),
        action="limit_template_update",
        before=before,
        after={"name": template.name, "description": template.description, "status": template.status},
        external_refs={"template_id": str(template.id), "name": template.name},
        reason=f"Обновлён шаблон лимитов '{template.name}'",
    )
    return _template_to_out(template)


@router.get("/reports/cards")
def export_cards_report(
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
    status: str | None = None,
    driver_id: str | None = Query(None, alias="driver_id"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    limit: int = Query(MAX_EXPORT_ROWS, ge=1, le=MAX_EXPORT_ROWS),
) -> Response:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    _ensure_report_access(token, {"CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_FLEET_MANAGER"})
    user_id = _support_ticket_user_id(token)
    email_to = _notification_user_email(token)
    request_id = request.headers.get("x-request-id")

    try:
        start, end = _date_range_bounds(date_from, date_to)
        query = db.query(FuelCard).filter(FuelCard.client_id == str(client.id))
        if status:
            query = query.filter(FuelCard.status == status.upper().strip())
        if driver_id:
            query = query.filter(FuelCard.driver_id == driver_id)
        if start:
            query = query.filter(FuelCard.created_at >= start)
        if end:
            query = query.filter(FuelCard.created_at <= end)

        cards = query.order_by(FuelCard.created_at.desc()).limit(limit + 1).all()
        if len(cards) > limit:
            raise HTTPException(status_code=413, detail="too_large")

        driver_ids = {str(card.driver_id) for card in cards if card.driver_id}
        drivers = db.query(FleetDriver).filter(FleetDriver.id.in_(driver_ids)).all() if driver_ids else []
        driver_map = {str(driver.id): driver for driver in drivers}

        card_ids = [str(card.id) for card in cards]
        limits = []
        if card_ids:
            limits = (
                db.query(FuelLimit)
                .filter(FuelLimit.client_id == str(client.id))
                .filter(FuelLimit.scope_type == FuelLimitScopeType.CARD)
                .filter(FuelLimit.scope_id.in_(card_ids))
                .filter(FuelLimit.active.is_(True))
                .order_by(FuelLimit.created_at.desc())
                .all()
            )
        limit_map: dict[str, list[FuelLimit]] = {}
        for item in limits:
            if item.scope_id:
                limit_map.setdefault(str(item.scope_id), []).append(item)

        rows = []
        for card in cards:
            driver = driver_map.get(str(card.driver_id)) if card.driver_id else None
            assigned_driver = driver.full_name if driver else None
            rows.append(
                [
                    str(card.id),
                    card.masked_pan,
                    _extract_token_tail(card.masked_pan or card.token_ref),
                    card.status.value if hasattr(card.status, "value") else str(card.status),
                    assigned_driver,
                    _limits_summary(limit_map.get(str(card.id), [])),
                    card.created_at,
                ]
            )

        _audit_export(
            db,
            request=request,
            token=token,
            client_id=str(client.id),
            action="export_cards",
            filters={
                "status": status,
                "driver_id": driver_id,
                "from": date_from,
                "to": date_to,
                "limit": limit,
            },
            row_count=len(rows),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _notify_export_failed(
            db,
            org_id=str(client.id),
            user_id=user_id,
            title="Ошибка экспорта",
            body="Не удалось сформировать отчёт по картам.",
            email_to=email_to,
            email_idempotency_key=_email_idempotency_key(
                event_type="export_failed",
                org_id=str(client.id),
                user_id=user_id,
                request_id=request_id,
            ),
        )
        raise

    _notify_export_ready(
        db,
        org_id=str(client.id),
        user_id=user_id,
        title="Отчёт готов",
        body="Выгрузка по картам готова к скачиванию",
        email_to=email_to,
        export_format="CSV",
        email_idempotency_key=_email_idempotency_key(
            event_type="export_ready",
            org_id=str(client.id),
            user_id=user_id,
            request_id=request_id,
        ),
    )
    return _csv_response(
        "cards_export.csv",
        ["card_id", "masked_pan", "token_tail", "status", "assigned_driver", "limit_summary", "created_at"],
        rows,
    )


@router.get("/reports/users")
def export_users_report(
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
    role: str | None = None,
    status: str | None = None,
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    limit: int = Query(MAX_EXPORT_ROWS, ge=1, le=MAX_EXPORT_ROWS),
) -> Response:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    _ensure_report_access(token, {"CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT"})
    user_id = _support_ticket_user_id(token)
    email_to = _notification_user_email(token)
    request_id = request.headers.get("x-request-id")

    try:
        start, end = _date_range_bounds(date_from, date_to)
        query = (
            db.query(ClientEmployee)
            .outerjoin(
                ClientUserRole,
                and_(
                    ClientUserRole.client_id == str(client.id),
                    ClientUserRole.user_id == ClientEmployee.id,
                ),
            )
            .filter(ClientEmployee.client_id == str(client.id))
        )
        if status:
            try:
                parsed_status = EmployeeStatus(status.upper().strip())
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="invalid_status") from exc
            query = query.filter(ClientEmployee.status == parsed_status)
        if role:
            role_value = role.upper().strip()
            if role_value == "CLIENT_USER":
                query = query.filter(or_(ClientUserRole.roles.ilike(f"%{role_value}%"), ClientUserRole.roles.is_(None)))
            else:
                query = query.filter(ClientUserRole.roles.ilike(f"%{role_value}%"))
        if start:
            query = query.filter(ClientEmployee.created_at >= start)
        if end:
            query = query.filter(ClientEmployee.created_at <= end)

        users = query.order_by(ClientEmployee.created_at.desc()).limit(limit + 1).all()
        if len(users) > limit:
            raise HTTPException(status_code=413, detail="too_large")

        user_ids = [str(user_item.id) for user_item in users]
        role_rows = (
            db.query(ClientUserRole)
            .filter(ClientUserRole.client_id == str(client.id), ClientUserRole.user_id.in_(user_ids))
            .all()
        )
        role_map = {row.user_id: row.roles for row in role_rows}

        rows = [
            [
                str(user_item.id),
                user_item.email,
                role_map.get(str(user_item.id), "CLIENT_USER"),
                user_item.status.value if user_item.status else None,
                user_item.created_at,
                None,
            ]
            for user_item in users
        ]

        _audit_export(
            db,
            request=request,
            token=token,
            client_id=str(client.id),
            action="export_users",
            filters={
                "role": role,
                "status": status,
                "from": date_from,
                "to": date_to,
                "limit": limit,
            },
            row_count=len(rows),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _notify_export_failed(
            db,
            org_id=str(client.id),
            user_id=user_id,
            title="Ошибка экспорта",
            body="Не удалось сформировать отчёт по пользователям.",
            email_to=email_to,
            email_idempotency_key=_email_idempotency_key(
                event_type="export_failed",
                org_id=str(client.id),
                user_id=user_id,
                request_id=request_id,
            ),
        )
        raise

    _notify_export_ready(
        db,
        org_id=str(client.id),
        user_id=user_id,
        title="Отчёт готов",
        body="Выгрузка по пользователям готова к скачиванию",
        email_to=email_to,
        export_format="CSV",
        email_idempotency_key=_email_idempotency_key(
            event_type="export_ready",
            org_id=str(client.id),
            user_id=user_id,
            request_id=request_id,
        ),
    )
    return _csv_response(
        "users_export.csv",
        ["user_id", "email", "roles", "status", "created_at", "last_login_at"],
        rows,
    )


@router.get("/reports/transactions")
def export_transactions_report(
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    status: str | None = None,
    card_id: str | None = None,
    card_ids: list[str] | None = Query(None, alias="cards[]"),
    min_amount: int | None = Query(None, alias="min_amount"),
    max_amount: int | None = Query(None, alias="max_amount"),
    limit: int = Query(..., ge=1, le=MAX_EXPORT_ROWS),
) -> Response:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="missing_client_context")
    _ensure_report_access(token, {"CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT", "CLIENT_FLEET_MANAGER"})
    if not date_from or not date_to:
        raise HTTPException(status_code=422, detail="date_range_required")
    user_id = _support_ticket_user_id(token)
    email_to = _notification_user_email(token)
    request_id = request.headers.get("x-request-id")

    try:
        start, end = _date_range_bounds(date_from, date_to)
        query = db.query(Operation).filter(Operation.client_id == str(client_id))
        if card_id:
            query = query.filter(Operation.card_id == card_id)
        if card_ids:
            query = query.filter(Operation.card_id.in_(card_ids))
        if status:
            query = query.filter(Operation.status == status)
        if start:
            query = query.filter(Operation.created_at >= start)
        if end:
            query = query.filter(Operation.created_at <= end)
        if min_amount is not None:
            query = query.filter(Operation.amount >= min_amount)
        if max_amount is not None:
            query = query.filter(Operation.amount <= max_amount)

        operations = query.order_by(Operation.created_at.desc()).limit(limit + 1).all()
        if len(operations) > limit:
            raise HTTPException(status_code=413, detail="too_large")

        card_ids_map = {op.card_id for op in operations}
        cards = db.query(Card).filter(Card.id.in_(card_ids_map)).all() if card_ids_map else []
        card_map = {card.id: card for card in cards}

        rows = [
            [
                str(op.operation_id),
                op.card_id,
                card_map.get(op.card_id).pan_masked if op.card_id in card_map else None,
                op.created_at,
                op.amount,
                op.currency,
                op.product_type.value if hasattr(op.product_type, "value") else op.product_type,
                op.merchant_id,
                op.terminal_id,
                op.status.value if hasattr(op.status, "value") else op.status,
            ]
            for op in operations
        ]

        _audit_export(
            db,
            request=request,
            token=token,
            client_id=str(client_id),
            action="export_transactions",
            filters={
                "card_id": card_id,
                "cards": card_ids,
                "status": status,
                "from": date_from,
                "to": date_to,
                "min_amount": min_amount,
                "max_amount": max_amount,
                "limit": limit,
            },
            row_count=len(rows),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _notify_export_failed(
            db,
            org_id=str(client_id),
            user_id=user_id,
            title="Ошибка экспорта",
            body="Не удалось сформировать отчёт по транзакциям.",
            email_to=email_to,
            email_idempotency_key=_email_idempotency_key(
                event_type="export_failed",
                org_id=str(client_id),
                user_id=user_id,
                request_id=request_id,
            ),
        )
        raise

    _notify_export_ready(
        db,
        org_id=str(client_id),
        user_id=user_id,
        title="Отчёт готов",
        body="Выгрузка по транзакциям готова к скачиванию",
        email_to=email_to,
        export_format="CSV",
        email_idempotency_key=_email_idempotency_key(
            event_type="export_ready",
            org_id=str(client_id),
            user_id=user_id,
            request_id=request_id,
        ),
    )
    return _csv_response(
        "transactions_export.csv",
        [
            "transaction_id",
            "card_id",
            "masked_pan",
            "date",
            "amount",
            "currency",
            "product_type",
            "station",
            "network",
            "status",
        ],
        rows,
    )


@router.get("/reports/documents")
def export_documents_report(
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    document_type: str | None = Query(None, alias="type"),
    status: str | None = None,
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    limit: int = Query(MAX_EXPORT_ROWS, ge=1, le=MAX_EXPORT_ROWS),
) -> Response:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="missing_client_context")
    _ensure_report_access(token, {"CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT"})
    assert_module_enabled(db, client_id=str(client_id), module_code="DOCS")
    user_id = _support_ticket_user_id(token)
    email_to = _notification_user_email(token)
    request_id = request.headers.get("x-request-id")

    try:
        query = db.query(Document).filter(Document.client_id == str(client_id))
        if date_from:
            query = query.filter(Document.period_from >= date_from)
        if date_to:
            query = query.filter(Document.period_to <= date_to)
        if document_type:
            resolved_type = _DOC_TYPE_ALIASES.get(document_type.upper().strip())
            if resolved_type is None:
                try:
                    resolved_type = DocumentType(document_type)
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail="invalid_document_type") from exc
            query = query.filter(Document.document_type == resolved_type)
        if status:
            try:
                parsed_status = DocumentStatus(status)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="invalid_document_status") from exc
            query = query.filter(Document.status == parsed_status)

        documents = query.order_by(Document.period_to.desc()).limit(limit + 1).all()
        if len(documents) > limit:
            raise HTTPException(status_code=413, detail="too_large")

        document_ids = [str(item.id) for item in documents]
        files = (
            db.query(DocumentFile)
            .filter(DocumentFile.document_id.in_(document_ids))
            .filter(DocumentFile.file_type == DocumentFileType.PDF)
            .all()
            if document_ids
            else []
        )
        file_map = {str(item.document_id): item for item in files}

        rows = []
        for item in documents:
            meta = item.meta if isinstance(item.meta, dict) else {}
            amount = None
            currency = None
            for key in ("amount_total", "total_amount", "amount"):
                if key in meta:
                    amount = meta.get(key)
                    break
            if isinstance(meta, dict):
                currency = meta.get("currency")
            file_item = file_map.get(str(item.id))
            file_name = file_item.object_key.split("/")[-1] if file_item else None
            rows.append(
                [
                    str(item.id),
                    item.document_type.value,
                    item.number,
                    item.period_to,
                    item.status.value,
                    amount,
                    currency,
                    file_name,
                ]
            )

        _audit_export(
            db,
            request=request,
            token=token,
            client_id=str(client_id),
            action="export_documents",
            filters={
                "type": document_type,
                "status": status,
                "from": date_from,
                "to": date_to,
                "limit": limit,
            },
            row_count=len(rows),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _notify_export_failed(
            db,
            org_id=str(client_id),
            user_id=user_id,
            title="Ошибка экспорта",
            body="Не удалось сформировать отчёт по документам.",
            email_to=email_to,
            email_idempotency_key=_email_idempotency_key(
                event_type="export_failed",
                org_id=str(client_id),
                user_id=user_id,
                request_id=request_id,
            ),
        )
        raise

    _notify_export_ready(
        db,
        org_id=str(client_id),
        user_id=user_id,
        title="Отчёт готов",
        body="Выгрузка по документам готова к скачиванию",
        email_to=email_to,
        export_format="CSV",
        email_idempotency_key=_email_idempotency_key(
            event_type="export_ready",
            org_id=str(client_id),
            user_id=user_id,
            request_id=request_id,
        ),
    )
    return _csv_response(
        "documents_export.csv",
        ["document_id", "type", "number", "date", "status", "amount", "currency", "file_name"],
        rows,
    )


@router.get("/analytics/summary", response_model=ClientAnalyticsSummaryResponse)
def get_client_analytics_summary(
    request: Request,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    scope: str | None = Query(default=None),
    timezone_name: str | None = Query(default=None, alias="timezone"),
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientAnalyticsSummaryResponse:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    assert_module_enabled(db, client_id=str(client.id), module_code="ANALYTICS")
    _ensure_analytics_access(token)
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="invalid_period")

    tz_name = timezone_name or resolve_user_timezone(db, token=token)
    if timezone_name:
        try:
            ZoneInfo(timezone_name)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="invalid_timezone") from exc
    tzinfo = ZoneInfo(tz_name)

    start_dt = datetime.combine(date_from, time.min, tzinfo=tzinfo).astimezone(timezone.utc)
    end_dt = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tzinfo).astimezone(timezone.utc)

    filters = [
        FuelTransaction.client_id == str(client.id),
        FuelTransaction.occurred_at >= start_dt,
        FuelTransaction.occurred_at < end_dt,
        FuelTransaction.status == FuelTransactionStatus.SETTLED,
    ]
    scope_value = (scope or "all").strip()
    if scope_value and scope_value != "all":
        if scope_value.startswith("cards:"):
            cards_payload = scope_value.split(":", 1)[1]
            card_ids = [card_id.strip() for card_id in cards_payload.split(",") if card_id.strip()]
            if not card_ids:
                raise HTTPException(status_code=400, detail="invalid_scope")
            filters.append(FuelTransaction.card_id.in_(card_ids))
        elif scope_value.startswith("driver:"):
            driver_id = scope_value.split(":", 1)[1].strip()
            if not driver_id:
                raise HTTPException(status_code=400, detail="invalid_scope")
            filters.append(FuelTransaction.driver_id == driver_id)
        else:
            raise HTTPException(status_code=400, detail="invalid_scope")

    summary_row = (
        db.query(
            func.count().label("transactions_count"),
            func.coalesce(func.sum(FuelTransaction.amount_total_minor), 0).label("total_spend_minor"),
            func.coalesce(func.sum(FuelTransaction.volume_liters), 0).label("total_liters"),
            func.count(func.distinct(FuelTransaction.driver_id)).label("unique_drivers"),
        )
        .filter(*filters)
        .one()
    )

    active_cards = (
        db.query(func.count())
        .filter(FuelCard.client_id == str(client.id), FuelCard.status == FuelCardStatus.ACTIVE)
        .scalar()
        or 0
    )
    blocked_cards = (
        db.query(func.count())
        .filter(FuelCard.client_id == str(client.id), FuelCard.status == FuelCardStatus.BLOCKED)
        .scalar()
        or 0
    )

    org_id = _support_ticket_org_id(token)
    ticket_filters = [
        SupportTicket.org_id == org_id,
        SupportTicket.created_at >= start_dt,
        SupportTicket.created_at < end_dt,
    ]
    open_tickets = (
        db.query(func.count())
        .filter(
            *ticket_filters,
            SupportTicket.status.in_({SupportTicketStatus.OPEN, SupportTicketStatus.IN_PROGRESS}),
        )
        .scalar()
        or 0
    )
    sla_first_breaches = (
        db.query(func.count())
        .filter(*ticket_filters, SupportTicket.sla_first_response_status == SupportTicketSlaStatus.BREACHED)
        .scalar()
        or 0
    )
    sla_resolution_breaches = (
        db.query(func.count())
        .filter(*ticket_filters, SupportTicket.sla_resolution_status == SupportTicketSlaStatus.BREACHED)
        .scalar()
        or 0
    )

    avg_first_response = (
        db.query(
            func.avg(
                func.extract(
                    "epoch",
                    SupportTicket.first_response_at - SupportTicket.created_at,
                )
                / 60
            )
        )
        .filter(*ticket_filters, SupportTicket.first_response_at.isnot(None))
        .scalar()
    )
    avg_resolve = (
        db.query(
            func.avg(
                func.extract(
                    "epoch",
                    SupportTicket.resolved_at - SupportTicket.created_at,
                )
                / 60
            )
        )
        .filter(*ticket_filters, SupportTicket.resolved_at.isnot(None))
        .scalar()
    )

    day_bucket = cast(
        func.date_trunc(
            "day",
            FuelTransaction.occurred_at.op("AT TIME ZONE")(tz_name),
        ),
        Date,
    ).label("day")
    timeseries_rows = (
        db.query(
            day_bucket,
            func.coalesce(func.sum(FuelTransaction.amount_total_minor), 0).label("spend_minor"),
            func.coalesce(func.sum(FuelTransaction.volume_liters), 0).label("liters"),
            func.count().label("count"),
        )
        .filter(*filters)
        .group_by(day_bucket)
        .order_by(day_bucket.asc())
        .all()
    )
    timeseries_map = {row.day: row for row in timeseries_rows if row.day}
    timeseries: list[ClientAnalyticsTimeseriesPoint] = []
    cursor = date_from
    while cursor <= date_to:
        row = timeseries_map.get(cursor)
        spend_minor = int(row.spend_minor) if row else 0
        liters_value = float(row.liters) if row and row.liters is not None else None
        count_value = int(row.count) if row else 0
        timeseries.append(
            ClientAnalyticsTimeseriesPoint(
                date=cursor,
                spend=spend_minor / 100,
                liters=liters_value,
                count=count_value,
            )
        )
        cursor += timedelta(days=1)

    top_cards_rows = (
        db.query(
            FuelTransaction.card_id,
            FuelCard.masked_pan,
            FuelCard.card_alias,
            func.coalesce(func.sum(FuelTransaction.amount_total_minor), 0).label("spend_minor"),
            func.coalesce(func.sum(FuelTransaction.volume_liters), 0).label("liters"),
            func.count().label("count"),
        )
        .join(FuelCard, FuelCard.id == FuelTransaction.card_id)
        .filter(*filters, FuelCard.client_id == str(client.id))
        .group_by(FuelTransaction.card_id, FuelCard.masked_pan, FuelCard.card_alias)
        .order_by(desc("spend_minor"))
        .limit(5)
        .all()
    )
    top_cards = [
        ClientAnalyticsTopCard(
            card_id=str(row.card_id),
            label=row.masked_pan or row.card_alias or str(row.card_id),
            spend=int(row.spend_minor) / 100,
            count=int(row.count),
            liters=float(row.liters) if row.liters is not None else None,
        )
        for row in top_cards_rows
    ]

    top_drivers_rows = (
        db.query(
            FuelTransaction.driver_id,
            FleetDriver.full_name,
            func.coalesce(func.sum(FuelTransaction.amount_total_minor), 0).label("spend_minor"),
            func.count().label("count"),
        )
        .join(FleetDriver, FleetDriver.id == FuelTransaction.driver_id)
        .filter(*filters, FuelTransaction.driver_id.isnot(None))
        .group_by(FuelTransaction.driver_id, FleetDriver.full_name)
        .order_by(desc("spend_minor"))
        .limit(5)
        .all()
    )
    top_drivers = [
        ClientAnalyticsTopDriver(
            user_id=str(row.driver_id),
            label=row.full_name or str(row.driver_id),
            spend=int(row.spend_minor) / 100,
            count=int(row.count),
        )
        for row in top_drivers_rows
    ]

    top_stations_rows = (
        db.query(
            FuelTransaction.station_id,
            FuelStation.name,
            func.coalesce(func.sum(FuelTransaction.amount_total_minor), 0).label("spend_minor"),
            func.coalesce(func.sum(FuelTransaction.volume_liters), 0).label("liters"),
            func.count().label("count"),
        )
        .join(FuelStation, FuelStation.id == FuelTransaction.station_id)
        .filter(*filters)
        .group_by(FuelTransaction.station_id, FuelStation.name)
        .order_by(desc("spend_minor"))
        .limit(5)
        .all()
    )
    top_stations = [
        ClientAnalyticsTopStation(
            station_id=str(row.station_id),
            label=row.name or str(row.station_id),
            spend=int(row.spend_minor) / 100,
            count=int(row.count),
            liters=float(row.liters) if row.liters is not None else None,
        )
        for row in top_stations_rows
    ]

    return ClientAnalyticsSummaryResponse(
        period=ClientAnalyticsPeriod(from_=date_from, to=date_to),
        summary=ClientAnalyticsSummary(
            transactions_count=int(summary_row.transactions_count or 0),
            total_spend=int(summary_row.total_spend_minor or 0) / 100,
            total_liters=float(summary_row.total_liters) if summary_row.total_liters is not None else None,
            active_cards=int(active_cards),
            blocked_cards=int(blocked_cards),
            unique_drivers=int(summary_row.unique_drivers or 0),
            open_tickets=int(open_tickets),
            sla_breaches_first=int(sla_first_breaches),
            sla_breaches_resolution=int(sla_resolution_breaches),
        ),
        timeseries=timeseries,
        tops=ClientAnalyticsTopLists(cards=top_cards, drivers=top_drivers, stations=top_stations),
        support=ClientAnalyticsSupport(
            open=int(open_tickets),
            avg_first_response_minutes=float(avg_first_response) if avg_first_response is not None else None,
            avg_resolve_minutes=float(avg_resolve) if avg_resolve is not None else None,
        ),
    )


@router.get("/analytics/drill/day", response_model=ClientAnalyticsDrillResponse)
def get_client_analytics_day_drill(
    date_value: date = Query(..., alias="date"),
    timezone_name: str | None = Query(default=None, alias="timezone"),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None),
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientAnalyticsDrillResponse:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    assert_module_enabled(db, client_id=str(client.id), module_code="ANALYTICS")
    _ensure_analytics_access(token)

    tz_name = timezone_name or resolve_user_timezone(db, token=token)
    if timezone_name:
        try:
            ZoneInfo(timezone_name)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="invalid_timezone") from exc
    tzinfo = ZoneInfo(tz_name)

    start_dt = datetime.combine(date_value, time.min, tzinfo=tzinfo).astimezone(timezone.utc)
    end_dt = datetime.combine(date_value + timedelta(days=1), time.min, tzinfo=tzinfo).astimezone(timezone.utc)

    query = _build_drill_transactions_query(
        db,
        client_id=str(client.id),
        start_dt=start_dt,
        end_dt=end_dt,
    )

    cursor_dt, cursor_id = _parse_datetime_cursor(cursor)
    if cursor_dt and cursor_id:
        query = query.filter(
            or_(
                FuelTransaction.occurred_at < cursor_dt,
                and_(FuelTransaction.occurred_at == cursor_dt, FuelTransaction.id < cursor_id),
            )
        )

    rows = (
        query.order_by(FuelTransaction.occurred_at.desc(), FuelTransaction.id.desc())
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    items = [
        ClientAnalyticsDrillTransaction(
            tx_id=str(tx.id),
            occurred_at=tx.occurred_at,
            card_id=str(tx.card_id),
            card_label=card.masked_pan or card.card_alias or str(tx.card_id),
            driver_user_id=str(driver.id) if driver else None,
            driver_label=driver.full_name if driver else None,
            amount=int(tx.amount_total_minor or 0) / 100,
            currency=tx.currency,
            liters=float(tx.volume_liters) if tx.volume_liters is not None else None,
            station=station.name or str(tx.station_id),
            status=tx.status.value if hasattr(tx.status, "value") else str(tx.status),
        )
        for tx, card, driver, station in rows
    ]
    next_cursor = _drill_transaction_cursor(rows[-1][0]) if has_more and rows else None

    return ClientAnalyticsDrillResponse(items=items, next_cursor=next_cursor)


@router.get("/analytics/drill/card/{card_id}", response_model=ClientAnalyticsDrillResponse)
def get_client_analytics_card_drill(
    card_id: str,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None),
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientAnalyticsDrillResponse:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    assert_module_enabled(db, client_id=str(client.id), module_code="ANALYTICS")
    _ensure_analytics_access(token)
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="invalid_period")

    card = (
        db.query(FuelCard)
        .filter(FuelCard.id == card_id, FuelCard.client_id == str(client.id))
        .one_or_none()
    )
    if card is None:
        raise HTTPException(status_code=404, detail="card_not_found")

    tzinfo = ZoneInfo(resolve_user_timezone(db, token=token))
    start_dt = datetime.combine(date_from, time.min, tzinfo=tzinfo).astimezone(timezone.utc)
    end_dt = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tzinfo).astimezone(timezone.utc)

    query = _build_drill_transactions_query(
        db,
        client_id=str(client.id),
        start_dt=start_dt,
        end_dt=end_dt,
    ).filter(FuelTransaction.card_id == card_id)

    cursor_dt, cursor_id = _parse_datetime_cursor(cursor)
    if cursor_dt and cursor_id:
        query = query.filter(
            or_(
                FuelTransaction.occurred_at < cursor_dt,
                and_(FuelTransaction.occurred_at == cursor_dt, FuelTransaction.id < cursor_id),
            )
        )

    rows = (
        query.order_by(FuelTransaction.occurred_at.desc(), FuelTransaction.id.desc())
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    items = [
        ClientAnalyticsDrillTransaction(
            tx_id=str(tx.id),
            occurred_at=tx.occurred_at,
            card_id=str(tx.card_id),
            card_label=card_item.masked_pan or card_item.card_alias or str(tx.card_id),
            driver_user_id=str(driver.id) if driver else None,
            driver_label=driver.full_name if driver else None,
            amount=int(tx.amount_total_minor or 0) / 100,
            currency=tx.currency,
            liters=float(tx.volume_liters) if tx.volume_liters is not None else None,
            station=station.name or str(tx.station_id),
            status=tx.status.value if hasattr(tx.status, "value") else str(tx.status),
        )
        for tx, card_item, driver, station in rows
    ]
    next_cursor = _drill_transaction_cursor(rows[-1][0]) if has_more and rows else None

    return ClientAnalyticsDrillResponse(items=items, next_cursor=next_cursor)


@router.get("/analytics/drill/driver/{user_id}", response_model=ClientAnalyticsDrillResponse)
def get_client_analytics_driver_drill(
    user_id: str,
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None),
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientAnalyticsDrillResponse:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    assert_module_enabled(db, client_id=str(client.id), module_code="ANALYTICS")
    _ensure_analytics_access(token)
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="invalid_period")

    driver = (
        db.query(FleetDriver)
        .filter(FleetDriver.id == user_id, FleetDriver.client_id == str(client.id))
        .one_or_none()
    )
    if driver is None:
        raise HTTPException(status_code=404, detail="driver_not_found")

    tzinfo = ZoneInfo(resolve_user_timezone(db, token=token))
    start_dt = datetime.combine(date_from, time.min, tzinfo=tzinfo).astimezone(timezone.utc)
    end_dt = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tzinfo).astimezone(timezone.utc)

    query = _build_drill_transactions_query(
        db,
        client_id=str(client.id),
        start_dt=start_dt,
        end_dt=end_dt,
    ).filter(FuelTransaction.driver_id == user_id)

    cursor_dt, cursor_id = _parse_datetime_cursor(cursor)
    if cursor_dt and cursor_id:
        query = query.filter(
            or_(
                FuelTransaction.occurred_at < cursor_dt,
                and_(FuelTransaction.occurred_at == cursor_dt, FuelTransaction.id < cursor_id),
            )
        )

    rows = (
        query.order_by(FuelTransaction.occurred_at.desc(), FuelTransaction.id.desc())
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    items = [
        ClientAnalyticsDrillTransaction(
            tx_id=str(tx.id),
            occurred_at=tx.occurred_at,
            card_id=str(tx.card_id),
            card_label=card_item.masked_pan or card_item.card_alias or str(tx.card_id),
            driver_user_id=str(driver_item.id) if driver_item else None,
            driver_label=driver_item.full_name if driver_item else None,
            amount=int(tx.amount_total_minor or 0) / 100,
            currency=tx.currency,
            liters=float(tx.volume_liters) if tx.volume_liters is not None else None,
            station=station.name or str(tx.station_id),
            status=tx.status.value if hasattr(tx.status, "value") else str(tx.status),
        )
        for tx, card_item, driver_item, station in rows
    ]
    next_cursor = _drill_transaction_cursor(rows[-1][0]) if has_more and rows else None

    return ClientAnalyticsDrillResponse(items=items, next_cursor=next_cursor)


@router.get("/analytics/drill/support", response_model=ClientAnalyticsSupportDrillResponse)
def get_client_analytics_support_drill(
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    filter_type: str | None = Query(default=None, alias="t"),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None),
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientAnalyticsSupportDrillResponse:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    assert_module_enabled(db, client_id=str(client.id), module_code="ANALYTICS")
    _ensure_analytics_access(token)
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="invalid_period")

    org_id = _support_ticket_org_id(token)
    tzinfo = ZoneInfo(resolve_user_timezone(db, token=token))
    start_dt = datetime.combine(date_from, time.min, tzinfo=tzinfo).astimezone(timezone.utc)
    end_dt = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=tzinfo).astimezone(timezone.utc)

    query = db.query(SupportTicket).filter(
        SupportTicket.org_id == org_id,
        SupportTicket.created_at >= start_dt,
        SupportTicket.created_at < end_dt,
    )

    filter_value = (filter_type or "open").strip().lower()
    if filter_value in {"open"}:
        query = query.filter(SupportTicket.status.in_({SupportTicketStatus.OPEN, SupportTicketStatus.IN_PROGRESS}))
    elif filter_value == "closed":
        query = query.filter(SupportTicket.status == SupportTicketStatus.CLOSED)
    elif filter_value in {"sla_breached", "sla_breached_any"}:
        query = query.filter(
            or_(
                SupportTicket.sla_first_response_status == SupportTicketSlaStatus.BREACHED,
                SupportTicket.sla_resolution_status == SupportTicketSlaStatus.BREACHED,
            )
        )
    elif filter_value == "sla_breached_first":
        query = query.filter(SupportTicket.sla_first_response_status == SupportTicketSlaStatus.BREACHED)
    elif filter_value == "sla_breached_resolution":
        query = query.filter(SupportTicket.sla_resolution_status == SupportTicketSlaStatus.BREACHED)
    else:
        raise HTTPException(status_code=400, detail="invalid_filter")

    cursor_dt, cursor_id = _parse_datetime_cursor(cursor)
    if cursor_dt and cursor_id:
        query = query.filter(
            or_(
                SupportTicket.created_at < cursor_dt,
                and_(SupportTicket.created_at == cursor_dt, SupportTicket.id < cursor_id),
            )
        )

    rows = (
        query.order_by(SupportTicket.created_at.desc(), SupportTicket.id.desc())
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    items = [
        ClientAnalyticsSupportDrillItem(
            ticket_id=str(ticket.id),
            subject=ticket.subject,
            status=ticket.status.value if hasattr(ticket.status, "value") else str(ticket.status),
            priority=ticket.priority.value if hasattr(ticket.priority, "value") else str(ticket.priority),
            created_at=ticket.created_at,
            first_response_status=(
                ticket.sla_first_response_status.value
                if hasattr(ticket.sla_first_response_status, "value")
                else str(ticket.sla_first_response_status)
            ),
            resolution_status=(
                ticket.sla_resolution_status.value
                if hasattr(ticket.sla_resolution_status, "value")
                else str(ticket.sla_resolution_status)
            ),
        )
        for ticket in rows
    ]
    next_cursor = _support_ticket_cursor(rows[-1]) if has_more and rows else None

    return ClientAnalyticsSupportDrillResponse(items=items, next_cursor=next_cursor)


@router.get("/users", response_model=ClientUsersResponse)
def list_users(
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> ClientUsersResponse:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    if not _is_user_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    users = (
        db.query(ClientEmployee)
        .filter(ClientEmployee.client_id == str(client.id))
        .order_by(ClientEmployee.created_at.desc())
        .all()
    )
    role_rows = db.query(ClientUserRole).filter(ClientUserRole.client_id == str(client.id)).all()
    role_map = {row.user_id: row.roles.split(",")[0] for row in role_rows}
    return ClientUsersResponse(
        items=[
            ClientUserSummary(
                id=str(user_item.id),
                email=user_item.email,
                role=role_map.get(str(user_item.id), "CLIENT_USER"),
                status=user_item.status.value if user_item.status else None,
                last_login=None,
            )
            for user_item in users
        ]
    )


@router.post("/users/invite", response_model=ClientUserSummary, status_code=201)
def invite_user(
    payload: ClientUserInviteRequest,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> ClientUserSummary:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    if not _is_user_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(status_code=422, detail="email_required")
    employee = (
        db.query(ClientEmployee)
        .filter(ClientEmployee.client_id == str(client.id), ClientEmployee.email == email)
        .one_or_none()
    )
    if employee:
        employee.status = EmployeeStatus.INVITED
    else:
        employee = ClientEmployee(client_id=str(client.id), email=email, status=EmployeeStatus.INVITED)
        db.add(employee)
        db.flush()
    role_record = (
        db.query(ClientUserRole)
        .filter(ClientUserRole.client_id == str(client.id), ClientUserRole.user_id == str(employee.id))
        .one_or_none()
    )
    if role_record:
        role_record.roles = payload.role
    else:
        role_record = ClientUserRole(client_id=str(client.id), user_id=str(employee.id), roles=payload.role)
        db.add(role_record)
    db.commit()
    return ClientUserSummary(
        id=str(employee.id),
        email=employee.email,
        role=payload.role,
        status=employee.status.value,
        last_login=None,
    )


@router.delete("/users/{user_id}")
def disable_user(
    user_id: str,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> dict:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    if not _is_user_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    employee = (
        db.query(ClientEmployee)
        .filter(ClientEmployee.client_id == str(client.id), ClientEmployee.id == user_id)
        .one_or_none()
    )
    if not employee:
        raise HTTPException(status_code=404, detail="user_not_found")
    employee.status = EmployeeStatus.DISABLED
    db.commit()
    return {"status": "disabled"}


@router.patch("/users/{user_id}/roles")
def update_user_roles(
    user_id: str,
    payload: UserRoleUpdateRequest,
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> dict:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")
    if not _is_user_admin(token):
        raise HTTPException(status_code=403, detail="forbidden")
    roles = payload.roles
    roles_normalized = ",".join([str(role) for role in roles])
    record = (
        db.query(ClientUserRole)
        .filter(ClientUserRole.client_id == str(client.id), ClientUserRole.user_id == user_id)
        .one_or_none()
    )
    before = {"roles": record.roles.split(",")} if record else None
    if record:
        record.roles = roles_normalized
    else:
        record = ClientUserRole(client_id=str(client.id), user_id=user_id, roles=roles_normalized)
        db.add(record)
    db.commit()
    _audit_event(
        db,
        request=request,
        token=token,
        event_type="role_change",
        entity_type="membership",
        entity_id=user_id,
        before=before,
        after={"roles": roles},
        action="update_roles",
    )
    return {"status": "ok", "user_id": user_id, "roles": roles}


@router.get("/docs/list", response_model=ClientDocsListResponse)
def list_client_docs(
    doc_type: str | None = Query(None, alias="type"),
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientDocsListResponse:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="missing_client_context")
    assert_module_enabled(db, client_id=str(client_id), module_code="DOCS")
    query = db.query(Document).filter(Document.client_id == str(client_id))
    if doc_type:
        mapped = _DOC_TYPE_ALIASES.get(doc_type.upper())
        if not mapped:
            return ClientDocsListResponse(items=[])
        query = query.filter(Document.document_type == mapped)
    documents = query.order_by(Document.period_to.desc()).all()
    items = [
        ClientDocSummary(
            id=str(doc.id),
            type=doc.document_type.value,
            status=doc.status.value,
            date=doc.period_to,
            download_url=f"/api/core/client/docs/{doc.id}/download",
        )
        for doc in documents
    ]
    return ClientDocsListResponse(items=items)


@router.get("/docs/{document_id}/download")
def download_client_doc(
    document_id: str,
    file_type: DocumentFileType = DocumentFileType.PDF,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> Response:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="missing_client_context")
    assert_module_enabled(db, client_id=str(client_id), module_code="DOCS")
    document = db.query(Document).filter(Document.id == document_id).one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="document_not_found")
    if document.client_id != str(client_id):
        raise HTTPException(status_code=403, detail="forbidden")
    file_record = (
        db.query(DocumentFile)
        .filter(DocumentFile.document_id == document.id, DocumentFile.file_type == file_type)
        .one_or_none()
    )
    if file_record is None:
        raise HTTPException(status_code=404, detail="document_file_not_found")
    payload = DocumentsStorage().fetch_bytes(file_record.object_key)
    if not payload:
        raise HTTPException(status_code=404, detail="document_file_not_found")
    extension = "pdf" if file_type == DocumentFileType.PDF else "xlsx"
    filename = f"{document.document_type.value}_v{document.version}.{extension}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=payload, media_type=file_record.content_type, headers=headers)


@router.get("/subscription", response_model=ClientSubscriptionOut)
def get_subscription(
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> ClientSubscriptionOut:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")

    tenant_id = int(token.get("tenant_id") or DEFAULT_TENANT_ID)
    subscription = get_client_subscription(db, tenant_id=tenant_id, client_id=str(client.id))
    if subscription is None:
        subscription = ensure_free_subscription(db, tenant_id=tenant_id, client_id=str(client.id))

    plan = db.get(SubscriptionPlan, subscription.plan_id) if subscription else None
    plan_code = plan.code if plan else "FREE"
    modules: dict[str, dict] = {}
    limits: dict[str, dict] = {}
    if plan:
        modules, limits = _plan_modules_map(db, plan_id=plan.id)

    return ClientSubscriptionOut(
        plan_code=plan_code,
        status=str(subscription.status) if subscription else None,
        modules=modules,
        limits=limits,
    )


@router.post("/subscription/select", response_model=ClientSubscriptionOut)
def select_subscription(
    payload: ClientSubscriptionSelectRequest,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> ClientSubscriptionOut:
    client = _resolve_client(db, token)
    if client is None:
        raise HTTPException(status_code=404, detail="org_not_found")

    tenant_id = int(token.get("tenant_id") or DEFAULT_TENANT_ID)
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == payload.plan_code).one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="plan_not_found")

    subscription = assign_plan_to_client(
        db,
        tenant_id=tenant_id,
        client_id=str(client.id),
        plan_id=plan.id,
        duration_months=payload.duration_months,
        auto_renew=payload.auto_renew,
    )
    modules, limits = _plan_modules_map(db, plan_id=plan.id)

    return ClientSubscriptionOut(
        plan_code=plan.code,
        status=str(subscription.status),
        modules=modules,
        limits=limits,
    )


@router.get("/subscriptions/plans", response_model=list[SubscriptionPlanOut])
def list_client_plans(
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
) -> list[SubscriptionPlanOut]:
    _ = token
    plans = list_plans(db, active_only=True)
    return [_build_plan_out(db, plan) for plan in plans]
