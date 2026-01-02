from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.fuel import (
    FleetNotificationChannel,
    FleetNotificationChannelType,
    FuelCardStatus,
    FuelLimitScopeType,
)
from app.schemas.client_fleet import (
    FleetAccessGrantIn,
    FleetAccessListResponse,
    FleetAccessOut,
    FleetAccessRevokeIn,
    FleetCardCreateIn,
    FleetCardListResponse,
    FleetCardOut,
    FleetCardUnblockIn,
    FleetEmployeeInviteIn,
    FleetEmployeeListResponse,
    FleetEmployeeOut,
    FleetGroupCreateIn,
    FleetGroupListResponse,
    FleetGroupMemberChangeIn,
    FleetGroupOut,
    FleetLimitListResponse,
    FleetLimitOut,
    FleetLimitRevokeIn,
    FleetLimitSetIn,
    FleetAlertIgnoreIn,
    FleetAlertListResponse,
    FleetAlertOut,
    FleetNotificationChannelIn,
    FleetNotificationChannelListResponse,
    FleetNotificationChannelOut,
    FleetNotificationPolicyIn,
    FleetNotificationPolicyListResponse,
    FleetNotificationPolicyOut,
    FleetNotificationTestOut,
    FleetTelegramBindingListResponse,
    FleetTelegramBindingOut,
    FleetTelegramLinkIn,
    FleetTelegramLinkOut,
    FleetPushSubscriptionIn,
    FleetPushSubscriptionLookupIn,
    FleetPushSubscriptionOut,
    FleetActionPolicyIn,
    FleetActionPolicyListResponse,
    FleetActionPolicyOut,
    FleetSpendSummaryOut,
    FleetSpendSummaryRow,
    FleetSpendSummaryTotals,
    FleetTransactionListResponse,
    FleetTransactionOut,
    FleetTransactionsExportOut,
)
from app.models.fuel import FleetNotificationEventType, FleetNotificationSeverity
from app.security.rbac.guard import require_permission
from app.security.rbac.permissions import Permission
from app.security.rbac.principal import Principal
from app.services import fleet_service
from app.services.fleet_notification_dispatcher import dispatch_outbox_item, enqueue_notification
from neft_shared.settings import get_settings

router = APIRouter(prefix="/api/client/fleet", tags=["client-fleet"])


def _request_ids(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("x-request-id"), request.headers.get("x-trace-id")


def _ensure_client_context(principal: Principal) -> str:
    if principal.client_id is None:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "missing_client"})
    return str(principal.client_id)


def _card_to_schema(card) -> FleetCardOut:
    return FleetCardOut(
        id=str(card.id),
        card_alias=card.card_alias,
        masked_pan=card.masked_pan,
        token_ref=card.token_ref,
        status=card.status,
        currency=card.currency,
        issued_at=card.issued_at,
        created_at=card.created_at,
    )


def _group_to_schema(group) -> FleetGroupOut:
    return FleetGroupOut(
        id=str(group.id),
        name=group.name,
        description=group.description,
        created_at=group.created_at,
    )


def _employee_to_schema(employee) -> FleetEmployeeOut:
    return FleetEmployeeOut(
        id=str(employee.id),
        email=employee.email,
        status=employee.status,
        created_at=employee.created_at,
    )


def _access_to_schema(access) -> FleetAccessOut:
    return FleetAccessOut(
        id=str(access.id),
        employee_id=str(access.employee_id),
        role=access.role,
        created_at=access.created_at,
        revoked_at=access.revoked_at,
    )


def _limit_to_schema(limit) -> FleetLimitOut:
    return FleetLimitOut(
        id=str(limit.id),
        scope_type=limit.scope_type,
        scope_id=str(limit.scope_id) if limit.scope_id else None,
        period=limit.period,
        amount_limit=limit.amount_limit,
        volume_limit_liters=limit.volume_limit_liters,
        categories=limit.categories,
        stations_allowlist=limit.stations_allowlist,
        active=limit.active,
        effective_from=limit.effective_from,
        created_at=limit.created_at,
    )


