from __future__ import annotations

import csv
from datetime import date, datetime, time, timezone
from hashlib import sha256
from io import StringIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import String, and_, cast, or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.client import Client
from app.models.client_onboarding import ClientOnboarding, ClientOnboardingContract
from app.models.client_portal import (
    CardAccess,
    CardAccessScope,
    CardLimit,
    ClientOperation,
    ClientUserRole,
    LimitTemplate,
)
from app.models.fleet import ClientEmployee, EmployeeStatus, FleetDriver
from app.models.card import Card
from app.models.documents import Document, DocumentFile, DocumentFileType, DocumentStatus, DocumentType
from app.models.fuel import FuelCard, FuelLimit, FuelLimitPeriod, FuelLimitScopeType, FuelLimitType
from app.models.operation import Operation
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
    ClientSubscriptionOut,
    ClientSubscriptionSelectRequest,
    ClientUserInviteRequest,
    ClientUserSummary,
    ClientUsersResponse,
    ContractInfo,
    ContractSignRequest,
)
from app.schemas.subscriptions import SubscriptionPlanOut
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
from app.services.entitlements_service import assert_module_enabled

router = APIRouter(prefix="/client", tags=["client-portal-v1"])

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


def _is_card_admin(token: dict) -> bool:
    roles = set(_normalize_roles(token))
    return bool(roles.intersection({"CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_FLEET_MANAGER"}))


def _is_user_admin(token: dict) -> bool:
    roles = set(_normalize_roles(token))
    return bool(roles.intersection({"CLIENT_OWNER", "CLIENT_ADMIN"}))


def _is_driver(token: dict) -> bool:
    roles = set(_normalize_roles(token))
    return bool(roles.intersection({"CLIENT_USER", "DRIVER"}))


def _ensure_report_access(token: dict, allowed_roles: set[str]) -> None:
    roles = set(_normalize_roles(token))
    if not roles.intersection(allowed_roles):
        raise HTTPException(status_code=403, detail="forbidden")


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
    return _csv_response(
        "documents_export.csv",
        ["document_id", "type", "number", "date", "status", "amount", "currency", "file_name"],
        rows,
    )


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
