from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
import re
from decimal import Decimal
from typing import Iterable, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from app.api.dependencies.client import client_portal_user
from app.db import get_db
from app.models.account import Account, AccountBalance
from app.models.audit_log import AuditLog, AuditVisibility
from app.models.card import Card
from app.models.client import Client
from app.models.client_actions import (
    DocumentAcknowledgement,
    InvoiceMessage,
    InvoiceMessageSenderType,
    InvoiceThread,
    InvoiceThreadStatus,
    ReconciliationRequest,
    ReconciliationRequestStatus,
)
from app.models.contract_limits import LimitConfig, LimitConfigScope, LimitType, LimitWindow
from app.models.finance import CreditNote, InvoicePayment
from app.models.invoice import Invoice, InvoiceStatus
from app.models.ledger_entry import LedgerDirection, LedgerEntry
from app.models.fuel import FuelStation
from app.models.operation import Operation, RiskResult
from app.repositories.billing_repository import BillingRepository
from app.schemas.client_portal import (
    BalanceItem,
    BalancesResponse,
    CardLimit,
    ClientCard,
    ClientCardsResponse,
    ClientAuditEvent,
    ClientAuditListResponse,
    ClientExportItem,
    ClientExportListResponse,
    ClientInvoiceDetails,
    ClientInvoiceListResponse,
    ClientInvoicePayment,
    ClientInvoiceRefund,
    ClientInvoiceSummary,
    ClientProfile,
    OperationDetails,
    OperationStation,
    OperationSummary,
    OperationsPage,
    StatementResponse,
)
from app.schemas.client_actions import (
    DocumentAcknowledgementResponse,
    InvoiceMessageCreateRequest,
    InvoiceMessageCreateResponse,
    InvoiceMessageOut,
    InvoiceThreadMessagesResponse,
    ReconciliationRequestCreate,
    ReconciliationRequestList,
    ReconciliationRequestOut,
)
from app.schemas.crm import CRMClientOnboardingStatus
from app.schemas.settlement_allocations import SettlementSummaryItem, SettlementSummaryResponse
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.services.document_chain import compute_ack_hash
from app.services.crm import onboarding
from app.services.s3_storage import S3Storage
from app.services.settlement_allocations import list_settlement_summary
from app.services.token_claims import DEFAULT_TENANT_ID, resolve_token_tenant_id, token_email
from app.services.fuel.stations import resolve_station_nav_url

router = APIRouter(prefix="/v1/client", tags=["client-portal"])


_CLIENT_REASON_MAP: dict[str, str] = {
    "AI_RISK_DECLINE_INTERNAL": "Операция отклонена службой безопасности",
    "RISK_DECLINE": "Операция отклонена правилами безопасности",
    "LIMIT_PER_TX": "Превышен лимит на одну транзакцию",
    "DAILY_LIMIT_EXCEEDED": "Превышен дневной лимит договора",
    "CARD_BLOCKED": "Карта заблокирована",
    "SUSPICIOUS_TRANSACTION": "Подозрительная транзакция",
}

_RISK_RESULT_MESSAGES: dict[RiskResult, str] = {
    RiskResult.HIGH: "Операция требует дополнительной проверки",
    RiskResult.BLOCK: "Операция заблокирована правилами безопасности",
    RiskResult.MANUAL_REVIEW: "Операция отправлена на ручную проверку",
}


def _ensure_client_context(token: dict) -> str:
    client_id = token.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Missing client context")
    return str(client_id)


def _ensure_tenant_context(token: dict, *, db: Session | None = None) -> int:
    return resolve_token_tenant_id(
        token,
        db=db,
        client_id=str(token.get("client_id") or "") or None,
        default=DEFAULT_TENANT_ID,
        error_detail="Missing tenant context",
    )


def _ensure_client_action_allowed(token: dict) -> None:
    allowed_roles = {"CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT"}
    roles = token.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    if token.get("role"):
        roles.append(token["role"])
    if not allowed_roles.intersection({str(role) for role in roles}):
        raise HTTPException(status_code=403, detail="forbidden")


def _as_uuid(value: str) -> UUID:
    try:
        return UUID(str(value))
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail="invalid_client") from exc


def _parse_enum_value(raw: str, enum_cls):
    if raw is None:
        return None
    try:
        return enum_cls(raw)
    except ValueError:
        try:
            return enum_cls(raw.split(".")[-1])
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=400, detail="invalid_limit_config") from exc


def _parse_status_values(raw_values: list[str] | None) -> list[InvoiceStatus] | None:
    if not raw_values:
        return None
    parsed: list[InvoiceStatus] = []
    for value in raw_values:
        parsed.append(_parse_enum_value(value, InvoiceStatus))
    return list(dict.fromkeys(parsed))


def _parse_reconciliation_status_values(
    raw_values: list[str] | None,
) -> list[ReconciliationRequestStatus] | None:
    if not raw_values:
        return None
    parsed: list[ReconciliationRequestStatus] = []
    for value in raw_values:
        parsed.append(_parse_enum_value(value, ReconciliationRequestStatus))
    return list(dict.fromkeys(parsed))