def _transaction_to_schema(tx) -> FleetTransactionOut:
    return FleetTransactionOut(
        id=str(tx.id),
        card_id=str(tx.card_id),
        occurred_at=tx.occurred_at,
        amount=tx.amount,
        currency=tx.currency,
        volume_liters=tx.volume_liters,
        category=tx.category,
        merchant_name=tx.merchant_name,
        merchant_key=tx.merchant_key,
        station_id=tx.station_external_id,
        location=tx.location,
        external_ref=tx.external_ref,
        provider_code=tx.provider_code,
        provider_tx_id=tx.provider_tx_id,
        limit_check_status=tx.limit_check_status.value if tx.limit_check_status else None,
        created_at=tx.created_at,
    )


@router.get(
    "/cards",
    response_model=FleetCardListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_CARDS_LIST.value))],
)
def list_cards(
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_CARDS_LIST.value)),
    db: Session = Depends(get_db),
) -> FleetCardListResponse:
    client_id = _ensure_client_context(principal)
    cards = fleet_service.list_cards(db, client_id=client_id, principal=principal)
    return FleetCardListResponse(items=[_card_to_schema(card) for card in cards])


@router.post(
    "/cards",
    response_model=FleetCardOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_CARDS_MANAGE.value))],
)
def create_card(
    payload: FleetCardCreateIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_CARDS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetCardOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    card = fleet_service.create_card(
        db,
        client_id=client_id,
        alias=payload.card_alias,
        masked_pan=payload.masked_pan,
        token_ref=payload.token_ref,
        currency=payload.currency,
        issued_at=payload.issued_at,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _card_to_schema(card)


@router.get(
    "/cards/{card_id}",
    response_model=FleetCardOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_CARDS_VIEW.value))],
)
def get_card(
    card_id: str,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_CARDS_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetCardOut:
    card = fleet_service.get_card(db, card_id=card_id, principal=principal)
    return _card_to_schema(card)


@router.post(
    "/cards/{card_id}/block",
    response_model=FleetCardOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_CARDS_MANAGE.value))],
)
def block_card(
    card_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_CARDS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetCardOut:
    request_id, trace_id = _request_ids(request)
    card = fleet_service.set_card_status(
        db,
        card_id=card_id,
        status=FuelCardStatus.BLOCKED,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _card_to_schema(card)


@router.post(
    "/cards/{card_id}/unblock",
    response_model=FleetCardOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_CARDS_MANAGE.value))],
)
def unblock_card(
    card_id: str,
    payload: FleetCardUnblockIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_CARDS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetCardOut:
    request_id, trace_id = _request_ids(request)
    card = fleet_service.unblock_card_with_reason(
        db,
        card_id=card_id,
        reason=payload.reason,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _card_to_schema(card)


@router.get(
    "/groups",
    response_model=FleetGroupListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_LIST.value))],
)
def list_groups(
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_LIST.value)),
    db: Session = Depends(get_db),
) -> FleetGroupListResponse:
    client_id = _ensure_client_context(principal)
    groups = fleet_service.list_groups(db, client_id=client_id, principal=principal)
    return FleetGroupListResponse(items=[_group_to_schema(group) for group in groups])


