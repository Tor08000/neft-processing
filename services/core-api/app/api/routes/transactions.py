# services/core-api/app/api/routes/transactions.py

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Body, HTTPException, Path
from pydantic import BaseModel

from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)

router = APIRouter()


# -----------------------------------------------------------------------------
# Pydantic-модели запросов
# -----------------------------------------------------------------------------
class TerminalAuthRequest(BaseModel):
    merchant_id: str
    terminal_id: str
    client_id: str
    card_id: str
    amount: int
    currency: str = "RUB"


class CaptureRequest(BaseModel):
    amount: int


class RefundRequest(BaseModel):
    # amount может быть None:
    # - None  -> FULL REFUND (на оставшуюся сумму)
    # - число -> частичный / явный возврат
    amount: Optional[int] = None
    reason: Optional[str] = None


class ReversalRequest(BaseModel):
    reason: Optional[str] = None


# -----------------------------------------------------------------------------
# Pydantic-модель операции (ответ)
# -----------------------------------------------------------------------------
class TransactionLogEntry(BaseModel):
    """
    Упрощённая модель операции для Core API.

    Важно:
    - operation_id: str — именно строка, чтобы не было проблем с ResponseValidationError.
    """

    operation_id: str
    created_at: datetime
    operation_type: str  # AUTH, CAPTURE, REFUND, REVERSAL
    status: str

    merchant_id: str
    terminal_id: str
    client_id: str
    card_id: str

    amount: int
    currency: str = "RUB"

    parent_operation_id: Optional[str] = None
    reason: Optional[str] = None


# -----------------------------------------------------------------------------
# In-memory журнал операций
# -----------------------------------------------------------------------------
# Храним операции в памяти: ключ — operation_id, значение — TransactionLogEntry
_TRANSACTIONS: Dict[str, TransactionLogEntry] = {}


def _append_log_entry(entry: TransactionLogEntry) -> TransactionLogEntry:
    _TRANSACTIONS[entry.operation_id] = entry
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
    return [
        tx for tx in _TRANSACTIONS.values()
        if tx.parent_operation_id == parent_id
    ]


def _get_captures_for_auth(auth_operation_id: str) -> List[TransactionLogEntry]:
    return [
        tx
        for tx in _TRANSACTIONS.values()
        if tx.operation_type == "CAPTURE" and tx.parent_operation_id == auth_operation_id
    ]


def _get_refunds_for_capture(capture_operation_id: str) -> List[TransactionLogEntry]:
    return [
        tx
        for tx in _TRANSACTIONS.values()
        if tx.operation_type == "REFUND" and tx.parent_operation_id == capture_operation_id
    ]


# -----------------------------------------------------------------------------
# Вспомогательные фабрики операций
# -----------------------------------------------------------------------------
def _create_auth_entry(body: TerminalAuthRequest) -> TransactionLogEntry:
    """
    AUTH: здесь пока без интеграции с лимитами/Celery.
    Всегда авторизуем (AUTHORIZED).
    """
    op_id = str(uuid4())
    entry = TransactionLogEntry(
        operation_id=op_id,
        created_at=datetime.utcnow(),
        operation_type="AUTH",
        status="AUTHORIZED",
        merchant_id=body.merchant_id,
        terminal_id=body.terminal_id,
        client_id=body.client_id,
        card_id=body.card_id,
        amount=body.amount,
        currency=body.currency,
    )
    return entry


def _create_capture_entry(auth_tx: TransactionLogEntry, amount: int) -> TransactionLogEntry:
    return TransactionLogEntry(
        operation_id=str(uuid4()),
        created_at=datetime.utcnow(),
        operation_type="CAPTURE",
        status="CAPTURED",
        merchant_id=auth_tx.merchant_id,
        terminal_id=auth_tx.terminal_id,
        client_id=auth_tx.client_id,
        card_id=auth_tx.card_id,
        amount=amount,
        currency=auth_tx.currency,
        parent_operation_id=auth_tx.operation_id,
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
        parent_operation_id=capture_tx.operation_id,
        reason=reason,
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
        parent_operation_id=original_tx.operation_id,
        reason=reason,
    )


