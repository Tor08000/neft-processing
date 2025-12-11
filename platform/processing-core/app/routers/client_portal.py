from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Iterable, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies.client import client_portal_user
from app.db import get_db
from app.models.account import Account, AccountBalance
from app.models.card import Card
from app.models.client import Client
from app.models.contract_limits import LimitConfig, LimitScope, LimitType, LimitWindow
from app.models.ledger_entry import LedgerDirection, LedgerEntry
from app.models.operation import Operation, RiskResult
from app.schemas.client_portal import (
    BalanceItem,
    BalancesResponse,
    CardLimit,
    ClientCard,
    ClientCardsResponse,
    ClientProfile,
    OperationDetails,
    OperationSummary,
    OperationsPage,
    StatementResponse,
)

router = APIRouter(prefix="/api/v1/client", tags=["client-portal"])


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


def _attach_limits(db: Session, cards: Iterable[Card]) -> list[ClientCard]:
    card_list = list(cards)
    card_ids = [card.id for card in card_list]
    limits = (
        db.query(LimitConfig)
        .filter(LimitConfig.scope == LimitScope.CARD)
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
        .filter(LimitConfig.scope == LimitScope.CARD)
        .filter(LimitConfig.subject_ref == card_id)
        .filter(LimitConfig.limit_type == limit_type)
        .one_or_none()
    )
    if limit:
        limit.value = payload.value
        limit.window = window
    else:
        limit = LimitConfig(
            scope=LimitScope.CARD,
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
