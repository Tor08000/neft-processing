from __future__ import annotations

import os
from typing import Any, Dict, Optional

from celery import Celery
from pydantic import BaseModel

from app.db import SessionLocal
from app.models.limit_rule import LimitRule

from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
DISABLE_CELERY = os.getenv("DISABLE_CELERY", "0") == "1"

celery_app: Optional[Celery]
if not DISABLE_CELERY:
    celery_app = Celery(
        "neft-workers",
        broker=CELERY_BROKER_URL,
        backend=CELERY_RESULT_BACKEND,
    )
    celery_app.conf.update(
        task_default_queue=os.getenv("CELERY_DEFAULT_QUEUE", "default"),
        task_default_exchange=os.getenv("CELERY_DEFAULT_QUEUE", "default"),
        task_default_routing_key=os.getenv("CELERY_DEFAULT_QUEUE", "default"),
        broker_connection_retry_on_startup=True,
    )
else:
    celery_app = None
    logger.warning("Celery disabled via DISABLE_CELERY=1 – limits sync mode will use stub")


class CheckAndReserveRequest(BaseModel):
    merchant_id: str
    terminal_id: str
    client_id: str
    card_id: str
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


def _match_rule(req: CheckAndReserveRequest, rule: LimitRule) -> bool:
    if rule.phase not in {req.phase, "BOTH"}:
        return False

    for field in [
        "client_id",
        "card_id",
        "merchant_id",
        "terminal_id",
        "client_group_id",
        "card_group_id",
        "product_category",
        "mcc",
        "tx_type",
        "currency",
    ]:
        rule_value = getattr(rule, field)
        req_value = getattr(req, field, None)
        if rule_value is not None and rule_value != req_value:
            return False

    return True


def evaluate_limits_locally(req: CheckAndReserveRequest) -> CheckAndReserveResult:
    """Evaluate limits based on local DB rules when Celery is unavailable."""

    session = SessionLocal()
    try:
        rules = (
            session.query(LimitRule)
            .filter(LimitRule.active.is_(True))
            .order_by(LimitRule.id.asc())
            .all()
        )

        matched: Optional[LimitRule] = None
        for rule in rules:
            if _match_rule(req, rule):
                matched = rule
                break

        if matched:
            daily_limit = matched.daily_limit if matched.daily_limit is not None else 1_000_000
            limit_per_tx = matched.limit_per_tx if matched.limit_per_tx is not None else 50_000
        else:
            daily_limit = 1_000_000
            limit_per_tx = 50_000

        used_today = 0
        new_used_today = used_today + req.amount
        approved = req.amount <= limit_per_tx and new_used_today <= daily_limit

        return CheckAndReserveResult(
            approved=approved,
            response_code="00" if approved else "51",
            response_message="approved" if approved else "limit exceeded",
            daily_limit=daily_limit,
            limit_per_tx=limit_per_tx,
            used_today=used_today,
            new_used_today=new_used_today,
        )
    finally:
        session.close()


def call_limits_check_and_reserve_sync(req: CheckAndReserveRequest) -> CheckAndReserveResult:
    """Call limits.check_and_reserve synchronously or fallback to stub."""

    if celery_app:
        try:
            result = celery_app.send_task(
                "limits.check_and_reserve",
                kwargs=req.dict(),
            )
            payload = result.get(timeout=10)  # type: ignore[assignment]
            return CheckAndReserveResult(**payload)
        except Exception as exc:  # pragma: no cover
            logger.warning("Celery limits.check_and_reserve failed, using local stub: %s", exc)

    try:
        return evaluate_limits_locally(req)
    except Exception as exc:  # pragma: no cover - fallback to stub
        logger.warning("Local limits evaluation failed, using stub: %s", exc)

    daily_limit = 1_000_000
    limit_per_tx = 50_000
    used_today = 20_000
    new_used_today = used_today + req.amount
    approved = req.amount <= limit_per_tx and new_used_today <= daily_limit
    return CheckAndReserveResult(
        approved=approved,
        response_code="00" if approved else "51",
        response_message="approved" if approved else "limit exceeded",
        daily_limit=daily_limit,
        limit_per_tx=limit_per_tx,
        used_today=used_today,
        new_used_today=new_used_today,
    )
