from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import MetaData, Table, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.schema import DB_SCHEMA
from app.models.audit_log import ActorType, AuditVisibility
from app.models.billing_dunning import (
    BillingDunningChannel,
    BillingDunningEvent,
    BillingDunningEventType,
    BillingDunningStatus,
)
from app.models.client_notification import ClientNotificationSeverity
from app.models.helpdesk import HelpdeskOutboxEventType
from app.models.notifications import NotificationChannel, NotificationPreference, NotificationSubjectType
from app.models.support_ticket import SupportTicket, SupportTicketPriority, SupportTicketStatus
from app.services.audit_service import AuditService, RequestContext
from app.services.client_notifications import ADMIN_TARGET_ROLES, create_notification
from app.services.email_service import enqueue_templated_email
from app.services.email_templates import build_portal_url
from app.services.entitlements_v2_service import get_org_entitlements_snapshot
from app.services.helpdesk_service import (
    build_idempotency_for_ticket,
    build_ticket_payload,
    enqueue_helpdesk_event,
    get_active_integration,
    schedule_helpdesk_outbox,
)
from app.services.support_ticket_sla import (
    DEFAULT_FIRST_RESPONSE_MINUTES,
    DEFAULT_RESOLUTION_MINUTES,
    SupportTicketSlaConfig,
    initialize_support_ticket_sla,
    load_support_ticket_sla_config,
)
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)

DUNNING_WINDOW_HOURS = 6
EMAIL_RATE_LIMIT = timedelta(days=1)


@dataclass(frozen=True)
class DunningInvoiceContext:
    org_id: int
    invoice_id: int
    subscription_id: int | None
    invoice_status: str
    subscription_status: str | None
    due_at: datetime
    suspend_at: datetime | None
    total_amount: Decimal | None
    currency: str | None


@dataclass(frozen=True)
class DunningNotification:
    event_type: str
    title: str
    body: str
    severity: ClientNotificationSeverity


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=db.get_bind(), schema=DB_SCHEMA)


def _table_exists(db: Session, name: str) -> bool:
    try:
        from sqlalchemy import inspect

        inspector = inspect(db.get_bind())
        return inspector.has_table(name, schema=DB_SCHEMA)
    except Exception:
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _format_date(value: datetime | None) -> str:
    if not value:
        return "—"
    return value.astimezone(timezone.utc).strftime("%d.%m.%Y")


def _format_amount(amount: Decimal | None, currency: str | None) -> str:
    if amount is None:
        amount = Decimal("0")
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    return f"{amount:.2f} {currency or 'RUB'}"


def _resolve_billing_email(db: Session, org_id: int) -> str | None:
    if not _table_exists(db, "billing_accounts"):
        return None
    billing_accounts = _table(db, "billing_accounts")
    row = (
        db.execute(select(billing_accounts.c.billing_email).where(billing_accounts.c.org_id == org_id))
        .mappings()
        .first()
    )
    if row and row.get("billing_email"):
        return str(row["billing_email"])
    return None


def _resolve_email_preference(db: Session, *, org_id: int, event_type: str) -> tuple[bool, str | None]:
    pref = (
        db.query(NotificationPreference)
        .filter(NotificationPreference.subject_type == NotificationSubjectType.CLIENT)
        .filter(NotificationPreference.subject_id == str(org_id))
        .filter(NotificationPreference.event_type == event_type)
        .filter(NotificationPreference.channel == NotificationChannel.EMAIL)
        .one_or_none()
    )
    if not pref:
        return True, None
    return bool(pref.enabled), pref.address_override


