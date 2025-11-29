from __future__ import annotations

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.card import Card
from app.models.client import Client
from app.models.operation import Operation
from app.schemas.admin_dashboard import (
    CardListResponse,
    CardShort,
    ClientListResponse,
    ClientShort,
    OperationListResponse,
    OperationShort,
    TransactionListResponse,
    TransactionShort,
)
from app.services.transactions import list_transactions
from app.security.admin_auth import require_admin

router = APIRouter(
    prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)


@router.get("/clients", response_model=ClientListResponse)
def list_clients(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    client_id: str | None = None,
    name: str | None = None,
    status: str | None = None,
    external_id: str | None = None,
    db: Session = Depends(get_db),
) -> ClientListResponse:
    query = db.query(Client)

    if client_id:
        try:
            parsed_client_id = UUID(client_id)
        except ValueError:
            return ClientListResponse(items=[], total=0, limit=limit, offset=offset)

        query = query.filter(Client.id == parsed_client_id)
    if name:
        query = query.filter(Client.name.ilike(f"%{name}%"))
    if status and hasattr(Client, "status"):
        query = query.filter(getattr(Client, "status") == status)
    if external_id:
        query = query.filter(Client.external_id == external_id)

    total = query.count()
    items: List[Client] = (
        query.order_by(Client.created_at.desc(), Client.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    serialized = [
        ClientShort(
            client_id=str(item.id),
            name=getattr(item, "name", None),
            status=getattr(item, "status", None),
            created_at=item.created_at,
        )
        for item in items
    ]

    return ClientListResponse(items=serialized, total=total, limit=limit, offset=offset)


@router.get("/cards", response_model=CardListResponse)
def list_cards(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    card_id: str | None = None,
    client_id: str | None = None,
    status: str | None = None,
    active: bool | None = None,
    db: Session = Depends(get_db),
) -> CardListResponse:
    query = db.query(Card)

    if card_id:
        query = query.filter(Card.id == card_id)
    if client_id:
        query = query.filter(Card.client_id == client_id)
    if status:
        query = query.filter(Card.status == status)
    if active is not None and hasattr(Card, "active"):
        query = query.filter(getattr(Card, "active") == active)

    total = query.count()
    items: List[Card] = (
        query.order_by(Card.created_at.desc(), Card.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    serialized = [
        CardShort(
            card_id=item.id,
            client_id=item.client_id,
            status=getattr(item, "status", None),
            active=getattr(item, "active", None),
            created_at=item.created_at,
        )
        for item in items
    ]

    return CardListResponse(items=serialized, total=total, limit=limit, offset=offset)


@router.get("/operations", response_model=OperationListResponse)
def list_operations(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    operation_type: str | None = None,
    status: str | None = None,
    merchant_id: str | None = None,
    terminal_id: str | None = None,
    client_id: str | None = None,
    card_id: str | None = None,
    from_created_at: datetime | None = None,
    to_created_at: datetime | None = None,
    mcc: str | None = None,
    product_category: str | None = None,
    tx_type: str | None = None,
    db: Session = Depends(get_db),
) -> OperationListResponse:
    query = db.query(Operation)

    if operation_type:
        query = query.filter(Operation.operation_type == operation_type)
    if status:
        query = query.filter(Operation.status == status)
    if merchant_id:
        query = query.filter(Operation.merchant_id == merchant_id)
    if terminal_id:
        query = query.filter(Operation.terminal_id == terminal_id)
    if client_id:
        query = query.filter(Operation.client_id == client_id)
    if card_id:
        query = query.filter(Operation.card_id == card_id)
    if from_created_at:
        query = query.filter(Operation.created_at >= from_created_at)
    if to_created_at:
        query = query.filter(Operation.created_at <= to_created_at)
    if mcc:
        query = query.filter(Operation.mcc == mcc)
    if product_category:
        query = query.filter(Operation.product_category == product_category)
    if tx_type:
        query = query.filter(Operation.tx_type == tx_type)

    total = query.count()
    items: List[Operation] = (
        query.order_by(Operation.created_at.desc(), Operation.operation_id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    serialized = [
        OperationShort(
            operation_id=item.operation_id,
            created_at=item.created_at,
            operation_type=item.operation_type,
            status=item.status,
            merchant_id=item.merchant_id,
            terminal_id=item.terminal_id,
            client_id=item.client_id,
            card_id=item.card_id,
            amount=item.amount,
            currency=item.currency,
            mcc=item.mcc,
            product_category=item.product_category,
            tx_type=item.tx_type,
        )
        for item in items
    ]

    return OperationListResponse(items=serialized, total=total, limit=limit, offset=offset)


@router.get("/transactions", response_model=TransactionListResponse)
def list_transactions_admin(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    client_id: str | None = None,
    card_id: str | None = None,
    merchant_id: str | None = None,
    terminal_id: str | None = None,
    status: str | None = None,
    from_created_at: datetime | None = None,
    to_created_at: datetime | None = None,
    mcc: str | None = None,
    product_category: str | None = None,
    tx_type: str | None = None,
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    page = list_transactions(
        db,
        limit=limit,
        offset=offset,
        client_id=client_id,
        card_id=card_id,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        status=status,
        from_created_at=from_created_at,
        to_created_at=to_created_at,
        no_pagination=True,
    )

    transactions = page.items
    if mcc:
        transactions = [tx for tx in transactions if tx.mcc == mcc]
    if product_category:
        transactions = [
            tx for tx in transactions if tx.product_category == product_category
        ]
    if tx_type:
        transactions = [tx for tx in transactions if tx.tx_type == tx_type]
    if status:
        transactions = [tx for tx in transactions if tx.status == status]

    transactions = sorted(
        transactions, key=lambda tx: (tx.created_at, tx.transaction_id), reverse=True
    )

    total = len(transactions)
    paginated = transactions[offset : offset + limit]

    serialized = [
        TransactionShort(
            transaction_id=tx.transaction_id,
            created_at=tx.created_at,
            updated_at=tx.updated_at,
            client_id=tx.client_id,
            card_id=tx.card_id,
            merchant_id=tx.merchant_id,
            terminal_id=tx.terminal_id,
            status=tx.status,
            authorized_amount=tx.authorized_amount,
            captured_amount=tx.captured_amount,
            refunded_amount=tx.refunded_amount,
            currency=tx.currency,
            mcc=tx.mcc,
            product_category=tx.product_category,
            tx_type=tx.tx_type,
        )
        for tx in paginated
    ]

    return TransactionListResponse(items=serialized, total=total, limit=limit, offset=offset)