@router.post(
    "/groups",
    response_model=FleetGroupOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value))],
)
def create_group(
    payload: FleetGroupCreateIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetGroupOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    group = fleet_service.create_group(
        db,
        client_id=client_id,
        name=payload.name,
        description=payload.description,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _group_to_schema(group)


@router.post(
    "/groups/{group_id}/members/add",
    response_model=dict,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value))],
)
def add_card_to_group(
    group_id: str,
    payload: FleetGroupMemberChangeIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> dict:
    request_id, trace_id = _request_ids(request)
    member = fleet_service.add_card_to_group(
        db,
        group_id=group_id,
        card_id=payload.card_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return {"group_id": str(member.group_id), "card_id": str(member.card_id)}


@router.post(
    "/groups/{group_id}/members/remove",
    response_model=dict,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value))],
)
def remove_card_from_group(
    group_id: str,
    payload: FleetGroupMemberChangeIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> dict:
    request_id, trace_id = _request_ids(request)
    member = fleet_service.remove_card_from_group(
        db,
        group_id=group_id,
        card_id=payload.card_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return {"group_id": str(member.group_id), "card_id": str(member.card_id)}


@router.get(
    "/groups/{group_id}/access",
    response_model=FleetAccessListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value))],
)
def list_group_access(
    group_id: str,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetAccessListResponse:
    items = fleet_service.list_group_access(db, group_id=group_id, principal=principal)
    return FleetAccessListResponse(items=[_access_to_schema(item) for item in items])


@router.post(
    "/groups/{group_id}/access/grant",
    response_model=FleetAccessOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value))],
)
def grant_group_access(
    group_id: str,
    payload: FleetAccessGrantIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetAccessOut:
    request_id, trace_id = _request_ids(request)
    access = fleet_service.grant_group_access(
        db,
        group_id=group_id,
        employee_id=payload.employee_id,
        role=payload.role,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _access_to_schema(access)


@router.post(
    "/groups/{group_id}/access/revoke",
    response_model=FleetAccessOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value))],
)
def revoke_group_access(
    group_id: str,
    payload: FleetAccessRevokeIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_GROUPS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetAccessOut:
    request_id, trace_id = _request_ids(request)
    access = fleet_service.revoke_group_access(
        db,
        group_id=group_id,
        employee_id=payload.employee_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _access_to_schema(access)


@router.get(
    "/limits",
    response_model=FleetLimitListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def list_limits(
    scope_type: FuelLimitScopeType = Query(...),
    scope_id: str = Query(...),
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetLimitListResponse:
    client_id = _ensure_client_context(principal)
    limits = fleet_service.list_limits(
        db,
        client_id=client_id,
        scope_type=scope_type,
        scope_id=scope_id,
        principal=principal,
    )
    return FleetLimitListResponse(items=[_limit_to_schema(limit) for limit in limits])


@router.post(
    "/limits/set",
    response_model=FleetLimitOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_LIMITS_MANAGE.value))],
)
def set_limit(
    payload: FleetLimitSetIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_LIMITS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetLimitOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    limit = fleet_service.set_limit(
        db,
        client_id=client_id,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        period=payload.period,
        amount_limit=payload.amount_limit,
        volume_limit_liters=payload.volume_limit_liters,
        categories=payload.categories,
        stations_allowlist=payload.stations_allowlist,
        effective_from=payload.effective_from,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _limit_to_schema(limit)


@router.post(
    "/limits/revoke",
    response_model=FleetLimitOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_LIMITS_MANAGE.value))],
)
def revoke_limit(
    payload: FleetLimitRevokeIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_LIMITS_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetLimitOut:
    request_id, trace_id = _request_ids(request)
    limit = fleet_service.revoke_limit(
        db,
        limit_id=payload.limit_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _limit_to_schema(limit)


@router.get(
    "/transactions",
    response_model=FleetTransactionListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def list_transactions(
    card_id: str | None = Query(None),
    group_id: str | None = Query(None),
    merchant: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetTransactionListResponse:
    client_id = _ensure_client_context(principal)
    items = fleet_service.list_transactions(
        db,
        client_id=client_id,
        principal=principal,
        card_id=card_id,
        group_id=group_id,
        merchant=merchant,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return FleetTransactionListResponse(items=[_transaction_to_schema(item) for item in items])


@router.get(
    "/spend/summary",
    response_model=FleetSpendSummaryOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def spend_summary(
    group_by: str = Query("day"),
    card_id: str | None = Query(None),
    group_id: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetSpendSummaryOut:
    client_id = _ensure_client_context(principal)
    rows = fleet_service.spend_summary(
        db,
        client_id=client_id,
        principal=principal,
        group_by=group_by,
        card_id=card_id,
        group_id=group_id,
        date_from=date_from,
        date_to=date_to,
    )
    return FleetSpendSummaryOut(
        group_by=group_by,
        totals=FleetSpendSummaryTotals(amount=rows.totals.amount, volume_liters=rows.totals.volume_liters),
        rows=[
            FleetSpendSummaryRow(
                key=row.key,
                amount=row.amount,
                volume_liters=row.volume_liters,
            )
            for row in rows.rows
        ],
        top_merchants=[
            FleetSpendSummaryRow(
                key=row.key,
                amount=row.amount,
                volume_liters=row.volume_liters,
            )
            for row in rows.top_merchants
        ],
        top_categories=[
            FleetSpendSummaryRow(
                key=row.key,
                amount=row.amount,
                volume_liters=row.volume_liters,
            )
            for row in rows.top_categories
        ],
    )


@router.get(
    "/transactions/export",
    response_model=FleetTransactionsExportOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def export_transactions(
    card_id: str | None = Query(None),
    group_id: str | None = Query(None),
    summary_group_by: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetTransactionsExportOut:
    client_id = _ensure_client_context(principal)
    export_id, url, expires_in, metadata = fleet_service.export_transactions(
        db,
        client_id=client_id,
        principal=principal,
        card_id=card_id,
        group_id=group_id,
        summary_group_by=summary_group_by,
        date_from=date_from,
        date_to=date_to,
    )
    db.commit()
    return FleetTransactionsExportOut(
        export_id=export_id,
        url=url,
        expires_in=expires_in,
        content_sha256=metadata.get("content_sha256"),
        artifact_signature=metadata.get("artifact_signature"),
        artifact_signature_alg=metadata.get("artifact_signature_alg"),
        artifact_signing_key_id=metadata.get("artifact_signing_key_id"),
    )


@router.get(
    "/alerts",
    response_model=FleetAlertListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def list_alerts(
    status: str | None = Query(None),
    severity_min: str | None = Query(None),
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetAlertListResponse:
    client_id = _ensure_client_context(principal)
    alerts = fleet_service.list_alerts(
        db,
        client_id=client_id,
        principal=principal,
        status=status,
        severity_min=severity_min,
    )
    return FleetAlertListResponse(
        items=[
            FleetAlertOut(
                id=alert["id"],
                alert_type=alert["alert_type"],
                status=alert["status"],
                severity=alert["severity"],
                occurred_at=alert["occurred_at"],
                card_id=alert.get("card_id"),
                group_id=alert.get("group_id"),
                tx_id=alert.get("tx_id"),
                limit_id=alert.get("limit_id"),
                breach_type=alert.get("breach_type"),
                threshold=alert.get("threshold"),
                observed=alert.get("observed"),
                delta=alert.get("delta"),
                period=alert.get("period"),
                anomaly_type=alert.get("anomaly_type"),
                score=alert.get("score"),
            )
            for alert in alerts
        ]
    )


@router.post(
    "/alerts/{alert_id}/ack",
    response_model=FleetAlertOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def ack_alert(
    alert_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetAlertOut:
    request_id, trace_id = _request_ids(request)
    alert = fleet_service.update_alert_status(
        db,
        alert_id=alert_id,
        status="ACKED",
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        reason=None,
    )
    db.commit()
    return FleetAlertOut(
        id=alert["id"],
        alert_type=alert["alert_type"],
        status=alert["status"],
        severity=alert["severity"],
        occurred_at=alert["occurred_at"],
        card_id=alert.get("card_id"),
        group_id=alert.get("group_id"),
        tx_id=alert.get("tx_id"),
        limit_id=alert.get("limit_id"),
        breach_type=alert.get("breach_type"),
        threshold=alert.get("threshold"),
        observed=alert.get("observed"),
        delta=alert.get("delta"),
        period=alert.get("period"),
        anomaly_type=alert.get("anomaly_type"),
        score=alert.get("score"),
    )


@router.post(
    "/alerts/{alert_id}/ignore",
    response_model=FleetAlertOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def ignore_alert(
    alert_id: str,
    payload: FleetAlertIgnoreIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetAlertOut:
    request_id, trace_id = _request_ids(request)
    alert = fleet_service.update_alert_status(
        db,
        alert_id=alert_id,
        status="IGNORED",
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
        reason=payload.reason,
    )
    db.commit()
    return FleetAlertOut(
        id=alert["id"],
        alert_type=alert["alert_type"],
        status=alert["status"],
        severity=alert["severity"],
        occurred_at=alert["occurred_at"],
        card_id=alert.get("card_id"),
        group_id=alert.get("group_id"),
        tx_id=alert.get("tx_id"),
        limit_id=alert.get("limit_id"),
        breach_type=alert.get("breach_type"),
        threshold=alert.get("threshold"),
        observed=alert.get("observed"),
        delta=alert.get("delta"),
        period=alert.get("period"),
        anomaly_type=alert.get("anomaly_type"),
        score=alert.get("score"),
    )


@router.get(
    "/notifications/channels",
    response_model=FleetNotificationChannelListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def list_notification_channels(
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetNotificationChannelListResponse:
    client_id = _ensure_client_context(principal)
    channels = fleet_service.list_notification_channels(db, client_id=client_id, principal=principal)
    return FleetNotificationChannelListResponse(
        items=[
            FleetNotificationChannelOut(
                id=str(channel.id),
                channel_type=channel.channel_type,
                target=channel.target,
                status=channel.status,
                created_at=channel.created_at,
            )
            for channel in channels
        ]
    )


@router.post(
    "/notifications/channels",
    response_model=FleetNotificationChannelOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def create_notification_channel(
    payload: FleetNotificationChannelIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetNotificationChannelOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    channel = fleet_service.create_notification_channel(
        db,
        client_id=client_id,
        channel_type=payload.channel_type,
        target=payload.target,
        secret_ref=payload.secret_ref,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return FleetNotificationChannelOut(
        id=str(channel.id),
        channel_type=channel.channel_type,
        target=channel.target,
        status=channel.status,
        created_at=channel.created_at,
    )


@router.post(
    "/notifications/channels/{channel_id}/disable",
    response_model=FleetNotificationChannelOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def disable_notification_channel(
    channel_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetNotificationChannelOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    channel = fleet_service.disable_notification_channel(
        db,
        channel_id=channel_id,
        client_id=client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return FleetNotificationChannelOut(
        id=str(channel.id),
        channel_type=channel.channel_type,
        target=channel.target,
        status=channel.status,
        created_at=channel.created_at,
    )


@router.post(
    "/notifications/channels/{channel_id}/test",
    response_model=FleetNotificationTestOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def test_notification_channel(
    channel_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetNotificationTestOut:
    client_id = _ensure_client_context(principal)
    channel = (
        db.query(FleetNotificationChannel)
        .filter(FleetNotificationChannel.id == channel_id)
        .filter(FleetNotificationChannel.client_id == client_id)
        .one_or_none()
    )
    if not channel:
        raise HTTPException(status_code=404, detail="channel_not_found")
    request_id, trace_id = _request_ids(request)
    payload = {
        "client_id": client_id,
        "event_type": FleetNotificationEventType.TEST.value,
        "severity": FleetNotificationSeverity.HIGH.value,
        "summary": {"message": "Test notification"},
        "channels_override": [channel.channel_type.value],
        "route": "/client/fleet/notifications/alerts",
    }
    outbox = enqueue_notification(
        db,
        client_id=client_id,
        event_type=FleetNotificationEventType.TEST,
        severity=FleetNotificationSeverity.HIGH,
        event_ref_type="notification_channel",
        event_ref_id=str(channel_id),
        payload=payload,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    outbox = dispatch_outbox_item(db, outbox_id=str(outbox.id))
    db.commit()
    return FleetNotificationTestOut(outbox_id=str(outbox.id), status=outbox.status.value)


@router.post(
    "/notifications/telegram/link",
    response_model=FleetTelegramLinkOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def create_telegram_link(
    payload: FleetTelegramLinkIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetTelegramLinkOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    token = fleet_service.issue_telegram_link_token(
        db,
        client_id=client_id,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    settings = get_settings()
    bot_username = settings.TELEGRAM_BOT_USERNAME
    deep_link = f"https://t.me/{bot_username}?start={token.token}" if bot_username else f"https://t.me/?start={token.token}"
    return FleetTelegramLinkOut(token=token.token, expires_at=token.expires_at, deep_link=deep_link)


@router.get(
    "/notifications/telegram/bindings",
    response_model=FleetTelegramBindingListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def list_telegram_bindings(
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetTelegramBindingListResponse:
    client_id = _ensure_client_context(principal)
    bindings = fleet_service.list_telegram_bindings(db, client_id=client_id, principal=principal)
    return FleetTelegramBindingListResponse(
        items=[
            FleetTelegramBindingOut(
                id=str(binding.id),
                scope_type=binding.scope_type,
                scope_id=str(binding.scope_id) if binding.scope_id else None,
                chat_title=binding.chat_title,
                chat_type=binding.chat_type,
                status=binding.status,
                created_at=binding.created_at,
                verified_at=binding.verified_at,
            )
            for binding in bindings
        ]
    )


@router.post(
    "/notifications/telegram/bindings/{binding_id}/disable",
    response_model=FleetTelegramBindingOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def disable_telegram_binding(
    binding_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetTelegramBindingOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    binding = fleet_service.disable_telegram_binding(
        db,
        binding_id=binding_id,
        client_id=client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return FleetTelegramBindingOut(
        id=str(binding.id),
        scope_type=binding.scope_type,
        scope_id=str(binding.scope_id) if binding.scope_id else None,
        chat_title=binding.chat_title,
        chat_type=binding.chat_type,
        status=binding.status,
        created_at=binding.created_at,
        verified_at=binding.verified_at,
    )


@router.get(
    "/notifications/policies",
    response_model=FleetNotificationPolicyListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def list_notification_policies(
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetNotificationPolicyListResponse:
    client_id = _ensure_client_context(principal)
    policies = fleet_service.list_notification_policies(db, client_id=client_id, principal=principal)
    return FleetNotificationPolicyListResponse(
        items=[
            FleetNotificationPolicyOut(
                id=str(policy.id),
                scope_type=policy.scope_type,
                scope_id=str(policy.scope_id) if policy.scope_id else None,
                event_type=policy.event_type,
                severity_min=policy.severity_min,
                channels=policy.channels or [],
                cooldown_seconds=policy.cooldown_seconds,
                active=policy.active,
                action_on_critical=policy.action_on_critical.value
                if policy.action_on_critical
                else None,
                hard_breach_only=policy.hard_breach_only,
                created_at=policy.created_at,
            )
            for policy in policies
        ]
    )


@router.post(
    "/notifications/policies",
    response_model=FleetNotificationPolicyOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def create_notification_policy(
    payload: FleetNotificationPolicyIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetNotificationPolicyOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    policy = fleet_service.create_notification_policy(
        db,
        client_id=client_id,
        payload=payload,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return FleetNotificationPolicyOut(
        id=str(policy.id),
        scope_type=policy.scope_type,
        scope_id=str(policy.scope_id) if policy.scope_id else None,
        event_type=policy.event_type,
        severity_min=policy.severity_min,
        channels=policy.channels or [],
        cooldown_seconds=policy.cooldown_seconds,
        active=policy.active,
        action_on_critical=policy.action_on_critical.value if policy.action_on_critical else None,
        hard_breach_only=policy.hard_breach_only,
        created_at=policy.created_at,
    )


@router.post(
    "/notifications/policies/{policy_id}/disable",
    response_model=FleetNotificationPolicyOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def disable_notification_policy(
    policy_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
    ) -> FleetNotificationPolicyOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    policy = fleet_service.disable_notification_policy(
        db,
        policy_id=policy_id,
        client_id=client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return FleetNotificationPolicyOut(
        id=str(policy.id),
        scope_type=policy.scope_type,
        scope_id=str(policy.scope_id) if policy.scope_id else None,
        event_type=policy.event_type,
        severity_min=policy.severity_min,
        channels=policy.channels or [],
        cooldown_seconds=policy.cooldown_seconds,
        active=policy.active,
        action_on_critical=policy.action_on_critical.value if policy.action_on_critical else None,
        hard_breach_only=policy.hard_breach_only,
        created_at=policy.created_at,
    )


@router.post(
    "/notifications/push/subscribe",
    response_model=FleetPushSubscriptionOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def subscribe_push_notifications(
    payload: FleetPushSubscriptionIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetPushSubscriptionOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    subscription = fleet_service.upsert_push_subscription(
        db,
        client_id=client_id,
        employee_id=str(principal.user_id) if principal.user_id else None,
        endpoint=payload.endpoint,
        p256dh=payload.p256dh,
        auth=payload.auth,
        user_agent=payload.user_agent,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return FleetPushSubscriptionOut(
        id=str(subscription.id),
        endpoint=subscription.endpoint,
        active=subscription.active,
        created_at=subscription.created_at,
        last_sent_at=subscription.last_sent_at,
    )


@router.post(
    "/notifications/push/unsubscribe",
    response_model=FleetPushSubscriptionOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def unsubscribe_push_notifications(
    payload: FleetPushSubscriptionLookupIn,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetPushSubscriptionOut:
    client_id = _ensure_client_context(principal)
    subscription = fleet_service.disable_push_subscription(
        db,
        client_id=client_id,
        endpoint=payload.endpoint,
        principal=principal,
    )
    db.commit()
    return FleetPushSubscriptionOut(
        id=str(subscription.id),
        endpoint=subscription.endpoint,
        active=subscription.active,
        created_at=subscription.created_at,
        last_sent_at=subscription.last_sent_at,
    )


@router.post(
    "/notifications/push/status",
    response_model=FleetPushSubscriptionOut | None,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def get_push_subscription_status(
    payload: FleetPushSubscriptionLookupIn,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetPushSubscriptionOut | None:
    client_id = _ensure_client_context(principal)
    subscription = fleet_service.get_push_subscription(
        db,
        client_id=client_id,
        endpoint=payload.endpoint,
        principal=principal,
    )
    if not subscription:
        return None
    return FleetPushSubscriptionOut(
        id=str(subscription.id),
        endpoint=subscription.endpoint,
        active=subscription.active,
        created_at=subscription.created_at,
        last_sent_at=subscription.last_sent_at,
    )


@router.post(
    "/notifications/push/test",
    response_model=FleetNotificationTestOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def send_test_push_notification(
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetNotificationTestOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    payload = {
        "client_id": client_id,
        "event_type": FleetNotificationEventType.TEST.value,
        "severity": FleetNotificationSeverity.HIGH.value,
        "summary": {"message": "Test push notification"},
        "channels_override": [FleetNotificationChannelType.PUSH.value],
        "route": "/client/fleet/notifications/alerts",
        "title": "NEFT Test Push",
        "body": "Push notifications are enabled on this device.",
        "url": "/client/fleet/notifications/alerts",
    }
    outbox = enqueue_notification(
        db,
        client_id=client_id,
        event_type=FleetNotificationEventType.TEST,
        severity=FleetNotificationSeverity.HIGH,
        event_ref_type="push_test",
        event_ref_id=str(principal.user_id) if principal.user_id else client_id,
        payload=payload,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    outbox = dispatch_outbox_item(db, outbox_id=str(outbox.id))
    db.commit()
    return FleetNotificationTestOut(outbox_id=str(outbox.id), status=outbox.status.value)


@router.get(
    "/policies",
    response_model=FleetActionPolicyListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value))],
)
def list_action_policies(
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_SPEND_VIEW.value)),
    db: Session = Depends(get_db),
) -> FleetActionPolicyListResponse:
    client_id = _ensure_client_context(principal)
    policies = fleet_service.list_action_policies(db, client_id=client_id, principal=principal)
    return FleetActionPolicyListResponse(
        items=[
            FleetActionPolicyOut(
                id=str(policy.id),
                scope_type=policy.scope_type,
                scope_id=str(policy.scope_id) if policy.scope_id else None,
                trigger_type=policy.trigger_type,
                trigger_severity_min=policy.trigger_severity_min,
                breach_kind=policy.breach_kind,
                action=policy.action,
                cooldown_seconds=policy.cooldown_seconds,
                active=policy.active,
                created_at=policy.created_at,
            )
            for policy in policies
        ]
    )


@router.post(
    "/policies",
    response_model=FleetActionPolicyOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def create_action_policy(
    payload: FleetActionPolicyIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetActionPolicyOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    policy = fleet_service.create_action_policy(
        db,
        client_id=client_id,
        payload=payload,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return FleetActionPolicyOut(
        id=str(policy.id),
        scope_type=policy.scope_type,
        scope_id=str(policy.scope_id) if policy.scope_id else None,
        trigger_type=policy.trigger_type,
        trigger_severity_min=policy.trigger_severity_min,
        breach_kind=policy.breach_kind,
        action=policy.action,
        cooldown_seconds=policy.cooldown_seconds,
        active=policy.active,
        created_at=policy.created_at,
    )


@router.post(
    "/policies/{policy_id}/disable",
    response_model=FleetActionPolicyOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def disable_action_policy(
    policy_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetActionPolicyOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    policy = fleet_service.disable_action_policy(
        db,
        policy_id=policy_id,
        client_id=client_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return FleetActionPolicyOut(
        id=str(policy.id),
        scope_type=policy.scope_type,
        scope_id=str(policy.scope_id) if policy.scope_id else None,
        trigger_type=policy.trigger_type,
        trigger_severity_min=policy.trigger_severity_min,
        breach_kind=policy.breach_kind,
        action=policy.action,
        cooldown_seconds=policy.cooldown_seconds,
        active=policy.active,
        created_at=policy.created_at,
    )


@router.get(
    "/employees",
    response_model=FleetEmployeeListResponse,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def list_employees(
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetEmployeeListResponse:
    client_id = _ensure_client_context(principal)
    employees = fleet_service.list_employees(db, client_id=client_id, principal=principal)
    return FleetEmployeeListResponse(items=[_employee_to_schema(item) for item in employees])


@router.post(
    "/employees/invite",
    response_model=FleetEmployeeOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def invite_employee(
    payload: FleetEmployeeInviteIn,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetEmployeeOut:
    client_id = _ensure_client_context(principal)
    request_id, trace_id = _request_ids(request)
    employee = fleet_service.invite_employee(
        db,
        client_id=client_id,
        email=payload.email,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _employee_to_schema(employee)


@router.post(
    "/employees/{employee_id}/disable",
    response_model=FleetEmployeeOut,
    dependencies=[Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value))],
)
def disable_employee(
    employee_id: str,
    request: Request,
    principal: Principal = Depends(require_permission(Permission.CLIENT_FLEET_EMPLOYEES_MANAGE.value)),
    db: Session = Depends(get_db),
) -> FleetEmployeeOut:
    request_id, trace_id = _request_ids(request)
    employee = fleet_service.disable_employee(
        db,
        employee_id=employee_id,
        principal=principal,
        request_id=request_id,
        trace_id=trace_id,
    )
    db.commit()
    return _employee_to_schema(employee)


__all__ = ["router"]