def _build_notification(event: BillingDunningEventType, ctx: DunningInvoiceContext) -> DunningNotification:
    due_date = _format_date(ctx.due_at)
    amount = _format_amount(ctx.total_amount, ctx.currency)
    invoice_ref = f"#{ctx.invoice_id}"

    if event == BillingDunningEventType.DUE_SOON_7D:
        return DunningNotification(
            event_type="billing_due_soon_7d",
            title="Счёт скоро к оплате",
            body=(
                f"Счёт {invoice_ref} скоро к оплате. Срок: {due_date}. "
                f"Сумма: {amount}. Оплатите по реквизитам или отправьте подтверждение в портале."
            ),
            severity=ClientNotificationSeverity.INFO,
        )
    if event == BillingDunningEventType.DUE_SOON_1D:
        return DunningNotification(
            event_type="billing_due_soon_1d",
            title="Напоминание об оплате",
            body=(
                f"Счёт {invoice_ref} к оплате завтра. Срок: {due_date}. "
                f"Сумма: {amount}. Оплатите по реквизитам или отправьте подтверждение в портале."
            ),
            severity=ClientNotificationSeverity.INFO,
        )
    if event == BillingDunningEventType.OVERDUE_1D:
        return DunningNotification(
            event_type="billing_overdue_1d",
            title="Счёт просрочен",
            body=(
                f"Счёт {invoice_ref} просрочен на 1 день. "
                "Доступ может быть ограничен. Оплатите или отправьте подтверждение."
            ),
            severity=ClientNotificationSeverity.WARNING,
        )
    if event == BillingDunningEventType.OVERDUE_7D:
        return DunningNotification(
            event_type="billing_overdue_7d",
            title="Просрочка по счёту",
            body=(
                f"Счёт {invoice_ref} просрочен на 7 дней. "
                "Оплатите или отправьте подтверждение в портале."
            ),
            severity=ClientNotificationSeverity.WARNING,
        )
    if event == BillingDunningEventType.PRE_SUSPEND_1D:
        return DunningNotification(
            event_type="billing_pre_suspend_1d",
            title="Предупреждение о приостановке",
            body=(
                f"Через 24 часа доступ будет приостановлен при отсутствии оплаты. "
                f"Счёт {invoice_ref}: сумма {amount}."
            ),
            severity=ClientNotificationSeverity.CRITICAL,
        )
    return DunningNotification(
        event_type="billing_suspended",
        title="Доступ приостановлен",
        body=(
            f"Доступ приостановлен из-за неоплаты. Счёт {invoice_ref}: сумма {amount}. "
            "Оплатите или отправьте подтверждение в портале."
        ),
        severity=ClientNotificationSeverity.CRITICAL,
    )


def _insert_dunning_event(
    db: Session,
    *,
    org_id: int,
    invoice_id: int,
    event_type: BillingDunningEventType,
    channel: BillingDunningChannel,
    status: BillingDunningStatus,
    sent_at: datetime | None,
    idempotency_key: str,
    error: str | None,
) -> bool:
    insert_stmt = (
        pg_insert(BillingDunningEvent.__table__)
        .values(
            org_id=org_id,
            invoice_id=invoice_id,
            event_type=event_type,
            channel=channel,
            status=status,
            sent_at=sent_at,
            idempotency_key=idempotency_key,
            error=error,
        )
        .on_conflict_do_nothing(index_elements=["idempotency_key"])
        .returning(BillingDunningEvent.id)
    )
    inserted = db.execute(insert_stmt).scalar_one_or_none()
    return inserted is not None


def _update_dunning_status(
    db: Session,
    *,
    idempotency_key: str,
    status: BillingDunningStatus,
    error: str | None = None,
) -> None:
    db.execute(
        update(BillingDunningEvent.__table__)
        .where(BillingDunningEvent.__table__.c.idempotency_key == idempotency_key)
        .values(status=status, error=error)
    )


def _audit_dunning_event(
    db: Session,
    *,
    event_type: str,
    ctx: DunningInvoiceContext,
    dunning_type: BillingDunningEventType,
    channel: BillingDunningChannel | None,
    reason: str | None = None,
) -> None:
    AuditService(db).audit(
        event_type=event_type,
        entity_type="billing_invoice",
        entity_id=str(ctx.invoice_id),
        action=event_type,
        after={
            "org_id": ctx.org_id,
            "invoice_id": ctx.invoice_id,
            "type": dunning_type.value,
            "channel": channel.value if channel else None,
            "reason": reason,
        },
        request_ctx=RequestContext(actor_type=ActorType.SYSTEM, actor_id="billing_dunning"),
    )


def _support_ticket_tables_ready(db: Session) -> bool:
    return _table_exists(db, "support_tickets")


