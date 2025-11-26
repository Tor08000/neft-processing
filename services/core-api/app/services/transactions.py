from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Sequence

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.operation import Operation
from app.schemas.operations import OperationSchema
from app.schemas.transactions import (
    TransactionDetailResponse,
    TransactionSchema,
    TransactionsPage,
)


def _group_operations_by_auth(
    operations: Iterable[Operation], auth_ids: List[str]
) -> Dict[str, List[Operation]]:
    auth_set = set(auth_ids)
    mapping: Dict[str, List[Operation]] = {auth_id: [] for auth_id in auth_ids}

    by_id: Dict[str, Operation] = {op.operation_id: op for op in operations}

    for op in operations:
        if op.operation_type == "AUTH" and op.operation_id in auth_set:
            mapping[op.operation_id].append(op)
            continue

        current = op
        visited = 0
        root_id: str | None = None

        while current.parent_operation_id and visited < 5:
            parent = by_id.get(current.parent_operation_id)
            if parent is None:
                break
            if parent.operation_type == "AUTH" and parent.operation_id in auth_set:
                root_id = parent.operation_id
                break
            current = parent
            visited += 1

        if root_id is not None:
            mapping[root_id].append(op)

    return mapping


def _determine_status(
    authorized_amount: int,
    captured_amount: int,
    refunded_amount: int,
    operations: Sequence[Operation],
) -> str:
    if authorized_amount <= 0:
        return "ERROR"

    if any(op.operation_type == "REVERSAL" for op in operations):
        return "CANCELLED"

    if refunded_amount > 0:
        if refunded_amount >= captured_amount:
            return "REFUNDED"
        if captured_amount > 0 and refunded_amount < captured_amount:
            return "PARTIALLY_REFUNDED"

    if captured_amount >= authorized_amount:
        return "CAPTURED"
    if 0 < captured_amount < authorized_amount:
        return "PARTIALLY_CAPTURED"

    if captured_amount == 0:
        return "AUTHORIZED"

    return "ERROR"


def build_transaction_from_operations(
    operations: Sequence[Operation],
) -> TransactionSchema | None:
    if not operations:
        return None

    auth_operations = [op for op in operations if op.operation_type == "AUTH"]
    if not auth_operations:
        return None

    auth_operation = sorted(auth_operations, key=lambda op: op.created_at)[0]
    auth_id = auth_operation.operation_id

    captures = [
        op
        for op in operations
        if op.operation_type == "CAPTURE" and op.parent_operation_id == auth_id
    ]
    capture_ids = {op.operation_id for op in captures}
    refunds = [
        op
        for op in operations
        if op.operation_type == "REFUND"
        and (
            op.parent_operation_id == auth_id
            or (op.parent_operation_id and op.parent_operation_id in capture_ids)
        )
    ]

    authorized_amount = sum(op.amount for op in auth_operations)
    captured_amount = sum(op.amount for op in captures)
    refunded_amount = sum(op.amount for op in refunds)

    status = _determine_status(
        authorized_amount=authorized_amount,
        captured_amount=captured_amount,
        refunded_amount=refunded_amount,
        operations=operations,
    )

    updated_at = max(operations, key=lambda op: op.created_at).created_at
    last_operation = max(operations, key=lambda op: (op.created_at, op.operation_id))

    operation_types = sorted({op.operation_type for op in operations})

    return TransactionSchema(
        transaction_id=auth_id,
        created_at=auth_operation.created_at,
        updated_at=updated_at,
        merchant_id=auth_operation.merchant_id,
        terminal_id=auth_operation.terminal_id,
        client_id=auth_operation.client_id,
        card_id=auth_operation.card_id,
        currency=auth_operation.currency,
        authorized_amount=authorized_amount,
        captured_amount=captured_amount,
        refunded_amount=refunded_amount,
        status=status,
        operation_types=operation_types,
        auth_operation=OperationSchema.from_orm(auth_operation),
        last_operation=OperationSchema.from_orm(last_operation),
    )