# -----------------------------------------------------------------------------
# ROUTES
# -----------------------------------------------------------------------------

@router.post(
    "/processing/terminal-auth",
    response_model=TransactionLogEntry,
)
def terminal_auth(
    body: TerminalAuthRequest = Body(...),
) -> TransactionLogEntry:
    """
    Авторизация терминала / карты / суммы.

    Возвращает объект с полем operation_id (строка!), которое и забирает run_tests.cmd.
    """
    entry = _create_auth_entry(body)
    _append_log_entry(entry)
    return entry


@router.post(
    "/transactions/{auth_operation_id}/capture",
    response_model=TransactionLogEntry,
)
def capture_transaction(
    auth_operation_id: str = Path(..., description="AUTH operation id"),
    body: CaptureRequest = Body(...),
) -> TransactionLogEntry:
    """
    CAPTURE по AUTH.
    """
    auth_tx = _get_transaction_or_404(auth_operation_id)
    if auth_tx.operation_type != "AUTH":
        raise HTTPException(status_code=400, detail="only AUTH can be captured")

    # Проверим, что не превышаем авторизованную сумму
    existing_captures = _get_captures_for_auth(auth_operation_id)
    already_captured_amount = sum(tx.amount for tx in existing_captures)
    if already_captured_amount + body.amount > auth_tx.amount:
        raise HTTPException(status_code=400, detail="capture amount exceeds authorized amount")

    entry = _create_capture_entry(auth_tx, body.amount)
    _append_log_entry(entry)
    return entry


@router.post(
    "/transactions/{capture_operation_id}/refund",
    response_model=TransactionLogEntry,
)
def refund_transaction(
    capture_operation_id: str = Path(..., description="CAPTURE operation id"),
    body: RefundRequest = Body(...),
) -> TransactionLogEntry:
    """
    REFUND по CAPTURE.
    Поддерживает:
    - полный возврат (amount = None -> на оставшуюся сумму),
    - частичные возвраты.
    """
    capture_tx = _get_transaction_or_404(capture_operation_id)
    if capture_tx.operation_type != "CAPTURE":
        raise HTTPException(status_code=400, detail="only CAPTURE can be refunded")

    refunds = _get_refunds_for_capture(capture_operation_id)
    already_refunded = sum(tx.amount for tx in refunds)

    remaining = capture_tx.amount - already_refunded
    if remaining <= 0:
        raise HTTPException(status_code=400, detail="nothing to refund")

    # Если amount не передан → FULL REFUND на оставшуюся сумму
    if body.amount is None:
        refund_amount = remaining
    else:
        refund_amount = body.amount

    if refund_amount <= 0:
        raise HTTPException(status_code=400, detail="refund amount must be positive")

    if already_refunded + refund_amount > capture_tx.amount:
        raise HTTPException(status_code=400, detail="refund amount exceeds captured amount")

    entry = _create_refund_entry(capture_tx, refund_amount, body.reason)
    _append_log_entry(entry)
    return entry


@router.post(
    "/transactions/{operation_id}/reversal",
    response_model=TransactionLogEntry,
)
def reverse_transaction(
    operation_id: str = Path(..., description="operation id to reverse"),
    body: ReversalRequest = Body(...),
) -> TransactionLogEntry:
    """
    REVERSAL любой операции (обычно AUTH).

    Ограничения:
    - нельзя ревёрсить REVERSAL;
    - нельзя делать два REVERSAL для одной и той же операции.
    """
    original_tx = _get_transaction_or_404(operation_id)

    if original_tx.operation_type == "REVERSAL":
        raise HTTPException(status_code=400, detail="cannot reverse reversal")

    children = _get_children(original_tx.operation_id)
    if any(child.operation_type == "REVERSAL" for child in children):
        raise HTTPException(status_code=400, detail="reversal already exists for this operation")

    entry = _create_reversal_entry(original_tx, body.reason)
    _append_log_entry(entry)
    return entry
