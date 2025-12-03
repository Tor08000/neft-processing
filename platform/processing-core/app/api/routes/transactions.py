# services/core-api/app/api/routes/transactions.py

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session

from neft_shared.logging_setup import get_logger

from app.db import SessionLocal, get_db
from app.models.operation import Operation
from app.services.limits import (
    CheckAndReserveRequest,
    CheckAndReserveResult,
    call_limits_check_and_reserve_sync,
)
from app.services.transactions import derive_tx_type

logger = get_logger(__name__)

router = APIRouter()


# =============================================================================
# Pydantic запросы
# =============================================================================

class TerminalAuthRequest(BaseModel):
    merchant_id: str
    terminal_id: str
    client_id: str
    card_id: str
    amount: int
    currency: str = "RUB"
    product_code: Optional[str] = None
    product_category: Optional[str] = None
    mcc: Optional[str] = None
    tx_type: Optional[str] = None
    client_group_id: Optional[str] = None
    card_group_id: Optional[str] = None


class CaptureRequest(BaseModel):
    amount: int


class RefundRequest(BaseModel):
    amount: Optional[int] = None
    reason: Optional[str] = None


class ReversalRequest(BaseModel):
    reason: Optional[str] = None


# =============================================================================
# Pydantic модель ответа (операция)
# =============================================================================

class TransactionLogEntry(BaseModel):
    operation_id: str
    created_at: datetime
    operation_type: str
    status: str

    merchant_id: str
    terminal_id: str
    client_id: str
    card_id: str

    amount: int
    currency: str = "RUB"

    daily_limit: Optional[int] = None
    limit_per_tx: Optional[int] = None
    used_today: Optional[int] = None
    new_used_today: Optional[int] = None

    authorized: bool = False
    response_code: str = "00"
    response_message: str = "OK"

    parent_operation_id: Optional[str] = None
    reason: Optional[str] = None

    mcc: Optional[str] = None
    product_code: Optional[str] = None
    product_category: Optional[str] = None
    tx_type: Optional[str] = None


# =============================================================================
# In-memory LOG + DB persist
# =============================================================================

_TRANSACTIONS: Dict[str, TransactionLogEntry] = {}


