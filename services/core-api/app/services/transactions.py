from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Sequence
from uuid import UUID, uuid4

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.operation import Operation


class OperationNotFound(Exception):
    pass


class InvalidOperationState(Exception):
    pass

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


def derive_tx_type(
    auth_op: Operation | None = None,
    *,
    product_category: str | None = None,
    mcc: str | None = None,
) -> str | None:
    """
    Возвращает тип транзакции на основе product_category / mcc.

    Простая эвристика для v1.1:
    * если категория начинается с DIESEL/GASOLINE/GAS → "FUEL"
    * если MCC топливный (5541/5542) → "FUEL"
    * если есть категория, но она не относится к топливу → "OTHER"
    * иначе None
    """

    category = (product_category or (auth_op.product_category if auth_op else None))
    category = category.upper() if category else None
    effective_mcc = mcc or (auth_op.mcc if auth_op else None)

    if category:
        if category.startswith("DIESEL") or category.startswith("GASOLINE") or category.startswith(
            "GAS"
        ):
            return "FUEL"
        return "OTHER"

    if effective_mcc in {"5541", "5542"}:
        return "FUEL"

    return None


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
        mcc=auth_operation.mcc,
        product_code=auth_operation.product_code,
        product_category=auth_operation.product_category,
        tx_type=auth_operation.tx_type
        or derive_tx_type(auth_operation),
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
    min_amount: int | None = None,
    max_amount: int | None = None,
    order_by: str = "created_at_desc",
    product_category: str | None = None,
    mcc: str | None = None,
    tx_type: str | None = None,
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

    auth_operations = auth_query.order_by(Operation.created_at.desc()).all()

    auth_ids = [op.operation_id for op in auth_operations]
    operations_by_auth = _fetch_operations_for_auths(db, auth_ids)

    transactions: List[TransactionSchema] = []
    for auth in auth_operations:
        transaction = build_transaction_from_operations(
            operations_by_auth.get(auth.operation_id, [])
        )
        if transaction:
            transactions.append(transaction)

    if status:
        transactions = [tx for tx in transactions if tx.status == status]
    if product_category:
        transactions = [
            tx for tx in transactions if tx.product_category == product_category
        ]
    if mcc:
        transactions = [tx for tx in transactions if tx.mcc == mcc]
    if tx_type:
        transactions = [tx for tx in transactions if tx.tx_type == tx_type]
    if min_amount is not None:
        transactions = [
            tx for tx in transactions if tx.authorized_amount >= min_amount
        ]
    if max_amount is not None:
        transactions = [
            tx for tx in transactions if tx.authorized_amount <= max_amount
        ]

    ordering = {
        "created_at_desc": lambda tx: (-tx.created_at.timestamp(), tx.transaction_id),
        "created_at_asc": lambda tx: (tx.created_at.timestamp(), tx.transaction_id),
        "amount_desc": lambda tx: (-tx.authorized_amount, tx.transaction_id),
        "amount_asc": lambda tx: (tx.authorized_amount, tx.transaction_id),
    }
    sort_key = ordering.get(order_by, ordering["created_at_desc"])
    transactions = sorted(transactions, key=sort_key)

    total = len(transactions)

    if no_pagination:
        return TransactionsPage(items=transactions, total=total, limit=total, offset=0)

    paginated = transactions[offset : offset + limit]
    return TransactionsPage(items=paginated, total=total, limit=limit, offset=offset)


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


# =============================================================================
# Lifecycle helpers (capture/refund/reversal)
# =============================================================================


def _get_operation_or_error(db: Session, operation_id: UUID | str) -> Operation:
    op = (
        db.query(Operation)
        .filter(Operation.operation_id == str(operation_id))
        .with_for_update()
        .first()
    )
    if op is None:
        raise OperationNotFound(f"operation {operation_id} not found")
    return op