@router.get("/onboarding", response_model=CRMClientOnboardingStatus)
def get_client_onboarding_status(
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> CRMClientOnboardingStatus:
    client_id = _ensure_client_context(token)
    ctx = request_context_from_request(request, token=token)
    state, facts = onboarding.recompute(db, client_id=client_id, request_ctx=ctx)
    return CRMClientOnboardingStatus(
        state=state.state,
        state_entered_at=state.state_entered_at,
        is_blocked=state.is_blocked,
        block_reason=state.block_reason,
        evidence=facts.__dict__,
        steps={},
        meta=state.meta,
    )


@router.post("/onboarding/actions/{action}", response_model=CRMClientOnboardingStatus)
def apply_client_onboarding_action(
    request: Request,
    action: onboarding.OnboardingAction,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> CRMClientOnboardingStatus:
    client_id = _ensure_client_context(token)
    if action not in {onboarding.OnboardingAction.REQUEST_LEGAL, onboarding.OnboardingAction.SIGN_CONTRACT}:
        raise HTTPException(status_code=403, detail="forbidden")
    ctx = request_context_from_request(request, token=token)
    state, facts = onboarding.advance(db, client_id=client_id, action=action, request_ctx=ctx)
    return CRMClientOnboardingStatus(
        state=state.state,
        state_entered_at=state.state_entered_at,
        is_blocked=state.is_blocked,
        block_reason=state.block_reason,
        evidence=facts.__dict__,
        steps={},
        meta=state.meta,
    )


def _audit_forbidden_access(
    *,
    token: dict,
    request: Request,
    db: Session,
    entity_type: str,
    entity_id: str,
) -> None:
    AuditService(db).audit(
        event_type="CLIENT_ACCESS_FORBIDDEN",
        entity_type=entity_type,
        entity_id=entity_id,
        action="FORBIDDEN",
        visibility=AuditVisibility.INTERNAL,
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
    db.commit()


def _sanitize_audit_snapshot(snapshot: dict | None) -> dict | None:
    if not snapshot:
        return None
    allowed = {"amount", "status", "currency", "number"}
    return {key: value for key, value in snapshot.items() if key in allowed}


def _sanitize_external_refs(payload: dict | None) -> dict | None:
    if not payload:
        return None
    external_refs = payload.get("external_refs")
    if isinstance(external_refs, dict):
        return {
            "provider": external_refs.get("provider"),
            "external_ref": external_refs.get("external_ref"),
        }
    provider = payload.get("provider")
    external_ref = payload.get("external_ref")
    if provider or external_ref:
        return {"provider": provider, "external_ref": external_ref}
    return None


def _resolve_actor_type(actor: str | None, payload: dict | None) -> str | None:
    if payload and payload.get("actor_type"):
        return payload.get("actor_type")
    if not actor:
        return None
    if actor.lower() in {"system"}:
        return "SYSTEM"
    return "SERVICE"


def _resolve_actor_id(actor: str | None, payload: dict | None) -> str | None:
    if payload and payload.get("actor_id"):
        return payload.get("actor_id")
    return actor


def _infer_entity_type(
    entity_id: str,
    *,
    invoice_id: str,
    payment_ids: set[str],
    refund_ids: set[str],
    payload: dict | None,
) -> str:
    if payload and payload.get("entity_type"):
        return str(payload.get("entity_type"))
    if entity_id == invoice_id:
        return "invoice"
    if entity_id in payment_ids:
        return "payment"
    if entity_id in refund_ids:
        return "refund"
    return "invoice"


def _attach_limits(db: Session, cards: Iterable[Card]) -> list[ClientCard]:
    card_list = list(cards)
    card_ids = [card.id for card in card_list]
    limits = (
        db.query(LimitConfig)
        .filter(LimitConfig.scope == LimitConfigScope.CARD)
        .filter(LimitConfig.subject_ref.in_(card_ids))
        .all()
    )
    limits_map: dict[str, list[CardLimit]] = defaultdict(list)
    for limit in limits:
        limit_type = getattr(limit.limit_type, "value", str(limit.limit_type))
        window = getattr(limit.window, "value", str(limit.window))
        limits_map[limit.subject_ref].append(
            CardLimit(type=limit_type, value=int(limit.value), window=window)
        )

    result: list[ClientCard] = []
    for card in card_list:
        result.append(
            ClientCard(
                id=card.id,
                pan_masked=card.pan_masked,
                status=card.status,
                limits=limits_map.get(card.id, []),
            )
        )
    return result


def _humanize_reason(op: Operation) -> str | None:
    if not op:
        return None

    if op.reason:
        key = str(op.reason).upper()
        return _CLIENT_REASON_MAP.get(key, op.reason)

    risk_result = getattr(op, "risk_result", None)
    if risk_result and isinstance(risk_result, RiskResult):
        return _RISK_RESULT_MESSAGES.get(risk_result)

    return None


def _serialize_station(station: FuelStation) -> OperationStation:
    address_parts = [station.country, station.region, station.city]
    address = ", ".join([str(part).strip() for part in address_parts if part and str(part).strip()]) or None
    return OperationStation(
        id=str(station.id),
        name=station.name,
        address=address,
        lat=station.lat,
        lon=station.lon,
        nav_url=resolve_station_nav_url(station),
    )


def _resolve_operation_station(op: Operation, station_by_id: dict[str, FuelStation], station_by_code: dict[str, FuelStation]) -> OperationStation | None:
    if op.fuel_station_id and op.fuel_station_id in station_by_id:
        return _serialize_station(station_by_id[op.fuel_station_id])

    terminal_id = (op.terminal_id or "").strip()
    if not terminal_id:
        return None

    station = station_by_code.get(terminal_id) or station_by_id.get(terminal_id)
    if station is None:
        return None
    return _serialize_station(station)


def _build_station_maps(db: Session, operations: list[Operation]) -> tuple[dict[str, FuelStation], dict[str, FuelStation]]:
    station_ids = {str(op.fuel_station_id) for op in operations if getattr(op, "fuel_station_id", None)}
    terminal_ids = {(op.terminal_id or "").strip() for op in operations if (op.terminal_id or "").strip()}
    if not station_ids and not terminal_ids:
        return {}, {}

    query = db.query(FuelStation)
    conditions = []
    if station_ids:
        conditions.append(cast(FuelStation.id, String).in_(station_ids))
    if terminal_ids:
        conditions.append(FuelStation.station_code.in_(terminal_ids))
    stations = query.filter(or_(*conditions)).all() if conditions else []

    by_id = {str(station.id): station for station in stations}
    by_code = {str(station.station_code): station for station in stations if station.station_code}
    return by_id, by_code


def _serialize_operation(op: Operation, station_by_id: dict[str, FuelStation], station_by_code: dict[str, FuelStation]) -> OperationSummary:
    return OperationSummary(
        id=op.operation_id,
        created_at=op.created_at,
        status=op.status,
        amount=op.amount,
        currency=op.currency,
        card_id=op.card_id,
        product_type=getattr(op, "product_type", None),
        merchant_id=op.merchant_id,
        terminal_id=op.terminal_id,
        reason=_humanize_reason(op),
        quantity=getattr(op, "quantity", None),
        station=_resolve_operation_station(op, station_by_id, station_by_code),
    )


@router.get("/me", response_model=ClientProfile)
async def client_profile(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientProfile:
    client_id = _ensure_client_context(token)
    client = db.query(Client).filter(Client.id == _as_uuid(client_id)).one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="client_not_found")

    return ClientProfile(
        id=str(client.id),
        name=client.name,
        external_id=client.external_id,
        inn=getattr(client, "inn", None),
        tariff_plan=getattr(client, "tariff_plan", None),
        account_manager=getattr(client, "account_manager", None),
        status=client.status,
    )


@router.get("/cards", response_model=ClientCardsResponse)
async def list_cards(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientCardsResponse:
    client_id = _ensure_client_context(token)
    cards = db.query(Card).filter(Card.client_id == client_id).all()
    return ClientCardsResponse(items=_attach_limits(db, cards))


@router.get("/cards/{card_id}", response_model=ClientCard)
async def card_details(
    card_id: str,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientCard:
    client_id = _ensure_client_context(token)
    card = (
        db.query(Card)
        .filter(Card.id == card_id)
        .filter(Card.client_id == client_id)
        .one_or_none()
    )
    if not card:
        raise HTTPException(status_code=404, detail="card_not_found")

    return _attach_limits(db, [card])[0]


@router.post("/cards/{card_id}/block")
async def block_card(
    card_id: str,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> dict:
    client_id = _ensure_client_context(token)
    card = (
        db.query(Card)
        .filter(Card.id == card_id)
        .filter(Card.client_id == client_id)
        .one_or_none()
    )
    if not card:
        raise HTTPException(status_code=404, detail="card_not_found")

    card.status = "BLOCKED"
    db.commit()
    db.refresh(card)
    return {"card_id": card.id, "status": card.status}


@router.post("/cards/{card_id}/unblock")
async def unblock_card(
    card_id: str,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> dict:
    client_id = _ensure_client_context(token)
    card = (
        db.query(Card)
        .filter(Card.id == card_id)
        .filter(Card.client_id == client_id)
        .one_or_none()
    )
    if not card:
        raise HTTPException(status_code=404, detail="card_not_found")

    card.status = "ACTIVE"
    db.commit()
    db.refresh(card)
    return {"card_id": card.id, "status": card.status}


@router.post("/cards/{card_id}/limits", response_model=ClientCard)
async def update_card_limits(
    card_id: str,
    payload: CardLimit,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientCard:
    client_id = _ensure_client_context(token)
    card = (
        db.query(Card)
        .filter(Card.id == card_id)
        .filter(Card.client_id == client_id)
        .one_or_none()
    )
    if not card:
        raise HTTPException(status_code=404, detail="card_not_found")

    limit_type = _parse_enum_value(payload.type, LimitType)
    window = _parse_enum_value(payload.window, LimitWindow)

    limit = (
        db.query(LimitConfig)
        .filter(LimitConfig.scope == LimitConfigScope.CARD)
        .filter(LimitConfig.subject_ref == card_id)
        .filter(LimitConfig.limit_type == limit_type)
        .one_or_none()
    )
    if limit:
        limit.value = payload.value
        limit.window = window
    else:
        limit = LimitConfig(
            scope=LimitConfigScope.CARD,
            subject_ref=card_id,
            limit_type=limit_type,
            value=payload.value,
            window=window,
            enabled=True,
        )
        db.add(limit)
    db.commit()
    return _attach_limits(db, [card])[0]


@router.get("/operations", response_model=OperationsPage)
async def list_operations(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    card_id: str | None = None,
    status: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> OperationsPage:
    client_id = _ensure_client_context(token)
    query = db.query(Operation).filter(Operation.client_id == client_id)

    if card_id:
        query = query.filter(Operation.card_id == card_id)
    if status:
        query = query.filter(Operation.status == status)
    if date_from:
        query = query.filter(Operation.created_at >= date_from)
    if date_to:
        query = query.filter(Operation.created_at <= date_to)

    total = query.count()
    operations: List[Operation] = (
        query.order_by(Operation.created_at.desc()).offset(offset).limit(limit).all()
    )
    station_by_id, station_by_code = _build_station_maps(db, operations)
    items = [_serialize_operation(op, station_by_id, station_by_code) for op in operations]
    return OperationsPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/operations/{operation_id}", response_model=OperationDetails)
async def operation_details(
    operation_id: str,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> OperationDetails:
    client_id = _ensure_client_context(token)
    op = (
        db.query(Operation)
        .filter(Operation.operation_id == operation_id)
        .filter(Operation.client_id == client_id)
        .one_or_none()
    )
    if not op:
        raise HTTPException(status_code=404, detail="operation_not_found")

    station_by_id, station_by_code = _build_station_maps(db, [op])
    return OperationDetails(**_serialize_operation(op, station_by_id, station_by_code).dict())


@router.get("/invoices", response_model=ClientInvoiceListResponse)
async def list_invoices(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    status: list[str] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("issued_at:desc"),
) -> ClientInvoiceListResponse:
    client_id = _ensure_client_context(token)
    repo = BillingRepository(db)
    issued_from = datetime.combine(date_from, time.min) if date_from else None
    issued_to = datetime.combine(date_to, time.max) if date_to else None

    parsed_statuses = _parse_status_values(status)
    sort_value = sort.strip().lower()
    if sort_value not in {"issued_at:desc", "issued_at:asc", "issued_at desc", "issued_at asc", "-issued_at"}:
        raise HTTPException(status_code=400, detail="invalid_sort")
    sort_desc = sort_value in {"issued_at:desc", "issued_at desc", "-issued_at"}

    invoices, total = repo.list_invoices(
        client_id=client_id,
        issued_from=issued_from,
        issued_to=issued_to,
        status=parsed_statuses,
        exclude_cancelled=True,
        limit=limit,
        offset=offset,
        sort_desc=sort_desc,
    )
    items = [
        ClientInvoiceSummary(
            id=invoice.id,
            number=invoice.number or invoice.external_number or invoice.id,
            issued_at=invoice.issued_at or invoice.created_at,
            status=invoice.status,
            amount_total=Decimal(invoice.total_with_tax or invoice.total_amount or 0),
            amount_paid=Decimal(invoice.amount_paid or 0),
            amount_refunded=Decimal(invoice.amount_refunded or 0),
            amount_due=Decimal(invoice.amount_due or 0),
            currency=invoice.currency,
        )
        for invoice in invoices
    ]
    return ClientInvoiceListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/invoices/{invoice_id}", response_model=ClientInvoiceDetails)
async def get_invoice_details(
    invoice_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientInvoiceDetails:
    client_id = _ensure_client_context(token)
    repo = BillingRepository(db)
    invoice = repo.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    if str(invoice.client_id) != client_id:
        _audit_forbidden_access(
            token=token,
            request=request,
            db=db,
            entity_type="invoice",
            entity_id=str(invoice_id),
        )
        raise HTTPException(status_code=403, detail="forbidden")
    payments = (
        db.query(InvoicePayment)
        .filter(InvoicePayment.invoice_id == invoice_id)
        .order_by(InvoicePayment.created_at.asc())
        .all()
    )
    refunds = (
        db.query(CreditNote)
        .filter(CreditNote.invoice_id == invoice_id)
        .order_by(CreditNote.created_at.asc())
        .all()
    )
    acknowledgement = (
        db.query(DocumentAcknowledgement)
        .filter(DocumentAcknowledgement.client_id == client_id)
        .filter(DocumentAcknowledgement.document_type == "INVOICE_PDF")
        .filter(DocumentAcknowledgement.document_id == invoice_id)
        .one_or_none()
    )

    return ClientInvoiceDetails(
        id=invoice.id,
        number=invoice.number or invoice.external_number or invoice.id,
        issued_at=invoice.issued_at or invoice.created_at,
        status=invoice.status,
        amount_total=Decimal(invoice.total_with_tax or invoice.total_amount or 0),
        amount_paid=Decimal(invoice.amount_paid or 0),
        amount_refunded=Decimal(invoice.amount_refunded or 0),
        amount_due=Decimal(invoice.amount_due or 0),
        currency=invoice.currency,
        pdf_available=bool(invoice.pdf_object_key),
        acknowledged=bool(acknowledgement),
        ack_at=acknowledgement.ack_at if acknowledgement else None,
        payments=[
            ClientInvoicePayment(
                id=str(payment.id),
                amount=Decimal(payment.amount or 0),
                status=payment.status.value if payment.status else "POSTED",
                provider=payment.provider,
                external_ref=payment.external_ref,
                created_at=payment.created_at,
            )
            for payment in payments
        ],
        refunds=[
            ClientInvoiceRefund(
                id=str(refund.id),
                amount=Decimal(refund.amount or 0),
                status=refund.status.value if refund.status else "POSTED",
                provider=refund.provider,
                external_ref=refund.external_ref,
                created_at=refund.created_at,
                reason=refund.reason,
            )
            for refund in refunds
        ],
    )


@router.get("/settlements", response_model=SettlementSummaryResponse)
def list_client_settlements(
    date_from: date = Query(...),
    date_to: date = Query(...),
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> SettlementSummaryResponse:
    client_id = _ensure_client_context(token)
    rows = list_settlement_summary(db, date_from=date_from, date_to=date_to, client_id=client_id)
    items = [
        SettlementSummaryItem(
            settlement_period_id=row.settlement_period_id,
            period_start=row.period_start,
            period_end=row.period_end,
            currency=row.currency,
            total_payments=row.total_payments,
            total_credits=row.total_credits,
            total_refunds=row.total_refunds,
            total_net=row.total_payments - row.total_credits - row.total_refunds,
            allocations_count=row.allocations_count,
        )
        for row in rows
    ]
    return SettlementSummaryResponse(items=items, total=len(items))


@router.get("/invoices/{invoice_id}/audit", response_model=ClientAuditListResponse)
async def list_invoice_audit(
    invoice_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    event_type: list[str] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ClientAuditListResponse:
    client_id = _ensure_client_context(token)
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    if str(invoice.client_id) != client_id:
        _audit_forbidden_access(
            token=token,
            request=request,
            db=db,
            entity_type="invoice",
            entity_id=str(invoice_id),
        )
        raise HTTPException(status_code=403, detail="forbidden")

    payment_ids = {
        str(payment.id)
        for payment in db.query(InvoicePayment.id).filter(InvoicePayment.invoice_id == invoice_id).all()
    }
    refund_ids = {
        str(refund.id)
        for refund in db.query(CreditNote.id).filter(CreditNote.invoice_id == invoice_id).all()
    }
    entity_ids = {invoice_id, *payment_ids, *refund_ids}

    query = db.query(AuditLog).filter(AuditLog.entity_id.in_(entity_ids))
    query = query.filter(AuditLog.visibility == AuditVisibility.PUBLIC)
    if date_from:
        query = query.filter(AuditLog.ts >= date_from)
    if date_to:
        query = query.filter(AuditLog.ts <= date_to)
    if event_type:
        query = query.filter(AuditLog.event_type.in_(event_type))

    total = query.count()
    logs = query.order_by(AuditLog.ts.desc(), AuditLog.id.desc()).offset(offset).limit(limit).all()

    items = []
    for log in logs:
        entity_id = str(log.entity_id or "")
        items.append(
            ClientAuditEvent(
                id=str(log.id),
                ts=log.ts,
                event_type=log.event_type or "",
                entity_type=log.entity_type,
                entity_id=entity_id,
                action=log.action,
                visibility=log.visibility.value if log.visibility else None,
                actor_type=log.actor_type.value if log.actor_type else None,
                actor_id=log.actor_id,
                external_refs=_sanitize_external_refs(log.external_refs),
                before=_sanitize_audit_snapshot(log.before),
                after=_sanitize_audit_snapshot(log.after),
                hash=log.hash,
                prev_hash=log.prev_hash,
            )
        )
    return ClientAuditListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/audit/search", response_model=ClientAuditListResponse)
async def search_audit_by_external_ref(
    request: Request,
    external_ref: str = Query(..., min_length=1),
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    provider: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    event_type: list[str] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ClientAuditListResponse:
    client_id = _ensure_client_context(token)
    invoice_ids = [row.id for row in db.query(Invoice.id).filter(Invoice.client_id == client_id).all()]
    payment_ids = [
        str(row.id)
        for row in db.query(InvoicePayment.id)
        .join(Invoice, Invoice.id == InvoicePayment.invoice_id)
        .filter(Invoice.client_id == client_id)
        .all()
    ]
    refund_ids = [
        str(row.id)
        for row in db.query(CreditNote.id)
        .join(Invoice, Invoice.id == CreditNote.invoice_id)
        .filter(Invoice.client_id == client_id)
        .all()
    ]
    entity_ids = {*(invoice_ids or []), *payment_ids, *refund_ids}
    if not entity_ids:
        return ClientAuditListResponse(items=[], total=0, limit=limit, offset=offset)

    query = db.query(AuditLog).filter(AuditLog.entity_id.in_(entity_ids))
    query = query.filter(AuditLog.visibility == AuditVisibility.PUBLIC)
    if date_from:
        query = query.filter(AuditLog.ts >= date_from)
    if date_to:
        query = query.filter(AuditLog.ts <= date_to)
    if event_type:
        query = query.filter(AuditLog.event_type.in_(event_type))

    external_refs = cast(AuditLog.external_refs, String)
    query = query.filter(external_refs.ilike(f"%{external_ref}%"))
    if provider:
        query = query.filter(external_refs.ilike(f"%{provider}%"))

    total = query.count()
    logs = query.order_by(AuditLog.ts.desc(), AuditLog.id.desc()).offset(offset).limit(limit).all()
    items = []
    for log in logs:
        entity_id = str(log.entity_id or "")
        items.append(
            ClientAuditEvent(
                id=str(log.id),
                ts=log.ts,
                event_type=log.event_type or "",
                entity_type=log.entity_type,
                entity_id=entity_id,
                action=log.action,
                visibility=log.visibility.value if log.visibility else None,
                actor_type=log.actor_type.value if log.actor_type else None,
                actor_id=log.actor_id,
                external_refs=_sanitize_external_refs(log.external_refs),
                before=_sanitize_audit_snapshot(log.before),
                after=_sanitize_audit_snapshot(log.after),
                hash=log.hash,
                prev_hash=log.prev_hash,
            )
        )
    return ClientAuditListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/reconciliation-requests", response_model=ReconciliationRequestOut, status_code=201)
async def create_reconciliation_request(
    request: Request,
    payload: ReconciliationRequestCreate,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ReconciliationRequestOut:
    _ensure_client_action_allowed(token)
    client_id = _ensure_client_context(token)
    tenant_id = _ensure_tenant_context(token, db=db)

    active_statuses = [
        ReconciliationRequestStatus.REQUESTED,
        ReconciliationRequestStatus.IN_PROGRESS,
        ReconciliationRequestStatus.GENERATED,
        ReconciliationRequestStatus.SENT,
    ]
    existing = (
        db.query(ReconciliationRequest)
        .filter(ReconciliationRequest.client_id == client_id)
        .filter(ReconciliationRequest.date_from == payload.date_from)
        .filter(ReconciliationRequest.date_to == payload.date_to)
        .filter(ReconciliationRequest.status.in_(active_statuses))
        .order_by(ReconciliationRequest.created_at.desc())
        .first()
    )
    if existing:
        return ReconciliationRequestOut.model_validate(existing)

    new_request = ReconciliationRequest(
        tenant_id=tenant_id,
        client_id=client_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
        note_client=payload.note,
        requested_by_user_id=token.get("user_id") or token.get("sub"),
        requested_by_email=token.get("email"),
        status=ReconciliationRequestStatus.REQUESTED,
    )
    db.add(new_request)
    db.flush()

    (
        db.query(Invoice)
        .filter(Invoice.client_id == client_id)
        .filter(Invoice.period_from >= payload.date_from)
        .filter(Invoice.period_to <= payload.date_to)
        .filter(Invoice.reconciliation_request_id.is_(None))
        .update({"reconciliation_request_id": new_request.id}, synchronize_session=False)
    )
    db.commit()
    db.refresh(new_request)

    AuditService(db).audit(
        event_type="RECONCILIATION_REQUEST_CREATED",
        entity_type="reconciliation_request",
        entity_id=str(new_request.id),
        action="CREATE",
        visibility=AuditVisibility.PUBLIC,
        after={
            "status": new_request.status.value,
            "date_from": new_request.date_from,
            "date_to": new_request.date_to,
        },
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
    db.commit()

    return ReconciliationRequestOut.model_validate(new_request)


@router.get("/reconciliation-requests", response_model=ReconciliationRequestList)
async def list_reconciliation_requests(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    status: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ReconciliationRequestList:
    client_id = _ensure_client_context(token)
    parsed_statuses = _parse_reconciliation_status_values(status)

    query = db.query(ReconciliationRequest).filter(ReconciliationRequest.client_id == client_id)
    if parsed_statuses:
        query = query.filter(ReconciliationRequest.status.in_(parsed_statuses))
    if date_from:
        query = query.filter(ReconciliationRequest.date_from >= date_from)
    if date_to:
        query = query.filter(ReconciliationRequest.date_to <= date_to)

    total = query.count()
    items = (
        query.order_by(ReconciliationRequest.created_at.desc(), ReconciliationRequest.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return ReconciliationRequestList(
        items=[ReconciliationRequestOut.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/reconciliation-requests/{request_id}", response_model=ReconciliationRequestOut)
async def get_reconciliation_request(
    request_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ReconciliationRequestOut:
    client_id = _ensure_client_context(token)
    request_item = db.query(ReconciliationRequest).filter(ReconciliationRequest.id == request_id).one_or_none()
    if request_item is None:
        raise HTTPException(status_code=404, detail="reconciliation_request_not_found")
    if str(request_item.client_id) != client_id:
        _audit_forbidden_access(
            token=token,
            request=request,
            db=db,
            entity_type="reconciliation_request",
            entity_id=str(request_id),
        )
        raise HTTPException(status_code=403, detail="forbidden")
    return ReconciliationRequestOut.model_validate(request_item)


@router.get("/reconciliation-requests/{request_id}/download")
async def download_reconciliation_request(
    request_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
):
    client_id = _ensure_client_context(token)
    request_item = db.query(ReconciliationRequest).filter(ReconciliationRequest.id == request_id).one_or_none()
    if request_item is None:
        raise HTTPException(status_code=404, detail="reconciliation_request_not_found")
    if str(request_item.client_id) != client_id:
        _audit_forbidden_access(
            token=token,
            request=request,
            db=db,
            entity_type="reconciliation_request",
            entity_id=str(request_id),
        )
        raise HTTPException(status_code=403, detail="forbidden")
    if not request_item.result_object_key:
        raise HTTPException(status_code=404, detail="reconciliation_result_not_found")

    storage = S3Storage(bucket=request_item.result_bucket)
    result_bytes = storage.get_bytes(request_item.result_object_key)
    if not result_bytes:
        raise HTTPException(status_code=404, detail="reconciliation_result_not_found")

    filename = f"reconciliation_{request_item.date_from}_{request_item.date_to}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=result_bytes, media_type="application/pdf", headers=headers)


@router.post("/reconciliation-requests/{request_id}/ack", response_model=ReconciliationRequestOut)
async def acknowledge_reconciliation_request(
    request_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ReconciliationRequestOut:
    _ensure_client_action_allowed(token)
    client_id = _ensure_client_context(token)
    request_item = db.query(ReconciliationRequest).filter(ReconciliationRequest.id == request_id).one_or_none()
    if request_item is None:
        raise HTTPException(status_code=404, detail="reconciliation_request_not_found")
    if str(request_item.client_id) != client_id:
        _audit_forbidden_access(
            token=token,
            request=request,
            db=db,
            entity_type="reconciliation_request",
            entity_id=str(request_id),
        )
        raise HTTPException(status_code=403, detail="forbidden")

    if request_item.status == ReconciliationRequestStatus.ACKNOWLEDGED:
        return ReconciliationRequestOut.model_validate(request_item)

    request_item.status = ReconciliationRequestStatus.ACKNOWLEDGED
    request_item.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(request_item)

    AuditService(db).audit(
        event_type="RECONCILIATION_ACKNOWLEDGED",
        entity_type="reconciliation_request",
        entity_id=str(request_item.id),
        action="UPDATE",
        visibility=AuditVisibility.PUBLIC,
        after={"status": request_item.status.value, "acknowledged_at": request_item.acknowledged_at},
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
    db.commit()

    return ReconciliationRequestOut.model_validate(request_item)


@router.post(
    "/documents/{document_type}/{document_id}/ack",
    response_model=DocumentAcknowledgementResponse,
    status_code=201,
)
async def acknowledge_document(
    document_type: str,
    document_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> DocumentAcknowledgementResponse:
    _ensure_client_action_allowed(token)
    client_id = _ensure_client_context(token)
    tenant_id = _ensure_tenant_context(token, db=db)

    invoice = None
    reconciliation_request = None
    if document_type == "INVOICE_PDF":
        invoice = db.query(Invoice).filter(Invoice.id == document_id).one_or_none()
        if invoice is None:
            raise HTTPException(status_code=404, detail="invoice_not_found")
        if str(invoice.client_id) != client_id:
            _audit_forbidden_access(
                token=token,
                request=request,
                db=db,
                entity_type="invoice",
                entity_id=str(document_id),
            )
            raise HTTPException(status_code=403, detail="forbidden")
    elif document_type == "ACT_RECONCILIATION":
        reconciliation_request = (
            db.query(ReconciliationRequest).filter(ReconciliationRequest.id == document_id).one_or_none()
        )
        if reconciliation_request is None:
            raise HTTPException(status_code=404, detail="reconciliation_request_not_found")
        if str(reconciliation_request.client_id) != client_id:
            _audit_forbidden_access(
                token=token,
                request=request,
                db=db,
                entity_type="reconciliation_request",
                entity_id=str(document_id),
            )
            raise HTTPException(status_code=403, detail="forbidden")
    else:
        raise HTTPException(status_code=400, detail="unsupported_document_type")

    request_ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
    document_object_key = None
    document_hash = None
    if invoice:
        document_object_key = invoice.pdf_object_key
        document_hash = invoice.pdf_hash
    if reconciliation_request:
        document_object_key = reconciliation_request.result_object_key
        document_hash = reconciliation_request.result_hash_sha256
    if not document_hash:
        AuditService(db).audit(
            event_type="DOCUMENT_IMMUTABILITY_VIOLATION",
            entity_type="document",
            entity_id=document_id,
            action="UPDATE",
            visibility=AuditVisibility.PUBLIC,
            after={"reason": "document_hash_missing", "document_type": document_type},
            request_ctx=request_ctx,
        )
        db.commit()
        raise HTTPException(status_code=409, detail="document_hash_missing")

    existing = (
        db.query(DocumentAcknowledgement)
        .filter(DocumentAcknowledgement.client_id == client_id)
        .filter(DocumentAcknowledgement.document_type == document_type)
        .filter(DocumentAcknowledgement.document_id == document_id)
        .one_or_none()
    )
    if existing:
        if existing.document_hash != document_hash:
            AuditService(db).audit(
                event_type="DOCUMENT_IMMUTABILITY_VIOLATION",
                entity_type="document",
                entity_id=document_id,
                action="UPDATE",
                visibility=AuditVisibility.PUBLIC,
                after={
                    "reason": "ack_hash_mismatch",
                    "document_type": document_type,
                    "ack_hash": existing.document_hash,
                    "current_hash": document_hash,
                },
                request_ctx=request_ctx,
            )
            db.commit()
            raise HTTPException(status_code=409, detail="ack_hash_mismatch")
        return DocumentAcknowledgementResponse(
            acknowledged=True,
            ack_at=existing.ack_at,
            document_type=existing.document_type,
            document_object_key=existing.document_object_key,
            document_hash=existing.document_hash,
        )
    ack_by_user_id = token.get("user_id") or token.get("sub")
    ack_by_email = token_email(token)
    if not ack_by_user_id or not ack_by_email:
        AuditService(db).audit(
            event_type="DOCUMENT_IMMUTABILITY_VIOLATION",
            entity_type="document",
            entity_id=document_id,
            action="UPDATE",
            visibility=AuditVisibility.PUBLIC,
            after={"reason": "ack_actor_missing", "document_type": document_type},
            request_ctx=request_ctx,
        )
        db.commit()
        raise HTTPException(status_code=409, detail="ack_actor_missing")

    acknowledgement = DocumentAcknowledgement(
        tenant_id=tenant_id,
        client_id=client_id,
        document_type=document_type,
        document_id=document_id,
        document_object_key=document_object_key,
        document_hash=document_hash,
        ack_by_user_id=ack_by_user_id,
        ack_by_email=ack_by_email,
        ack_ip=request_ctx.ip if request_ctx else None,
        ack_user_agent=request_ctx.user_agent if request_ctx else None,
        ack_method="UI",
    )
    db.add(acknowledgement)
    db.commit()
    db.refresh(acknowledgement)

    ack_by = acknowledgement.ack_by_user_id or acknowledgement.ack_by_email or ""
    ack_hash = compute_ack_hash(acknowledgement.document_hash, acknowledgement.ack_at, ack_by)
    AuditService(db).audit(
        event_type="DOCUMENT_ACKNOWLEDGED",
        entity_type="document",
        entity_id=document_id,
        action="CREATE",
        visibility=AuditVisibility.PUBLIC,
        after={
            "document_type": document_type,
            "ack_at": acknowledgement.ack_at,
            "document_hash": acknowledgement.document_hash,
            "ack_hash": ack_hash,
        },
        request_ctx=request_ctx,
    )
    db.commit()

    return DocumentAcknowledgementResponse(
        acknowledged=True,
        ack_at=acknowledgement.ack_at,
        document_type=document_type,
        document_object_key=acknowledgement.document_object_key,
        document_hash=acknowledgement.document_hash,
    )


@router.post("/invoices/{invoice_id}/messages", response_model=InvoiceMessageCreateResponse, status_code=201)
async def create_invoice_message(
    invoice_id: str,
    request: Request,
    payload: InvoiceMessageCreateRequest,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> InvoiceMessageCreateResponse:
    _ensure_client_action_allowed(token)
    client_id = _ensure_client_context(token)
    _ensure_tenant_context(token, db=db)

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    if str(invoice.client_id) != client_id:
        _audit_forbidden_access(
            token=token,
            request=request,
            db=db,
            entity_type="invoice",
            entity_id=str(invoice_id),
        )
        raise HTTPException(status_code=403, detail="forbidden")

    thread = db.query(InvoiceThread).filter(InvoiceThread.invoice_id == invoice_id).one_or_none()
    if thread and str(thread.client_id) != client_id:
        _audit_forbidden_access(
            token=token,
            request=request,
            db=db,
            entity_type="invoice_thread",
            entity_id=str(thread.id),
        )
        raise HTTPException(status_code=403, detail="forbidden")
    if thread is None:
        thread = InvoiceThread(
            invoice_id=invoice_id,
            client_id=client_id,
            status=InvoiceThreadStatus.WAITING_SUPPORT,
        )
        db.add(thread)
        db.flush()
    elif thread.status == InvoiceThreadStatus.CLOSED:
        raise HTTPException(status_code=409, detail="thread_closed")
    else:
        thread.status = InvoiceThreadStatus.WAITING_SUPPORT

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=1)
    recent_count = (
        db.query(InvoiceMessage)
        .filter(InvoiceMessage.thread_id == thread.id)
        .filter(InvoiceMessage.sender_type == InvoiceMessageSenderType.CLIENT)
        .filter(InvoiceMessage.created_at >= window_start)
        .count()
    )
    if recent_count >= 10:
        raise HTTPException(status_code=429, detail="message_rate_limited")

    clean_message = re.sub(r"<[^>]*>", "", payload.message or "").strip()
    if not clean_message:
        raise HTTPException(status_code=422, detail="message_empty")

    message = InvoiceMessage(
        thread_id=thread.id,
        sender_type=InvoiceMessageSenderType.CLIENT,
        sender_user_id=token.get("user_id") or token.get("sub"),
        sender_email=token.get("email"),
        message=clean_message,
    )
    thread.last_message_at = now
    db.add(message)
    db.commit()
    db.refresh(message)

    AuditService(db).audit(
        event_type="INVOICE_MESSAGE_CREATED",
        entity_type="invoice",
        entity_id=invoice_id,
        action="CREATE",
        visibility=AuditVisibility.PUBLIC,
        after={
            "thread_id": str(thread.id),
            "message_id": str(message.id),
            "sender_type": message.sender_type.value,
        },
        request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
    )
    db.commit()

    return InvoiceMessageCreateResponse(
        thread_id=str(thread.id),
        message_id=str(message.id),
        status=thread.status.value,
    )


@router.get("/invoices/{invoice_id}/messages", response_model=InvoiceThreadMessagesResponse)
async def list_invoice_messages(
    invoice_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> InvoiceThreadMessagesResponse:
    client_id = _ensure_client_context(token)
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    if str(invoice.client_id) != client_id:
        _audit_forbidden_access(
            token=token,
            request=request,
            db=db,
            entity_type="invoice",
            entity_id=str(invoice_id),
        )
        raise HTTPException(status_code=403, detail="forbidden")

    thread = db.query(InvoiceThread).filter(InvoiceThread.invoice_id == invoice_id).one_or_none()
    if thread and str(thread.client_id) != client_id:
        _audit_forbidden_access(
            token=token,
            request=request,
            db=db,
            entity_type="invoice_thread",
            entity_id=str(thread.id),
        )
        raise HTTPException(status_code=403, detail="forbidden")
    if thread is None:
        return InvoiceThreadMessagesResponse(items=[], total=0, limit=limit, offset=offset)

    query = db.query(InvoiceMessage).filter(InvoiceMessage.thread_id == thread.id)
    total = query.count()
    messages = query.order_by(InvoiceMessage.created_at.asc()).offset(offset).limit(limit).all()

    return InvoiceThreadMessagesResponse(
        thread_id=str(thread.id),
        status=thread.status.value,
        created_at=thread.created_at,
        closed_at=thread.closed_at,
        last_message_at=thread.last_message_at,
        items=[
            InvoiceMessageOut(
                id=str(item.id),
                sender_type=item.sender_type.value,
                sender_user_id=item.sender_user_id,
                sender_email=item.sender_email,
                message=item.message,
                created_at=item.created_at,
            )
            for item in messages
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: str,
    request: Request,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
):
    client_id = _ensure_client_context(token)
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    if str(invoice.client_id) != client_id:
        _audit_forbidden_access(
            token=token,
            request=request,
            db=db,
            entity_type="invoice",
            entity_id=str(invoice_id),
        )
        raise HTTPException(status_code=403, detail="forbidden")
    if not invoice.pdf_object_key:
        raise HTTPException(status_code=404, detail="pdf_not_found")

    storage = S3Storage()
    pdf_bytes = storage.get_bytes(invoice.pdf_object_key)
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="pdf_not_found")

    filename = f"{invoice.number or invoice.external_number or invoice.id}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.get("/exports", response_model=ClientExportListResponse)
async def list_exports(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientExportListResponse:
    client_id = _ensure_client_context(token)
    invoices = (
        db.query(Invoice)
        .filter(Invoice.client_id == client_id)
        .filter(Invoice.pdf_object_key.isnot(None))
        .order_by(Invoice.issued_at.desc().nullslast(), Invoice.created_at.desc())
        .all()
    )
    items = [
        ClientExportItem(
            type="INVOICE_PDF",
            title=f"Счет {invoice.number or invoice.external_number or invoice.id}",
            created_at=invoice.issued_at or invoice.created_at,
            download_url=f"/api/v1/client/invoices/{invoice.id}/pdf",
        )
        for invoice in invoices
    ]
    return ClientExportListResponse(items=items)


@router.get("/balances", response_model=BalancesResponse)
async def list_balances(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> BalancesResponse:
    client_id = _ensure_client_context(token)
    accounts: List[Account] = db.query(Account).filter(Account.client_id == client_id).all()
    items: list[BalanceItem] = []
    for account in accounts:
        balance: AccountBalance | None = (
            db.query(AccountBalance)
            .filter(AccountBalance.account_id == account.id)
            .one_or_none()
        )
        current = Decimal(balance.current_balance or 0) if balance else Decimal(0)
        available = Decimal(balance.available_balance or 0) if balance else Decimal(0)
        items.append(
            BalanceItem(
                currency=account.currency,
                current=current,
                available=available,
            )
        )
    return BalancesResponse(items=items)


@router.get("/statements", response_model=List[StatementResponse])
async def statements(
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
) -> List[StatementResponse]:
    client_id = _ensure_client_context(token)
    accounts: List[Account] = db.query(Account).filter(Account.client_id == client_id).all()
    account_ids = [account.id for account in accounts]
    if not account_ids:
        return []

    query = db.query(LedgerEntry).filter(LedgerEntry.account_id.in_(account_ids))
    if date_from:
        query = query.filter(LedgerEntry.posted_at >= date_from)
    if date_to:
        query = query.filter(LedgerEntry.posted_at <= date_to)

    period_entries = query.all()

    # Compute balances per currency
    def _calc_balance(entries: Iterable[LedgerEntry]) -> dict[str, Decimal]:
        balances: dict[str, Decimal] = defaultdict(Decimal)
        for entry in entries:
            amount = Decimal(entry.amount)
            if entry.direction == LedgerDirection.CREDIT:
                balances[entry.currency] += amount
            else:
                balances[entry.currency] -= amount
        return balances

    historical_query = db.query(LedgerEntry).filter(LedgerEntry.account_id.in_(account_ids))
    if date_from:
        historical_query = historical_query.filter(LedgerEntry.posted_at < date_from)
    historical_entries = historical_query.all()

    start_balances = _calc_balance(historical_entries)
    delta_balances = _calc_balance(period_entries)

    statements_response: list[StatementResponse] = []
    currencies = set(list(start_balances.keys()) + [e.currency for e in period_entries])
    for currency in currencies:
        start = start_balances.get(currency, Decimal(0))
        credits = sum(
            Decimal(entry.amount)
            for entry in period_entries
            if entry.currency == currency and entry.direction == LedgerDirection.CREDIT
        )
        debits = sum(
            Decimal(entry.amount)
            for entry in period_entries
            if entry.currency == currency and entry.direction == LedgerDirection.DEBIT
        )
        end_balance = start + delta_balances.get(currency, Decimal(0))
        statements_response.append(
            StatementResponse(
                currency=currency,
                start_balance=start,
                end_balance=end_balance,
                credits=credits,
                debits=debits,
            )
        )

    return statements_response


__all__ = ["router"]
