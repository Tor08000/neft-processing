from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional

from celery import Celery
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from pydantic import BaseModel

from neft_shared.logging_setup import get_logger

from app.db import SessionLocal
from app.models.limits import CardGroupMembership, ClientGroupMembership, LimitRule
from app.models.operation import Operation

logger = get_logger(__name__)

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
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


def _normalize_limits_payload(payload: Dict[str, Any], req: CheckAndReserveRequest) -> CheckAndReserveResult:
    approved = payload.get("approved")
    if approved is None:
        approved = payload.get("allowed")

    daily_limit = int(payload.get("daily_limit", DEFAULT_DAILY_LIMIT))
    limit_per_tx = int(payload.get("limit_per_tx", DEFAULT_LIMIT_PER_TX))
    used_today = int(payload.get("used_today", 0))
    new_used_today = int(payload.get("new_used_today", used_today + req.amount))

    response_code = payload.get("response_code")
    response_message = payload.get("response_message")

    if response_code is None:
        response_code = "00" if approved else "51"
    if response_message is None:
        response_message = payload.get("reason") or ("approved" if approved else "limit exceeded")

    return CheckAndReserveResult(
        approved=bool(approved),
        response_code=str(response_code),
        response_message=str(response_message),
        daily_limit=daily_limit,
        limit_per_tx=limit_per_tx,
        used_today=used_today,
        new_used_today=new_used_today,
    )


def evaluate_limits_locally(
    req: CheckAndReserveRequest, db: Optional[Session] = None
) -> CheckAndReserveResult:
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        client_group_ids = [
            row[0]
            for row in db.query(ClientGroupMembership.group_id)
            .filter(ClientGroupMembership.client_id == req.client_id)
            .all()
        ]
        card_group_ids = [
            row[0]
            for row in db.query(CardGroupMembership.group_id)
            .filter(CardGroupMembership.card_id == req.card_id)
            .all()
        ]

        client_condition = [LimitRule.client_group_id.is_(None)]
        if client_group_ids:
            client_condition.append(LimitRule.client_group_id.in_(client_group_ids))

        card_condition = [LimitRule.card_group_id.is_(None)]
        if card_group_ids:
            card_condition.append(LimitRule.card_group_id.in_(card_group_ids))

        rule = (
            db.query(LimitRule)
            .filter(or_(*client_condition))
            .filter(or_(*card_condition))
            .filter(LimitRule.currency == req.currency)
            .order_by(LimitRule.priority.desc(), LimitRule.id.asc())
            .first()
        )

        daily_limit = rule.daily_limit if rule else DEFAULT_DAILY_LIMIT
        limit_per_tx = rule.limit_per_tx if rule else DEFAULT_LIMIT_PER_TX

        today = datetime.utcnow().date()
        used_today = (
            db.query(func.coalesce(func.sum(Operation.amount), 0))
            .filter(
                Operation.card_id == req.card_id,
                func.date(Operation.created_at) == today,
                Operation.status == "AUTHORIZED",
            )
            .scalar()
        )
        used_today = int(used_today or 0)
        new_used_today = used_today + req.amount
        approved = req.amount <= limit_per_tx and new_used_today <= daily_limit

        return CheckAndReserveResult(
            approved=approved,
            response_code="00" if approved else "51",
            response_message="approved" if approved else "limit exceeded",
            daily_limit=int(daily_limit),
            limit_per_tx=int(limit_per_tx),
            used_today=used_today,
            new_used_today=new_used_today,
        )
    finally:
        if close_session:
            db.close()


def call_limits_check_and_reserve_sync(
    req: CheckAndReserveRequest, db: Optional[Session] = None
) -> CheckAndReserveResult:
    """Call limits.check_and_reserve synchronously or fallback to local logic."""

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

    return evaluate_limits_locally(req, db=db)