def capture_operation(db: Session, *, auth_operation_id: UUID, amount: int | None = None) -> Operation:
    auth_op = _get_operation_or_error(db, auth_operation_id)
    if auth_op.operation_type != "AUTH":
        raise InvalidOperationState("only AUTH operations can be captured")
    if auth_op.status not in {"AUTHORIZED", "PARTIALLY_CAPTURED"}:
        raise InvalidOperationState("auth is not in a capturable state")

    remaining = auth_op.amount - (auth_op.captured_amount or 0)
    capture_amount = remaining if amount is None else amount
    if capture_amount <= 0:
        raise InvalidOperationState("capture amount must be positive")
    if capture_amount > remaining:
        raise InvalidOperationState("capture amount exceeds authorized remainder")

    new_capture = Operation(
        operation_id=str(uuid4()),
        operation_type="CAPTURE",
        status="CAPTURED" if capture_amount == remaining else "PARTIALLY_CAPTURED",
        merchant_id=auth_op.merchant_id,
        terminal_id=auth_op.terminal_id,
        client_id=auth_op.client_id,
        card_id=auth_op.card_id,
        amount=capture_amount,
        currency=auth_op.currency,
        parent_operation_id=auth_op.operation_id,
        captured_amount=0,
        refunded_amount=0,
        mcc=auth_op.mcc,
        product_code=auth_op.product_code,
        product_category=auth_op.product_category,
        tx_type=auth_op.tx_type,
    )

    auth_op.captured_amount = (auth_op.captured_amount or 0) + capture_amount
    if auth_op.captured_amount >= auth_op.amount:
        auth_op.status = "CAPTURED"
    else:
        auth_op.status = "PARTIALLY_CAPTURED"

    db.add(new_capture)
    db.add(auth_op)
    db.commit()
    db.refresh(new_capture)
    db.refresh(auth_op)
    return new_capture


def refund_operation(
    db: Session, *, captured_operation_id: UUID, amount: int | None = None
) -> Operation:
    capture_op = _get_operation_or_error(db, captured_operation_id)
    if capture_op.operation_type != "CAPTURE":
        raise InvalidOperationState("only CAPTURE operations can be refunded")
    if capture_op.status not in {"CAPTURED", "PARTIALLY_REFUNDED"}:
        raise InvalidOperationState("capture is not refundable")

    remaining = capture_op.amount - (capture_op.refunded_amount or 0)
    refund_amount = remaining if amount is None else amount
    if refund_amount <= 0:
        raise InvalidOperationState("refund amount must be positive")
    if refund_amount > remaining:
        raise InvalidOperationState("refund amount exceeds captured remainder")

    refund_op = Operation(
        operation_id=str(uuid4()),
        operation_type="REFUND",
        status="REFUNDED" if refund_amount == remaining else "PARTIALLY_REFUNDED",
        merchant_id=capture_op.merchant_id,
        terminal_id=capture_op.terminal_id,
        client_id=capture_op.client_id,
        card_id=capture_op.card_id,
        amount=refund_amount,
        currency=capture_op.currency,
        parent_operation_id=capture_op.operation_id,
        captured_amount=0,
        refunded_amount=0,
        mcc=capture_op.mcc,
        product_code=capture_op.product_code,
        product_category=capture_op.product_category,
        tx_type=capture_op.tx_type,
    )

    capture_op.refunded_amount = (capture_op.refunded_amount or 0) + refund_amount
    if capture_op.refunded_amount >= capture_op.amount:
        capture_op.status = "REFUNDED"
    else:
        capture_op.status = "PARTIALLY_REFUNDED"

    db.add(refund_op)
    db.add(capture_op)
    db.commit()
    db.refresh(refund_op)
    db.refresh(capture_op)
    return refund_op


def reverse_auth(db: Session, *, auth_operation_id: UUID) -> Operation:
    auth_op = _get_operation_or_error(db, auth_operation_id)
    if auth_op.operation_type != "AUTH":
        raise InvalidOperationState("only AUTH operations can be reversed")

    children = (
        db.query(Operation)
        .filter(Operation.parent_operation_id == auth_op.operation_id)
        .all()
    )
    if any(child.operation_type == "CAPTURE" for child in children):
        raise InvalidOperationState("cannot reverse auth with captures")

    reversal_op = Operation(
        operation_id=str(uuid4()),
        operation_type="REVERSAL",
        status="REVERSED",
        merchant_id=auth_op.merchant_id,
        terminal_id=auth_op.terminal_id,
        client_id=auth_op.client_id,
        card_id=auth_op.card_id,
        amount=auth_op.amount,
        currency=auth_op.currency,
        parent_operation_id=auth_op.operation_id,
        captured_amount=0,
        refunded_amount=0,
        mcc=auth_op.mcc,
        product_code=auth_op.product_code,
        product_category=auth_op.product_category,
        tx_type=auth_op.tx_type,
    )

    auth_op.status = "REVERSED"
    db.add(reversal_op)
    db.add(auth_op)
    db.commit()
    db.refresh(reversal_op)
    db.refresh(auth_op)
    return reversal_op
