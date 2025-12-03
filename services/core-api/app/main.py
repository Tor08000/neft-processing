from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4

from celery.exceptions import TimeoutError as CeleryTimeoutError
from fastapi import Body, Depends, FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from neft_shared.logging_setup import get_logger, init_logging

from app.db import init_db, SessionLocal, get_db
from sqlalchemy.orm import Session
from app.api.routes import router as api_router
from app.routers.admin import router as admin_router
from app.services.transactions import derive_tx_type
from app.services.limits import (
    CheckAndReserveRequest,
    CheckAndReserveResult,
    CheckAndReserveTaskResponse,
    LimitsTaskResponse,
    RecalcLimitsRequest,
    call_limits_check_and_reserve_sync,
    celery_app,
)
from app.services.bootstrap import ensure_default_refs


# Если есть отдельный роутер для чтения операций из БД – подключим его
try:
    from app.api.v1.endpoints.operations_read import router as operations_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    operations_router = None  # type: ignore

# Роутер транзакций поверх operations
try:
    from app.api.v1.endpoints.transactions import router as transactions_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    transactions_router = None  # type: ignore

# Роутер отчётов по биллингу
try:
    from app.api.v1.endpoints.reports_billing import router as reports_billing_router
except Exception:  # pragma: no cover - в dev может ещё не существовать
    reports_billing_router = None  # type: ignore

SERVICE_NAME = os.getenv("SERVICE_NAME", "core-api")
init_logging(service_name=SERVICE_NAME)
logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Pydantic-модели
# -----------------------------------------------------------------------------
class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "ok"


class CeleryPingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str
    result: Dict[str, Any]


class TransactionLogEntry(BaseModel):
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


class TransactionsPage(BaseModel):
    items: List[TransactionLogEntry]
    total: int
    limit: int
    offset: int


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
    # amount стал НЕобязательным:
    # - если есть → частичный / явный возврат
    # - если нет → FULL REFUND оставшейся суммы
    amount: Optional[int] = None
    reason: Optional[str] = None


class ReversalRequest(BaseModel):
    reason: Optional[str] = None


# -----------------------------------------------------------------------------
# In-memory лог операций + сохранение в БД
# -----------------------------------------------------------------------------
TRANSACTION_LOG: List[TransactionLogEntry] = []


def _persist_operation_to_db(entry: TransactionLogEntry) -> None:
    """
    Пишем операцию в таблицу operations через ORM.

    Используем каноническую модель app.models.operation.Operation.
    """
    try:
        from app.db import SessionLocal  # type: ignore
        from app.models.operation import Operation  # type: ignore
    except Exception as exc:  # pragma: no cover
        logger.warning("DB Operation model not available yet: %s", exc)
        return

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
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to persist operation to DB: %s", exc)
        db.rollback()
    finally:
        db.close()


def _append_log_entry(entry: TransactionLogEntry) -> TransactionLogEntry:
    TRANSACTION_LOG.append(entry)
    _persist_operation_to_db(entry)
    return entry


def _find_transaction(operation_id: str) -> Optional[TransactionLogEntry]:
    for tx in TRANSACTION_LOG:
        if tx.operation_id == operation_id:
            return tx
    return None


def _get_transaction_or_404(operation_id: str) -> TransactionLogEntry:
    tx = _find_transaction(operation_id)
    if not tx:
        raise HTTPException(status_code=404, detail="operation not found")
    return tx


def _get_children(parent_id: str) -> List[TransactionLogEntry]:
    return [tx for tx in TRANSACTION_LOG if tx.parent_operation_id == parent_id]


def _get_captures_for_auth(auth_operation_id: str) -> List[TransactionLogEntry]:
    return [
        tx
        for tx in TRANSACTION_LOG
        if tx.operation_type == "CAPTURE" and tx.parent_operation_id == auth_operation_id
    ]


def _get_refunds_for_capture(capture_operation_id: str) -> List[TransactionLogEntry]:
    return [
        tx
        for tx in TRANSACTION_LOG
        if tx.operation_type == "REFUND" and tx.parent_operation_id == capture_operation_id
    ]


# -----------------------------------------------------------------------------
# FASTAPI
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    db = SessionLocal()
    try:
        ensure_default_refs(db)
    finally:
        db.close()
    logger.info("core-api startup complete")
    yield