def _maybe_create_support_ticket_for_suspend(
    db: Session,
    *,
    ctx: DunningInvoiceContext,
) -> SupportTicket | None:
    if not _support_ticket_tables_ready(db):
        return None

    subject = f"Billing: account suspended (Invoice #{ctx.invoice_id})"
    existing = (
        db.query(SupportTicket)
        .filter(SupportTicket.org_id == str(ctx.org_id))
        .filter(SupportTicket.subject == subject)
        .filter(SupportTicket.status != SupportTicketStatus.CLOSED)
        .one_or_none()
    )
    if existing:
        return existing

    amount = _format_amount(ctx.total_amount, ctx.currency)
    message = (
        "Доступ приостановлен из-за неоплаты.\n"
        f"Счёт: #{ctx.invoice_id}\n"
        f"Сумма: {amount}\n"
        f"Срок оплаты: {_format_date(ctx.due_at)}\n"
        f"Дата приостановки: {_format_date(ctx.suspend_at)}\n"
    )
    ticket = SupportTicket(
        org_id=str(ctx.org_id),
        created_by_user_id="system",
        subject=subject,
        message=message,
        status=SupportTicketStatus.OPEN,
        priority=SupportTicketPriority.NORMAL,
    )
    try:
        sla_config = load_support_ticket_sla_config(db, org_id=str(ctx.org_id))
    except Exception:  # noqa: BLE001 - optional SLA table
        sla_config = SupportTicketSlaConfig(
            first_response_minutes=DEFAULT_FIRST_RESPONSE_MINUTES,
            resolution_minutes=DEFAULT_RESOLUTION_MINUTES,
        )
    initialize_support_ticket_sla(ticket, sla_config)
    db.add(ticket)
    db.flush()
    AuditService(db).audit(
        event_type="support_ticket_created",
        entity_type="support_ticket",
        entity_id=str(ticket.id),
        action="support_ticket_created",
        visibility=AuditVisibility.INTERNAL,
        after={"status": ticket.status.value, "priority": ticket.priority.value, "subject": ticket.subject},
        request_ctx=RequestContext(actor_type=ActorType.SYSTEM, actor_id="billing_dunning"),
    )

    integration = get_active_integration(db, org_id=str(ctx.org_id))
    if integration:
        outbox = enqueue_helpdesk_event(
            db,
            org_id=str(ctx.org_id),
            provider=integration.provider,
            internal_ticket_id=str(ticket.id),
            event_type=HelpdeskOutboxEventType.TICKET_CREATED,
            payload=build_ticket_payload(ticket=ticket, created_by_email=None, attachments=[]),
            idempotency_key=build_idempotency_for_ticket(
                HelpdeskOutboxEventType.TICKET_CREATED,
                str(ticket.id),
                str(ctx.org_id),
            ),
        )
        schedule_helpdesk_outbox(outbox)

    return ticket


def _rate_limited(
    db: Session,
    *,
    org_id: int,
    now: datetime,
    cache: dict[int, bool],
) -> bool:
    if org_id in cache:
        return cache[org_id]
    limit_start = now - EMAIL_RATE_LIMIT
    exists = (
        db.query(BillingDunningEvent.id)
        .filter(BillingDunningEvent.org_id == org_id)
        .filter(BillingDunningEvent.channel == BillingDunningChannel.EMAIL)
        .filter(BillingDunningEvent.status == BillingDunningStatus.SENT)
        .filter(BillingDunningEvent.sent_at.isnot(None))
        .filter(BillingDunningEvent.sent_at >= limit_start)
        .first()
        is not None
    )
    cache[org_id] = exists
    return exists


