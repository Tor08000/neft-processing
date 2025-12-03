from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional

import os

from celery import Celery
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db import SessionLocal
from app.models.limit_rule import LimitRule

from neft_shared.logging_setup import get_logger
from app.services.limits_engine import calculate_used_amount, evaluate_limits

from app.models.operation import Operation

logger = get_logger(__name__)

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_DEFAULT_QUEUE = os.getenv("CELERY_DEFAULT_QUEUE", "celery")
DISABLE_CELERY = os.getenv("DISABLE_CELERY", "0") == "1"
DEFAULT_DAILY_LIMIT = 1_000_000
DEFAULT_LIMIT_PER_TX = 50_000

celery_app: Optional[Celery]
if not DISABLE_CELERY:
    celery_app = Celery(
        "neft-workers",
        broker=CELERY_BROKER_URL,
        backend=CELERY_RESULT_BACKEND,
    )
    celery_app.conf.update(
        task_default_queue=CELERY_DEFAULT_QUEUE,
        task_default_exchange=CELERY_DEFAULT_QUEUE,
        task_default_routing_key=CELERY_DEFAULT_QUEUE,
        broker_connection_retry_on_startup=True,
    )
else:
    celery_app = None
    logger.warning("Celery disabled via DISABLE_CELERY=1 – limits sync mode will use stub")


class CheckAndReserveRequest(BaseModel):
    client_id: Optional[str] = None
    card_id: Optional[str] = None
    merchant_id: Optional[str] = None
    terminal_id: Optional[str] = None
    amount: int
    currency: str = "RUB"
    phase: str = "AUTH"
    client_group_id: Optional[str] = None
    card_group_id: Optional[str] = None
    product_category: Optional[str] = None
    mcc: Optional[str] = None
    tx_type: Optional[str] = None


class CheckAndReserveResult(BaseModel):
    approved: bool
    response_code: str
    response_message: str
    daily_limit: int
    limit_per_tx: int
    used_today: int
    new_used_today: int
    applied_rule_id: Optional[int] = None


class CheckAndReserveTaskResponse(BaseModel):
    task: str
    result: CheckAndReserveResult


class RecalcLimitsRequest(BaseModel):
    merchant_id: str
    terminal_id: str
    client_id: str
    card_id: str


class LimitsTaskResponse(BaseModel):
    task: str
    result: Dict[str, Any]


class CeleryUnavailable(Exception):
    pass


def _evaluate_locally(req: CheckAndReserveRequest, db: Session | None = None) -> CheckAndReserveResult:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        rules = session.query(LimitRule).filter(LimitRule.active.is_(True)).all()
        used_today = calculate_used_amount(session, req)
    finally:
        if owns_session:
            session.close()

    payload = evaluate_limits(req, rules, used_today=used_today)
    return CheckAndReserveResult(**payload)


def call_limits_check_and_reserve_sync(
    req: CheckAndReserveRequest, db: Session | None = None
) -> CheckAndReserveResult:
    """Call limits.check_and_reserve synchronously or fallback to stub."""

    if celery_app:
        try:
            result = celery_app.send_task(
                "limits.check_and_reserve",
                kwargs=req.dict(),
            )
            payload = result.get(timeout=10)  # type: ignore[assignment]
            return _normalize_limits_payload(payload, req)
        except Exception as exc:  # pragma: no cover
            logger.warning("Celery limits.check_and_reserve failed, using local stub: %s", exc)
    return _evaluate_locally(req, db=db)


def evaluate_limits_locally(req: CheckAndReserveRequest, db: Session | None = None) -> CheckAndReserveResult:
    """Public helper for invoking the local limits evaluator."""

    return _evaluate_locally(req, db=db)