app = FastAPI(
    title="NEFT Core API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Основной роутер v1
app.include_router(api_router, prefix="/api/v1")


# Включаем доп. роутер с чтением операций из БД, если он есть
if operations_router is not None:
    app.include_router(operations_router, prefix="")

# Включаем роутер транзакций, если он доступен
if transactions_router is not None:
    app.include_router(transactions_router, prefix="")

# Включаем роутер отчётов, если он доступен
if reports_billing_router is not None:
    app.include_router(reports_billing_router, prefix="")

app.include_router(admin_router)


# -----------------------------------------------------------------------------
# HEALTH
# -----------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse)
@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/health/db", response_model=HealthResponse)
def health_db(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        db.execute("SELECT 1")
        return HealthResponse(status="ok")
    except Exception as exc:  # pragma: no cover
        logger.exception("DB health failed: %s", exc)
        raise HTTPException(status_code=503, detail="db unavailable")


@app.get("/health/celery", response_model=HealthResponse)
def health_celery() -> HealthResponse:
    if not celery_app:
        raise HTTPException(status_code=503, detail="celery disabled")
    try:
        celery_app.control.ping(timeout=2)
        return HealthResponse(status="ok")
    except Exception as exc:  # pragma: no cover
        logger.exception("Celery health failed: %s", exc)
        raise HTTPException(status_code=503, detail="celery unavailable")


# -----------------------------------------------------------------------------
# Celery health
# -----------------------------------------------------------------------------
@app.get("/api/v1/health/enqueue", response_model=CeleryPingResponse)
def health_enqueue(
    wait: bool = Query(False, description="Wait synchronously for Celery ping result"),
) -> CeleryPingResponse:
    if not celery_app:
        # работаем в деградированном режиме без Celery
        return CeleryPingResponse(task="disabled", result={"pong": 1, "celery": "disabled"})

    try:
        async_result = celery_app.send_task("workers.ping", kwargs={"x": 1})
    except Exception as exc:
        logger.exception("Failed to enqueue Celery ping task: %s", exc)
        raise HTTPException(status_code=503, detail="Celery unavailable")

    if not wait:
        # просто проверяем, что задача успешно поставлена в очередь
        return CeleryPingResponse(
            task="ping",
            result={"queued": True, "task_id": async_result.id},
        )

    # Синхронное ожидание результата с обработкой таймаута
    try:
        result = async_result.get(timeout=5)
        return CeleryPingResponse(task="ping", result=result)
    except CeleryTimeoutError:
        logger.warning("Celery ping timeout, task_id=%s", async_result.id)
        # Не роняем /health/enqueue в 500, просто сигнализируем, что таймаут
        return CeleryPingResponse(
            task="ping",
            result={"error": "timeout", "task_id": async_result.id},
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("Celery ping failed: %s", exc)
        raise HTTPException(status_code=503, detail="Celery ping failed")


# -----------------------------------------------------------------------------
# LIMITS – обёртки над tasks limits.check_and_reserve / limits.recalc
# -----------------------------------------------------------------------------
@app.post("/api/v1/limits/check-and-reserve", response_model=CheckAndReserveTaskResponse)
def limits_check_and_reserve(
    body: CheckAndReserveRequest = Body(...),
) -> CheckAndReserveTaskResponse:
    result = call_limits_check_and_reserve_sync(body)
    return CheckAndReserveTaskResponse(task="limits.check_and_reserve", result=result)


@app.post("/api/v1/limits/recalc", response_model=LimitsTaskResponse)
def limits_recalc(
    body: RecalcLimitsRequest = Body(...),
) -> LimitsTaskResponse:
    if not celery_app:
        return LimitsTaskResponse(
            task="limits.recalc",
            result={"status": "queued", "celery": "disabled"},
        )

    async_result = celery_app.send_task("limits.recalc_all", kwargs={})
    return LimitsTaskResponse(task="limits.recalc_all", result={"task_id": async_result.id})


# -----------------------------------------------------------------------------
# AUTH
# -----------------------------------------------------------------------------
@app.post(
    "/api/v1/processing/terminal-auth",
    response_model=TransactionLogEntry,
)
def terminal_auth(body: TerminalAuthRequest = Body(...)) -> TransactionLogEntry:
    tx_type = body.tx_type or derive_tx_type(
        product_category=body.product_category, mcc=body.mcc
    )

    limits_result = call_limits_check_and_reserve_sync(
        CheckAndReserveRequest(
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
    )

    op_id = str(uuid4())
    status = "AUTHORIZED" if limits_result.approved else "DECLINED"

    entry = TransactionLogEntry(
        operation_id=op_id,
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
    _append_log_entry(entry)
    return entry


# -----------------------------------------------------------------------------
# CAPTURE
# -----------------------------------------------------------------------------
def _create_capture_entry(
    auth_tx: TransactionLogEntry,
    amount: int,
    limits_result: Optional[CheckAndReserveResult] = None,
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


@app.post(
    "/api/v1/transactions/{auth_operation_id}/capture",
    response_model=TransactionLogEntry,
)
def capture_transaction(
    auth_operation_id: str = Path(..., description="AUTH operation id"),
    body: CaptureRequest = Body(...),
) -> TransactionLogEntry:
    auth_tx = _get_transaction_or_404(auth_operation_id)
    if auth_tx.operation_type != "AUTH":
        raise HTTPException(status_code=400, detail="only AUTH can be captured")

    existing_captures = _get_captures_for_auth(auth_operation_id)
    already_captured_amount = sum(tx.amount for tx in existing_captures)
    if already_captured_amount + body.amount > auth_tx.amount:
        raise HTTPException(status_code=400, detail="capture amount exceeds authorized amount")

    capture_tx_type = auth_tx.tx_type or derive_tx_type(
        product_category=auth_tx.product_category, mcc=auth_tx.mcc
    )
    limits_result = call_limits_check_and_reserve_sync(
        CheckAndReserveRequest(
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
    )

    entry = _create_capture_entry(auth_tx, body.amount, limits_result)
    _append_log_entry(entry)
    return entry


# -----------------------------------------------------------------------------
# REFUND
# -----------------------------------------------------------------------------
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


@app.post(
    "/api/v1/transactions/{capture_operation_id}/refund",
    response_model=TransactionLogEntry,
)
def refund_transaction(
    capture_operation_id: str = Path(..., description="CAPTURE operation id"),
    body: RefundRequest = Body(...),
) -> TransactionLogEntry:
    capture_tx = _get_transaction_or_404(capture_operation_id)
    if capture_tx.operation_type != "CAPTURE":
        raise HTTPException(status_code=400, detail="only CAPTURE can be refunded")

    refunds = _get_refunds_for_capture(capture_operation_id)
    already_refunded = sum(tx.amount for tx in refunds)

    # Сколько ещё можно вернуть
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


# -----------------------------------------------------------------------------
# REVERSAL
# -----------------------------------------------------------------------------
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
        authorized=False,
        response_code="00",
        response_message="reversed",
        parent_operation_id=original_tx.operation_id,
        reason=reason,
        mcc=original_tx.mcc,
        product_code=original_tx.product_code,
        product_category=original_tx.product_category,
        tx_type=original_tx.tx_type,
    )


@app.post(
    "/api/v1/transactions/{operation_id}/reversal",
    response_model=TransactionLogEntry,
)
def reverse_transaction(
    operation_id: str = Path(..., description="operation id to reverse"),
    body: ReversalRequest = Body(...),
) -> TransactionLogEntry:
    original_tx = _get_transaction_or_404(operation_id)

    # нельзя ревёрсить уже ревёрснутые операции
    if original_tx.operation_type == "REVERSAL":
        raise HTTPException(status_code=400, detail="cannot reverse reversal")

    # проверим, не был ли уже сделан REVERSAL для этой операции
    children = _get_children(original_tx.operation_id)
    if any(child.operation_type == "REVERSAL" for child in children):
        raise HTTPException(status_code=400, detail="reversal already exists for this operation")

    entry = _create_reversal_entry(original_tx, body.reason)
    _append_log_entry(entry)
    return entry


# -----------------------------------------------------------------------------
# ЧТЕНИЕ in-memory лога
# -----------------------------------------------------------------------------
@app.get("/api/v1/transactions/log", response_model=TransactionsPage)
def list_operations_log(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> TransactionsPage:
    # Возвращаем в обратном порядке (сначала последние)
    items = list(reversed(TRANSACTION_LOG))
    total = len(items)
    slice_ = items[offset : offset + limit]
    return TransactionsPage(
        items=slice_,
        total=total,
        limit=limit,
        offset=offset,
    )