def _dispatch_dunning(
    db: Session,
    *,
    ctx: DunningInvoiceContext,
    dunning_type: BillingDunningEventType,
    now: datetime,
    email_rate_cache: dict[int, bool],
    stats: dict[str, int],
) -> None:
    notification = _build_notification(dunning_type, ctx)
    link = f"/client/invoices/{ctx.invoice_id}"

    in_app_key = (
        f"dunning:{dunning_type.value}:org:{ctx.org_id}:invoice:{ctx.invoice_id}:"
        f"channel:{BillingDunningChannel.IN_APP.value}"
    )
    if _insert_dunning_event(
        db,
        org_id=ctx.org_id,
        invoice_id=ctx.invoice_id,
        event_type=dunning_type,
        channel=BillingDunningChannel.IN_APP,
        status=BillingDunningStatus.SENT,
        sent_at=now,
        idempotency_key=in_app_key,
        error=None,
    ):
        create_notification(
            db,
            org_id=str(ctx.org_id),
            event_type=notification.event_type,
            severity=notification.severity,
            title=notification.title,
            body=notification.body,
            link=link,
            target_roles=ADMIN_TARGET_ROLES,
            entity_type="billing_invoice",
            entity_id=str(ctx.invoice_id),
        )
        _audit_dunning_event(
            db,
            event_type="dunning_sent",
            ctx=ctx,
            dunning_type=dunning_type,
            channel=BillingDunningChannel.IN_APP,
        )
        stats["sent"] += 1

    email_key = (
        f"dunning:{dunning_type.value}:org:{ctx.org_id}:invoice:{ctx.invoice_id}:"
        f"channel:{BillingDunningChannel.EMAIL.value}"
    )
    email_enabled, override_email = _resolve_email_preference(db, org_id=ctx.org_id, event_type=notification.event_type)
    if not email_enabled:
        if _insert_dunning_event(
            db,
            org_id=ctx.org_id,
            invoice_id=ctx.invoice_id,
            event_type=dunning_type,
            channel=BillingDunningChannel.EMAIL,
            status=BillingDunningStatus.SKIPPED,
            sent_at=now,
            idempotency_key=email_key,
            error="email_disabled",
        ):
            _audit_dunning_event(
                db,
                event_type="dunning_skipped",
                ctx=ctx,
                dunning_type=dunning_type,
                channel=BillingDunningChannel.EMAIL,
                reason="email_disabled",
            )
            stats["skipped"] += 1
        return

    if _rate_limited(db, org_id=ctx.org_id, now=now, cache=email_rate_cache):
        if _insert_dunning_event(
            db,
            org_id=ctx.org_id,
            invoice_id=ctx.invoice_id,
            event_type=dunning_type,
            channel=BillingDunningChannel.EMAIL,
            status=BillingDunningStatus.SKIPPED,
            sent_at=now,
            idempotency_key=email_key,
            error="rate_limited",
        ):
            _audit_dunning_event(
                db,
                event_type="dunning_skipped",
                ctx=ctx,
                dunning_type=dunning_type,
                channel=BillingDunningChannel.EMAIL,
                reason="rate_limited",
            )
            stats["skipped"] += 1
        return

    email_to = override_email or _resolve_billing_email(db, ctx.org_id)
    if not email_to:
        if _insert_dunning_event(
            db,
            org_id=ctx.org_id,
            invoice_id=ctx.invoice_id,
            event_type=dunning_type,
            channel=BillingDunningChannel.EMAIL,
            status=BillingDunningStatus.SKIPPED,
            sent_at=now,
            idempotency_key=email_key,
            error="email_missing",
        ):
            _audit_dunning_event(
                db,
                event_type="dunning_skipped",
                ctx=ctx,
                dunning_type=dunning_type,
                channel=BillingDunningChannel.EMAIL,
                reason="email_missing",
            )
            stats["skipped"] += 1
        return

    if not _insert_dunning_event(
        db,
        org_id=ctx.org_id,
        invoice_id=ctx.invoice_id,
        event_type=dunning_type,
        channel=BillingDunningChannel.EMAIL,
        status=BillingDunningStatus.SENT,
        sent_at=now,
        idempotency_key=email_key,
        error=None,
    ):
        return

    try:
        enqueue_templated_email(
            db,
            template_key=notification.event_type,
            to=[email_to],
            idempotency_key=email_key,
            org_id=str(ctx.org_id),
            user_id=None,
            context={
                "body": notification.body,
                "link": build_portal_url(link),
                "title": notification.title,
            },
            tags={"billing_invoice_id": str(ctx.invoice_id)},
        )
    except Exception as exc:  # noqa: BLE001 - should not break dunning cycle
        logger.exception("billing_dunning.email_failed", extra={"invoice_id": ctx.invoice_id, "error": str(exc)})
        _update_dunning_status(db, idempotency_key=email_key, status=BillingDunningStatus.FAILED, error=str(exc))
        _audit_dunning_event(
            db,
            event_type="dunning_skipped",
            ctx=ctx,
            dunning_type=dunning_type,
            channel=BillingDunningChannel.EMAIL,
            reason="email_failed",
        )
        stats["failed"] += 1
        return

    _audit_dunning_event(
        db,
        event_type="dunning_sent",
        ctx=ctx,
        dunning_type=dunning_type,
        channel=BillingDunningChannel.EMAIL,
    )
    stats["sent"] += 1
    email_rate_cache[ctx.org_id] = True