def _persist_operation_to_db(entry: TransactionLogEntry) -> None:
    """
    Запись операции в таблицу operations (Postgres).
    """
    db = SessionLocal()
    try:
        db_op = Operation(
            operation_id=entry.operation_id,
            created_at=entry.created_at,
            operation_type=entry.operation_type,
            status=entry.status,
            merchant_id=entry.merchant_id,
            terminal_id=entry.terminal_id,
            client_id=entry.client_id,
            card_id=entry.card_id,
            amount=entry.amount,
            currency=entry.currency,
            daily_limit=entry.daily_limit,
            limit_per_tx=entry.limit_per_tx,
            used_today=entry.used_today,
            new_used_today=entry.new_used_today,
            authorized=entry.authorized,
            response_code=entry.response_code,
            response_message=entry.response_message,
            parent_operation_id=entry.parent_operation_id,
            reason=entry.reason,
            mcc=entry.mcc,
            product_code=entry.product_code,
            product_category=entry.product_category,
            tx_type=entry.tx_type,
        )
        db.add(db_op)
        db.commit()
    except Exception as exc:
        logger.exception("DB persist failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def _append_log_entry(entry: TransactionLogEntry) -> TransactionLogEntry:
    """
    Унифицированная запись операции:
    - пишем в память
    - пишем в БД
    - логируем
    """
    _TRANSACTIONS[entry.operation_id] = entry
    _persist_operation_to_db(entry)

    logger.info(
        "Stored %s operation %s for card %s amount=%s",
        entry.operation_type,
        entry.operation_id,
        entry.card_id,
        entry.amount,
    )
    return entry


def _get_transaction_or_404(operation_id: str) -> TransactionLogEntry:
    tx = _TRANSACTIONS.get(operation_id)
    if not tx:
        raise HTTPException(status_code=404, detail="operation not found")
    return tx


def _get_children(parent_id: str) -> List[TransactionLogEntry]:
    return [tx for tx in _TRANSACTIONS.values() if tx.parent_operation_id == parent_id]


def _get_captures_for_auth(auth_operation_id: str) -> List[TransactionLogEntry]:
    return [
        tx for tx in _TRANSACTIONS.values()
        if tx.operation_type == "CAPTURE" and tx.parent_operation_id == auth_operation_id
    ]


def _get_refunds_for_capture(capture_operation_id: str) -> List[TransactionLogEntry]:
    return [
        tx for tx in _TRANSACTIONS.values()
        if tx.operation_type == "REFUND" and tx.parent_operation_id == capture_operation_id
    ]


# =============================================================================
# FACTORIES
# =============================================================================

def _create_auth_entry(
    body: TerminalAuthRequest, limits_result: CheckAndReserveResult, tx_type: Optional[str]
) -> TransactionLogEntry:
    status = "AUTHORIZED" if limits_result.approved else "DECLINED"
    return TransactionLogEntry(
        operation_id=str(uuid4()),
        created_at=datetime.utcnow(),
        operation_type="AUTH",
        status=status,
        merchant_id=body.merchant_id,
        terminal_id=body.terminal_id,
        client_id=body.client_id,
        card_id=body.card_id,
        amount=body.amount,
        currency=body.currency,
        daily_limit=limits_result.daily_limit,
        limit_per_tx=limits_result.limit_per_tx,
        used_today=limits_result.used_today,
        new_used_today=limits_result.new_used_today,
        authorized=limits_result.approved,
        response_code=limits_result.response_code,
        response_message=limits_result.response_message,
        mcc=body.mcc,
        product_code=body.product_code,
        product_category=body.product_category,
        tx_type=tx_type,
    )


def _create_capture_entry(
    auth_tx: TransactionLogEntry, amount: int, limits_result: Optional[CheckAndReserveResult] = None
) -> TransactionLogEntry:
    approved = limits_result.approved if limits_result else True
    status = "CAPTURED" if approved else "DECLINED"
    return TransactionLogEntry(
        operation_id=str(uuid4()),
        created_at=datetime.utcnow(),
        operation_type="CAPTURE",
        status=status,
        merchant_id=auth_tx.merchant_id,
        terminal_id=auth_tx.terminal_id,
        client_id=auth_tx.client_id,
        card_id=auth_tx.card_id,
        amount=amount,
        currency=auth_tx.currency,
        daily_limit=limits_result.daily_limit if limits_result else auth_tx.daily_limit,
        limit_per_tx=limits_result.limit_per_tx if limits_result else auth_tx.limit_per_tx,
        used_today=limits_result.used_today if limits_result else auth_tx.used_today,
        new_used_today=limits_result.new_used_today if limits_result else auth_tx.new_used_today,
        authorized=approved,
        response_code=limits_result.response_code if limits_result else "00",
        response_message=limits_result.response_message if limits_result else "captured",
        parent_operation_id=auth_tx.operation_id,
        mcc=auth_tx.mcc,
        product_code=auth_tx.product_code,
        product_category=auth_tx.product_category,
        tx_type=auth_tx.tx_type,
    )


def _create_refund_entry(
    capture_tx: TransactionLogEntry,
    amount: int,
    reason: Optional[str],
) -> TransactionLogEntry:
    return TransactionLogEntry(
        operation_id=str(uuid4()),
        created_at=datetime.utcnow(),
        operation_type="REFUND",
        status="REFUNDED",
        merchant_id=capture_tx.merchant_id,
        terminal_id=capture_tx.terminal_id,
        client_id=capture_tx.client_id,
        card_id=capture_tx.card_id,
        amount=amount,
        currency=capture_tx.currency,
        daily_limit=capture_tx.daily_limit,
        limit_per_tx=capture_tx.limit_per_tx,
        used_today=capture_tx.used_today,
        new_used_today=capture_tx.new_used_today,
        authorized=True,
        response_code="00",
        response_message="refunded",
        parent_operation_id=capture_tx.operation_id,
        reason=reason,
        mcc=capture_tx.mcc,
        product_code=capture_tx.product_code,
        product_category=capture_tx.product_category,
        tx_type=capture_tx.tx_type,
    )


def _create_reversal_entry(
    original_tx: TransactionLogEntry,
    reason: Optional[str],
) -> TransactionLogEntry:
    return TransactionLogEntry(
        operation_id=str(uuid4()),
        created_at=datetime.utcnow(),
        operation_type="REVERSAL",
        status="REVERSED",
        merchant_id=original_tx.merchant_id,
        terminal_id=original_tx.terminal_id,
        client_id=original_tx.client_id,
        card_id=original_tx.card_id,
        amount=original_tx.amount,
        currency=original_tx.currency,
        daily_limit=original_tx.daily_limit,
        limit_per_tx=original_tx.limit_per_tx,
        used_today=original_tx.used_today,
        new_used_today=original_tx.new_used_today,
        authorized=True,
        response_code="00",
        response_message="reversed",
        parent_operation_id=original_tx.operation_id,
        reason=reason,
        mcc=original_tx.mcc,
        product_code=original_tx.product_code,
        product_category=original_tx.product_category,
        tx_type=original_tx.tx_type,
    )


# =============================================================================
# ROUTES
# =============================================================================

@router.post("/processing/terminal-auth", response_model=TransactionLogEntry)
def terminal_auth(body: TerminalAuthRequest = Body(...)) -> TransactionLogEntry:
    tx_type = body.tx_type or derive_tx_type(
        product_category=body.product_category, mcc=body.mcc
    )
    limits_req = CheckAndReserveRequest(
        merchant_id=body.merchant_id,
        terminal_id=body.terminal_id,
        client_id=body.client_id,
        card_id=body.card_id,
        amount=body.amount,
        currency=body.currency,
        product_category=body.product_category,
        mcc=body.mcc,
        tx_type=tx_type,
        phase="AUTH",
        client_group_id=body.client_group_id,
        card_group_id=body.card_group_id,
    )
    limits_result = call_limits_check_and_reserve_sync(limits_req)
    entry = _create_auth_entry(body, limits_result, tx_type)
    return _append_log_entry(entry)


@router.post("/transactions/{auth_operation_id}/capture", response_model=TransactionLogEntry)
def capture_transaction(
    auth_operation_id: str = Path(...),
    body: CaptureRequest = Body(...),
) -> TransactionLogEntry:

    auth_tx = _get_transaction_or_404(auth_operation_id)

    if auth_tx.operation_type != "AUTH":
        raise HTTPException(status_code=400, detail="only AUTH can be captured")

    existing_captures = _get_captures_for_auth(auth_operation_id)
    already_captured = sum(tx.amount for tx in existing_captures)

    if already_captured + body.amount > auth_tx.amount:
        raise HTTPException(status_code=400, detail="capture amount exceeds authorized amount")
    capture_tx_type = auth_tx.tx_type or derive_tx_type(
        product_category=auth_tx.product_category, mcc=auth_tx.mcc
    )
    limits_req = CheckAndReserveRequest(
        merchant_id=auth_tx.merchant_id,
        terminal_id=auth_tx.terminal_id,
        client_id=auth_tx.client_id,
        card_id=auth_tx.card_id,
        amount=body.amount,
        currency=auth_tx.currency,
        product_category=auth_tx.product_category,
        mcc=auth_tx.mcc,
        tx_type=capture_tx_type,
        phase="CAPTURE",
    )
    limits_result = call_limits_check_and_reserve_sync(limits_req)

    entry = _create_capture_entry(auth_tx, body.amount, limits_result)
    return _append_log_entry(entry)


@router.post("/transactions/{capture_operation_id}/refund", response_model=TransactionLogEntry)
def refund_transaction(
    capture_operation_id: str = Path(...),
    body: RefundRequest = Body(...),
) -> TransactionLogEntry:

    capture_tx = _get_transaction_or_404(capture_operation_id)

    if capture_tx.operation_type != "CAPTURE":
        raise HTTPException(status_code=400, detail="only CAPTURE can be refunded")

    refunds = _get_refunds_for_capture(capture_operation_id)
    already_refunded = sum(tx.amount for tx in refunds)

    remaining = capture_tx.amount - already_refunded
    if remaining <= 0:
        raise HTTPException(status_code=400, detail="nothing to refund")

    refund_amount = body.amount if body.amount is not None else remaining

    if refund_amount <= 0:
        raise HTTPException(status_code=400, detail="refund amount must be positive")

    if refund_amount + already_refunded > capture_tx.amount:
        raise HTTPException(status_code=400, detail="refund amount exceeds captured amount")

    entry = _create_refund_entry(capture_tx, refund_amount, body.reason)
    return _append_log_entry(entry)


@router.post("/transactions/{operation_id}/reversal", response_model=TransactionLogEntry)
def reverse_transaction(
    operation_id: str = Path(...),
    body: ReversalRequest = Body(...),
) -> TransactionLogEntry:

    original_tx = _get_transaction_or_404(operation_id)

    if original_tx.operation_type == "REVERSAL":
        raise HTTPException(status_code=400, detail="cannot reverse reversal")

    children = _get_children(original_tx.operation_id)
    if any(ch.operation_type == "REVERSAL" for ch in children):
        raise HTTPException(status_code=400, detail="reversal already exists for this operation")

    entry = _create_reversal_entry(original_tx, body.reason)
    return _append_log_entry(entry)
