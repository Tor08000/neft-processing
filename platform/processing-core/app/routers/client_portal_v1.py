from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
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
)
from app.models.fleet import ClientEmployee, EmployeeStatus
from app.models.card import Card
from app.models.documents import Document, DocumentFile, DocumentFileType, DocumentType
from app.models.subscriptions_v1 import SubscriptionPlan, SubscriptionPlanModule
from app.schemas.client_cards_v1 import (
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
    UserRoleUpdateRequest,
)
from app.schemas.client_portal_v1 import (
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
from app.models.audit_log import AuditVisibility
from app.services.entitlements_service import assert_module_enabled

router = APIRouter(prefix="/client", tags=["client-portal-v1"])

_CONTRACT_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "assets" / "client_onboarding_contract_v1.pdf"
_DOC_TYPE_ALIASES = {
    "CONTRACT": DocumentType.OFFER,
    "INVOICE": DocumentType.INVOICE,
    "ACT": DocumentType.ACT,
    "RECONCILIATION_ACT": DocumentType.RECONCILIATION_ACT,
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


def _is_card_admin(token: dict) -> bool:
    roles = set(_normalize_roles(token))
    return bool(roles.intersection({"CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_FLEET_MANAGER"}))


def _is_user_admin(token: dict) -> bool:
    roles = set(_normalize_roles(token))
    return bool(roles.intersection({"CLIENT_OWNER", "CLIENT_ADMIN"}))


def _is_driver(token: dict) -> bool:
    roles = set(_normalize_roles(token))
    return bool(roles.intersection({"CLIENT_USER", "DRIVER"}))


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
) -> None:
    ctx = request_context_from_request(request, token=token)
    AuditService(db).record(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before=before,
        after=after,
        visibility=AuditVisibility.INTERNAL,
        request_ctx=ctx,
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
