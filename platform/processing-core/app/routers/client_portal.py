from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time
from decimal import Decimal
from typing import Iterable, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import String, cast
from sqlalchemy.orm import Session

from app.api.dependencies.client import client_portal_user
from app.db import get_db
from app.models.account import Account, AccountBalance
from app.models.audit_log import AuditLog
from app.models.card import Card
from app.models.client import Client
from app.models.contract_limits import LimitConfig, LimitConfigScope, LimitType, LimitWindow
from app.models.finance import CreditNote, InvoicePayment
from app.models.invoice import Invoice, InvoiceStatus
from app.models.ledger_entry import LedgerDirection, LedgerEntry
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
    OperationSummary,
    OperationsPage,
    StatementResponse,
)
from app.services.s3_storage import S3Storage

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


def _serialize_operation(op: Operation) -> OperationSummary:
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
    items = [_serialize_operation(op) for op in operations]
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

    return OperationDetails(**_serialize_operation(op).dict())


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
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
) -> ClientInvoiceDetails:
    client_id = _ensure_client_context(token)
    repo = BillingRepository(db)
    invoice = repo.get_invoice(invoice_id)
    if invoice is None or str(invoice.client_id) != client_id:
        raise HTTPException(status_code=404, detail="invoice_not_found")
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


@router.get("/invoices/{invoice_id}/audit", response_model=ClientAuditListResponse)
async def list_invoice_audit(
    invoice_id: str,
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
    if invoice is None or str(invoice.client_id) != client_id:
        raise HTTPException(status_code=404, detail="invoice_not_found")

    payment_ids = {
        str(payment.id)
        for payment in db.query(InvoicePayment.id).filter(InvoicePayment.invoice_id == invoice_id).all()
    }
    refund_ids = {
        str(refund.id)
        for refund in db.query(CreditNote.id).filter(CreditNote.invoice_id == invoice_id).all()
    }
    entity_ids = {invoice_id, *payment_ids, *refund_ids}

    query = db.query(AuditLog).filter(AuditLog.target.in_(entity_ids))
    if date_from:
        query = query.filter(AuditLog.ts >= date_from)
    if date_to:
        query = query.filter(AuditLog.ts <= date_to)
    if event_type:
        query = query.filter(AuditLog.action.in_(event_type))

    total = query.count()
    logs = query.order_by(AuditLog.ts.desc(), AuditLog.id.desc()).offset(offset).limit(limit).all()

    items = []
    for log in logs:
        payload = log.payload if isinstance(log.payload, dict) else {}
        entity_id = str(log.target or "")
        items.append(
            ClientAuditEvent(
                id=str(log.id),
                ts=log.ts,
                event_type=log.action or "",
                entity_type=_infer_entity_type(
                    entity_id,
                    invoice_id=invoice_id,
                    payment_ids=payment_ids,
                    refund_ids=refund_ids,
                    payload=payload,
                ),
                entity_id=entity_id,
                action=payload.get("action") or log.action,
                actor_type=_resolve_actor_type(log.actor, payload),
                actor_id=_resolve_actor_id(log.actor, payload),
                external_refs=_sanitize_external_refs(payload),
                before=_sanitize_audit_snapshot(payload.get("before") if payload else None),
                after=_sanitize_audit_snapshot(payload.get("after") if payload else None),
                hash=log.hash,
                prev_hash=payload.get("prev_hash") if payload else None,
            )
        )
    return ClientAuditListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/audit/search", response_model=ClientAuditListResponse)
async def search_audit_by_external_ref(
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

    query = db.query(AuditLog).filter(AuditLog.target.in_(entity_ids))
    if date_from:
        query = query.filter(AuditLog.ts >= date_from)
    if date_to:
        query = query.filter(AuditLog.ts <= date_to)
    if event_type:
        query = query.filter(AuditLog.action.in_(event_type))

    payload_text = cast(AuditLog.payload, String)
    query = query.filter(payload_text.ilike(f"%{external_ref}%"))
    if provider:
        query = query.filter(payload_text.ilike(f"%{provider}%"))

    total = query.count()
    logs = query.order_by(AuditLog.ts.desc(), AuditLog.id.desc()).offset(offset).limit(limit).all()
    items = []
    for log in logs:
        payload = log.payload if isinstance(log.payload, dict) else {}
        entity_id = str(log.target or "")
        items.append(
            ClientAuditEvent(
                id=str(log.id),
                ts=log.ts,
                event_type=log.action or "",
                entity_type=_infer_entity_type(
                    entity_id,
                    invoice_id=entity_id if entity_id in invoice_ids else "",
                    payment_ids=set(payment_ids),
                    refund_ids=set(refund_ids),
                    payload=payload,
                ),
                entity_id=entity_id,
                action=payload.get("action") or log.action,
                actor_type=_resolve_actor_type(log.actor, payload),
                actor_id=_resolve_actor_id(log.actor, payload),
                external_refs=_sanitize_external_refs(payload),
                before=_sanitize_audit_snapshot(payload.get("before") if payload else None),
                after=_sanitize_audit_snapshot(payload.get("after") if payload else None),
                hash=log.hash,
                prev_hash=payload.get("prev_hash") if payload else None,
            )
        )
    return ClientAuditListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: str,
    token: dict = Depends(client_portal_user),
    db: Session = Depends(get_db),
):
    client_id = _ensure_client_context(token)
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice_not_found")
    if str(invoice.client_id) != client_id:
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