def _in_window(now: datetime, *, milestone: datetime) -> bool:
    window_end = milestone + timedelta(hours=DUNNING_WINDOW_HOURS)
    return milestone <= now < window_end


def scan_billing_dunning(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    required_tables = ["billing_invoices", "org_subscriptions", "billing_dunning_events"]
    if not all(_table_exists(db, name) for name in required_tables):
        logger.warning("billing_dunning.tables_missing")
        return {"sent": 0, "skipped": 0, "failed": 0}

    now = now or _now()
    billing_invoices = _table(db, "billing_invoices")
    org_subscriptions = _table(db, "org_subscriptions")

    rows = (
        db.execute(
            select(
                billing_invoices.c.id,
                billing_invoices.c.org_id,
                billing_invoices.c.subscription_id,
                billing_invoices.c.status,
                billing_invoices.c.due_at,
                billing_invoices.c.total_amount,
                billing_invoices.c.currency,
                org_subscriptions.c.status.label("subscription_status"),
                org_subscriptions.c.grace_period_days,
            )
            .select_from(
                billing_invoices.join(
                    org_subscriptions,
                    billing_invoices.c.subscription_id == org_subscriptions.c.id,
                    isouter=True,
                )
            )
            .where(billing_invoices.c.status.in_(["ISSUED", "OVERDUE"]))
            .where(billing_invoices.c.due_at.isnot(None))
        )
        .mappings()
        .all()
    )

    stats = {"sent": 0, "skipped": 0, "failed": 0}
    email_rate_cache: dict[int, bool] = {}

    for row in rows:
        due_at = row.get("due_at")
        if not due_at:
            continue
        subscription_status = row.get("subscription_status")
        if subscription_status == "SUSPENDED":
            continue
        grace_days = int(row.get("grace_period_days") or 0)
        suspend_at = due_at + timedelta(days=grace_days) if grace_days > 0 else None
        ctx = DunningInvoiceContext(
            org_id=row["org_id"],
            invoice_id=row["id"],
            subscription_id=row.get("subscription_id"),
            invoice_status=row["status"],
            subscription_status=subscription_status,
            due_at=due_at,
            suspend_at=suspend_at,
            total_amount=row.get("total_amount"),
            currency=row.get("currency"),
        )

        events: list[tuple[BillingDunningEventType, datetime]] = [
            (BillingDunningEventType.DUE_SOON_7D, due_at - timedelta(days=7)),
            (BillingDunningEventType.DUE_SOON_1D, due_at - timedelta(days=1)),
            (BillingDunningEventType.OVERDUE_1D, due_at + timedelta(days=1)),
            (BillingDunningEventType.OVERDUE_7D, due_at + timedelta(days=7)),
        ]
        if suspend_at and grace_days > 0:
            events.append((BillingDunningEventType.PRE_SUSPEND_1D, suspend_at - timedelta(days=1)))

        for event_type, milestone in events:
            if not _in_window(now, milestone=milestone):
                continue
            if event_type in {BillingDunningEventType.DUE_SOON_7D, BillingDunningEventType.DUE_SOON_1D}:
                if ctx.invoice_status != "ISSUED":
                    continue
            if event_type == BillingDunningEventType.PRE_SUSPEND_1D and not suspend_at:
                continue
            _dispatch_dunning(
                db,
                ctx=ctx,
                dunning_type=event_type,
                now=now,
                email_rate_cache=email_rate_cache,
                stats=stats,
            )

    return stats


def auto_suspend_overdue(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    required_tables = ["billing_invoices", "org_subscriptions", "billing_dunning_events"]
    if not all(_table_exists(db, name) for name in required_tables):
        logger.warning("billing_dunning.tables_missing_suspend")
        return {"suspended": 0, "sent": 0, "skipped": 0, "failed": 0}

    now = now or _now()
    billing_invoices = _table(db, "billing_invoices")
    org_subscriptions = _table(db, "org_subscriptions")

    subscription_columns = [
        org_subscriptions.c.status.label("subscription_status"),
        org_subscriptions.c.grace_period_days,
    ]
    if "suspend_blocked_until" in org_subscriptions.c:
        subscription_columns.append(org_subscriptions.c.suspend_blocked_until)

    rows = (
        db.execute(
            select(
                billing_invoices.c.id,
                billing_invoices.c.org_id,
                billing_invoices.c.subscription_id,
                billing_invoices.c.status,
                billing_invoices.c.due_at,
                billing_invoices.c.total_amount,
                billing_invoices.c.currency,
                *subscription_columns,
            )
            .select_from(
                billing_invoices.join(
                    org_subscriptions,
                    billing_invoices.c.subscription_id == org_subscriptions.c.id,
                    isouter=True,
                )
            )
            .where(billing_invoices.c.status == "OVERDUE")
            .where(billing_invoices.c.due_at.isnot(None))
        )
        .mappings()
        .all()
    )

    stats = {"suspended": 0, "sent": 0, "skipped": 0, "failed": 0}
    email_rate_cache: dict[int, bool] = {}

    for row in rows:
        due_at = row.get("due_at")
        if not due_at:
            continue
        grace_days = int(row.get("grace_period_days") or 0)
        suspend_at = due_at + timedelta(days=grace_days)
        if now < suspend_at:
            continue
        blocked_until = row.get("suspend_blocked_until")
        ctx = DunningInvoiceContext(
            org_id=row["org_id"],
            invoice_id=row["id"],
            subscription_id=row.get("subscription_id"),
            invoice_status=row["status"],
            subscription_status=row.get("subscription_status"),
            due_at=due_at,
            suspend_at=suspend_at,
            total_amount=row.get("total_amount"),
            currency=row.get("currency"),
        )
        if blocked_until and now < blocked_until:
            _audit_dunning_event(
                db,
                event_type="dunning_skipped",
                ctx=ctx,
                dunning_type=BillingDunningEventType.SUSPENDED,
                channel=None,
                reason="suspend_blocked_until",
            )
            stats["skipped"] += 1
            continue
        if row.get("subscription_status") == "SUSPENDED":
            continue

        db.execute(
            update(org_subscriptions)
            .where(org_subscriptions.c.id == row.get("subscription_id"))
            .values(status="SUSPENDED")
        )
        get_org_entitlements_snapshot(db, org_id=row["org_id"])
        ctx = DunningInvoiceContext(
            org_id=row["org_id"],
            invoice_id=row["id"],
            subscription_id=row.get("subscription_id"),
            invoice_status=row["status"],
            subscription_status="SUSPENDED",
            due_at=due_at,
            suspend_at=suspend_at,
            total_amount=row.get("total_amount"),
            currency=row.get("currency"),
        )
        AuditService(db).audit(
            event_type="auto_suspended",
            entity_type="org_subscription",
            entity_id=str(row.get("subscription_id")),
            action="SUSPEND",
            after={
                "org_id": row["org_id"],
                "invoice_id": row["id"],
                "subscription_id": row.get("subscription_id"),
            },
            request_ctx=RequestContext(actor_type=ActorType.SYSTEM, actor_id="billing_suspend"),
        )
        _dispatch_dunning(
            db,
            ctx=ctx,
            dunning_type=BillingDunningEventType.SUSPENDED,
            now=now,
            email_rate_cache=email_rate_cache,
            stats=stats,
        )
        try:
            _maybe_create_support_ticket_for_suspend(db, ctx=ctx)
        except Exception as exc:  # noqa: BLE001 - ticket creation should not block suspend
            logger.exception(
                "billing_dunning.support_ticket_failed",
                extra={"invoice_id": ctx.invoice_id, "error": str(exc)},
            )
        stats["suspended"] += 1

    return stats


__all__ = ["auto_suspend_overdue", "scan_billing_dunning"]