def _fetch_operations_for_auths(
    db: Session, auth_ids: List[str]
) -> Dict[str, List[Operation]]:
    if not auth_ids:
        return {}

    operations = (
        db.query(Operation)
        .filter(
            or_(
                Operation.operation_id.in_(auth_ids),
                Operation.parent_operation_id.in_(auth_ids),
            )
        )
        .order_by(Operation.created_at.asc())
        .all()
    )

    capture_ids = [
        op.operation_id
        for op in operations
        if op.operation_type == "CAPTURE" and op.parent_operation_id in auth_ids
    ]

    if capture_ids:
        refund_children = (
            db.query(Operation)
            .filter(
                Operation.operation_type == "REFUND",
                Operation.parent_operation_id.in_(capture_ids),
            )
            .order_by(Operation.created_at.asc())
            .all()
        )
        operations.extend(refund_children)

    return _group_operations_by_auth(operations, auth_ids)


def list_transactions(
    db: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    client_id: str | None = None,
    card_id: str | None = None,
    merchant_id: str | None = None,
    terminal_id: str | None = None,
    status: str | None = None,
    from_created_at: datetime | None = None,
    to_created_at: datetime | None = None,
    no_pagination: bool = False,
) -> TransactionsPage:
    auth_query = db.query(Operation).filter(Operation.operation_type == "AUTH")

    if client_id:
        auth_query = auth_query.filter(Operation.client_id == client_id)
    if card_id:
        auth_query = auth_query.filter(Operation.card_id == card_id)
    if merchant_id:
        auth_query = auth_query.filter(Operation.merchant_id == merchant_id)
    if terminal_id:
        auth_query = auth_query.filter(Operation.terminal_id == terminal_id)
    if from_created_at:
        auth_query = auth_query.filter(Operation.created_at >= from_created_at)
    if to_created_at:
        auth_query = auth_query.filter(Operation.created_at <= to_created_at)

    auth_query = auth_query.order_by(Operation.created_at.desc())

    if status:
        auth_operations = auth_query.all()
        auth_ids = [op.operation_id for op in auth_operations]
        operations_by_auth = _fetch_operations_for_auths(db, auth_ids)

        transactions: List[TransactionSchema] = []
        for auth in auth_operations:
            tx_operations = operations_by_auth.get(auth.operation_id, [])
            transaction = build_transaction_from_operations(tx_operations)
            if transaction and transaction.status == status:
                transactions.append(transaction)

        total = len(transactions)

        if no_pagination:
            return TransactionsPage(
                items=transactions, total=total, limit=total, offset=0
            )

        paginated = transactions[offset : offset + limit]
        return TransactionsPage(
            items=paginated, total=total, limit=limit, offset=offset
        )

    if no_pagination:
        auth_operations = auth_query.all()
        total = len(auth_operations)
    else:
        total = auth_query.count()
        auth_operations = auth_query.offset(offset).limit(limit).all()
    auth_ids = [op.operation_id for op in auth_operations]
    operations_by_auth = _fetch_operations_for_auths(db, auth_ids)

    items: List[TransactionSchema] = []
    for auth in auth_operations:
        transaction = build_transaction_from_operations(
            operations_by_auth.get(auth.operation_id, [])
        )
        if transaction:
            items.append(transaction)

    return TransactionsPage(
        items=items,
        total=total,
        limit=total if no_pagination else limit,
        offset=0 if no_pagination else offset,
    )


def get_transaction(db: Session, transaction_id: str) -> TransactionDetailResponse | None:
    operations = (
        db.query(Operation)
        .filter(
            or_(
                Operation.operation_id == transaction_id,
                Operation.parent_operation_id == transaction_id,
            )
        )
        .order_by(Operation.created_at.asc())
        .all()
    )

    if not operations:
        return None

    transaction = build_transaction_from_operations(operations)
    if transaction is None:
        return None

    return TransactionDetailResponse(
        transaction=transaction,
        operations=[OperationSchema.from_orm(op) for op in operations],
    )
