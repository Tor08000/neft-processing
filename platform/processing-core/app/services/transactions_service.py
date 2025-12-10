from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from neft_shared.logging_setup import get_logger

from app import services
from app.services import risk_adapter
from app.models.card import Card
from app.models.client import Client
from app.models.merchant import Merchant
from app.models.operation import Operation, OperationStatus, OperationType, RiskResult as RiskLevel
from app.models.terminal import Terminal
from app.schemas.operations import OperationSchema
from app.services.limits import CheckAndReserveRequest, evaluate_limits_locally
from app.services.risk_adapter import (
    OperationContext,
    RiskDecisionLevel,
    RiskEvaluation,
    evaluate_risk_sync,
)

call_risk_engine_sync = evaluate_risk_sync

logger = get_logger(__name__)


class TransactionException(Exception):
    """Base transaction exception."""


class InvalidOperationState(TransactionException):
    pass


class AmountExceeded(TransactionException):
    pass


RISK_ENGINE_OVERRIDE = None


def _evaluate_risk(context: OperationContext, db=None) -> RiskEvaluation:
    override = globals().get("RISK_ENGINE_OVERRIDE")
    if callable(override):
        return override(context)

    service_override = getattr(services, "call_risk_engine_override", None)
    if callable(service_override):
        return service_override(context)

    engine_func = globals().get("call_risk_engine_sync", evaluate_risk_sync)
    try:
        result = engine_func(context, db=db)
    except TypeError:
        result = engine_func(context)

    if isinstance(result, risk_adapter.RiskEvaluation):
        return result
    if isinstance(result, risk_adapter.RiskResult):
        legacy_decision = risk_adapter.RiskDecision(
            level=risk_adapter._normalize_level(result.risk_result),
            rules_fired=result.flags.get("rules", []),
            reason_codes=list(result.reasons),
        )
        return risk_adapter.RiskEvaluation(
            decision=legacy_decision,
            score=result.risk_score,
            source=result.source,
            flags=result.flags,
        )
    if isinstance(result, tuple) and len(result) >= 3:
        legacy_level, legacy_score, legacy_payload = result
        level_value = legacy_level.value if hasattr(legacy_level, "value") else str(legacy_level)
        decision_level = risk_adapter._normalize_level(level_value)
        decision = risk_adapter.RiskDecision(
            level=decision_level,
            rules_fired=list(legacy_payload.get("rules", [])),
            reason_codes=list(legacy_payload.get("reasons", [])),
        )
        return risk_adapter.RiskEvaluation(
            decision=decision,
            score=legacy_score,
            source=legacy_payload.get("source", "LEGACY"),
            flags=legacy_payload,
        )

    raise ValueError("Unsupported risk engine result")


def _to_risk_level(value: str | RiskLevel | RiskDecisionLevel | None) -> RiskLevel:
    if isinstance(value, RiskLevel):
        return value
    if isinstance(value, RiskDecisionLevel):
        if value == RiskDecisionLevel.HARD_DECLINE:
            return RiskLevel.BLOCK
        return RiskLevel.__members__.get(value.value, RiskLevel.MEDIUM)
    if not value:
        return RiskLevel.MEDIUM
    normalized = str(value).upper()
    if normalized == RiskDecisionLevel.HARD_DECLINE.value:
        return RiskLevel.BLOCK
    return RiskLevel.__members__.get(normalized, RiskLevel.MEDIUM)


def _fetch_operation_by_ext_id(db: Session, ext_operation_id: str) -> Operation | None:
    return (
        db.query(Operation)
        .filter(Operation.ext_operation_id == ext_operation_id)
        .order_by(Operation.created_at.desc())
        .first()
    )


def _validate_references(
    db: Session, *, client_id: str, card_id: str, terminal_id: str, merchant_id: str
):
    try:
        client_uuid = UUID(str(client_id))
    except Exception:
        raise InvalidOperationState("CLIENT_INACTIVE")

    client = db.query(Client).filter(Client.id == client_uuid).first()
    if client is None or client.status != "ACTIVE":
        raise InvalidOperationState("CLIENT_INACTIVE")

    card = db.query(Card).filter(Card.id == card_id, Card.client_id == client_id).first()
    if card is None or card.status not in {"ACTIVE", "ENABLED"}:
        raise InvalidOperationState("CARD_BLOCKED")

    terminal = db.query(Terminal).filter(Terminal.id == terminal_id).first()
    if terminal is None or terminal.status != "ACTIVE":
        raise InvalidOperationState("TERMINAL_INACTIVE")

    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if merchant is None or merchant.status != "ACTIVE":
        raise InvalidOperationState("MERCHANT_INACTIVE")


def decline_operation(
    db: Session,
    *,
    ext_operation_id: str,
    reason: str,
    amount: int,
    currency: str,
    client_id: str,
    card_id: str,
    terminal_id: str,
    merchant_id: str,
    product_id: str | None = None,
    product_type: str | None = None,
    limit_payload: dict | None = None,
    risk_payload: dict | None = None,
    risk_result: RiskResult | None = None,
) -> Operation:
    existing = _fetch_operation_by_ext_id(db, ext_operation_id)
    if existing:
        return existing

    op = Operation(
        ext_operation_id=ext_operation_id,
        operation_id=ext_operation_id,
        operation_type=OperationType.DECLINE,
        status=OperationStatus.DECLINED,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        client_id=client_id,
        card_id=card_id,
        product_id=product_id,
        product_type=product_type,
        amount=amount,
        currency=currency,
        authorized=False,
        response_code=reason,
        response_message=reason,
        limit_check_result=limit_payload,
        risk_payload=risk_payload,
        risk_result=risk_result,
    )
    db.add(op)
    db.commit()
    db.refresh(op)
    try:
        services.audit_log(db, "system", "TX_DECLINE", op.operation_id, {"reason": reason})
    except Exception:  # pragma: no cover - best effort
        logger.exception("Failed to store audit log for decline")
    return op


def authorize_operation(
    db: Session,
    *,
    client_id: str,
    card_id: str,
    terminal_id: str,
    merchant_id: str,
    product_id: str | None,
    product_type: str | None,
    amount: int,
    currency: str,
    ext_operation_id: str,
    quantity: float | None = None,
    unit_price: float | None = None,
    mcc: str | None = None,
    product_category: str | None = None,
    tx_type: str | None = None,
    client_group_id: str | None = None,
    card_group_id: str | None = None,
) -> Operation:
    existing = _fetch_operation_by_ext_id(db, ext_operation_id)
    if existing:
        return existing

    try:
        _validate_references(
            db,
            client_id=client_id,
            card_id=card_id,
            terminal_id=terminal_id,
            merchant_id=merchant_id,
        )
    except InvalidOperationState as exc:
        return decline_operation(
            db,
            ext_operation_id=ext_operation_id,
            reason=str(exc),
            amount=amount,
            currency=currency,
            client_id=client_id,
            card_id=card_id,
            terminal_id=terminal_id,
            merchant_id=merchant_id,
            product_id=product_id,
            product_type=product_type,
        )

    limits_request = CheckAndReserveRequest(
        client_id=client_id,
        card_id=card_id,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        amount=amount,
        currency=currency,
        product_category=product_category,
        product_type=product_type,
        mcc=mcc,
        tx_type=tx_type,
        client_group_id=client_group_id,
        card_group_id=card_group_id,
    )
    limit_result = evaluate_limits_locally(limits_request, db=db)
    if not limit_result.approved:
        return decline_operation(
            db,
            ext_operation_id=ext_operation_id,
            reason="LIMIT_EXCEEDED",
            amount=amount,
            currency=currency,
            client_id=client_id,
            card_id=card_id,
            terminal_id=terminal_id,
            merchant_id=merchant_id,
            product_id=product_id,
            product_type=product_type,
            limit_payload=limit_result.model_dump(),
        )

    risk_context = OperationContext(
        client_id=client_id,
        card_id=card_id,
        terminal_id=terminal_id,
        merchant_id=merchant_id,
        product_id=product_id,
        product_type=product_type,
        amount=amount,
        currency=currency,
        quantity=quantity,
        unit_price=unit_price,
        product_category=product_category,
        mcc=mcc,
        tx_type=tx_type,
        created_at=datetime.now(timezone.utc),
        metadata={"client_group_id": client_group_id, "card_group_id": card_group_id},
    )
    risk_evaluation = _evaluate_risk(risk_context, db=db)
    risk_level = _to_risk_level(risk_evaluation.decision.level)

    strict_high = os.getenv("RISK_HIGH_STRICT_MODE", "false").lower() in {"1", "true", "yes"}

    if risk_evaluation.decision.level == RiskDecisionLevel.HARD_DECLINE:
        return decline_operation(
            db,
            ext_operation_id=ext_operation_id,
            reason="RISK_HARD_DECLINE",
            amount=amount,
            currency=currency,
            client_id=client_id,
            card_id=card_id,
            terminal_id=terminal_id,
            merchant_id=merchant_id,
            product_id=product_id,
            product_type=product_type,
            limit_payload=limit_result.model_dump(),
            risk_payload=risk_evaluation.to_payload(),
            risk_result=_to_risk_level(risk_evaluation.decision.level),
        )

    if strict_high and risk_level == RiskLevel.HIGH:
        return decline_operation(
            db,
            ext_operation_id=ext_operation_id,
            reason="RISK_HIGH",
            amount=amount,
            currency=currency,
            client_id=client_id,
            card_id=card_id,
            terminal_id=terminal_id,
            merchant_id=merchant_id,
            product_id=product_id,
            product_type=product_type,
            limit_payload=limit_result.model_dump(),
            risk_payload=risk_evaluation.to_payload(),
            risk_result=risk_level,
        )

    risk_payload = risk_evaluation.to_payload()

    operation = Operation(
        id=None,
        ext_operation_id=ext_operation_id,
        operation_id=ext_operation_id,
        operation_type=OperationType.AUTH,
        status=OperationStatus.AUTHORIZED,
        merchant_id=merchant_id,
        terminal_id=terminal_id,
        client_id=client_id,
        card_id=card_id,
        product_id=product_id,
        amount=amount,
        amount_settled=0,
        currency=currency,
        product_type=product_type,
        quantity=quantity,
        unit_price=unit_price,
        captured_amount=0,
        refunded_amount=0,
        daily_limit=limit_result.daily_limit,
        limit_per_tx=limit_result.limit_per_tx,
        used_today=limit_result.used_today,
        new_used_today=limit_result.new_used_today,
        limit_profile_id=limit_result.applied_rule_id,
        limit_check_result=limit_result.model_dump(),
        authorized=True,
        response_code="00",
        response_message="APPROVED",
        auth_code=str(uuid4())[:6],
        mcc=mcc,
        product_category=product_category,
        tx_type=tx_type,
        risk_score=risk_evaluation.score,
        risk_result=risk_level,
        risk_payload=risk_payload,
    )
    db.add(operation)
    db.commit()
    db.refresh(operation)
    try:
        services.audit_log(
            db,
            "system",
            "TX_AUTH",
            operation.operation_id,
            {
                "limit": limit_result.model_dump(),
                "risk": risk_payload,
                "risk_result": risk_level.value,
            },
        )
    except Exception:  # pragma: no cover
        logger.exception("Failed to audit auth operation")
    return operation


def commit_operation(
    db: Session,
    *,
    operation_id: str,
    amount: Optional[int] = None,
    quantity: Optional[float] = None,
) -> Operation:
    operation = _fetch_operation_by_ext_id(db, operation_id)
    if operation is None:
        raise InvalidOperationState("OPERATION_NOT_FOUND")
    if operation.status not in {OperationStatus.AUTHORIZED, OperationStatus.HELD}:
        raise InvalidOperationState("INVALID_STATE")

    commit_amount = amount if amount is not None else operation.amount
    if commit_amount <= 0 or commit_amount > operation.amount:
        raise AmountExceeded("COMMIT_AMOUNT_INVALID")

    operation.amount_settled = commit_amount
    operation.status = OperationStatus.COMPLETED
    if quantity is not None:
        operation.quantity = quantity
    db.add(operation)
    db.commit()
    db.refresh(operation)
    try:
        services.audit_log(db, "system", "TX_COMMIT", operation.operation_id, {"amount": commit_amount})
    except Exception:  # pragma: no cover
        logger.exception("Failed to audit commit operation")
    return operation


def reverse_operation(db: Session, *, operation_id: str, reason: str | None = None) -> Operation:
    operation = _fetch_operation_by_ext_id(db, operation_id)
    if operation is None:
        raise InvalidOperationState("OPERATION_NOT_FOUND")
    if operation.status not in {OperationStatus.AUTHORIZED, OperationStatus.HELD}:
        raise InvalidOperationState("INVALID_STATE")

    operation.status = OperationStatus.REVERSED
    operation.operation_type = OperationType.REVERSE
    operation.reason = reason
    db.add(operation)
    db.commit()
    db.refresh(operation)
    try:
        services.audit_log(db, "system", "TX_REVERSE", operation.operation_id, {"reason": reason})
    except Exception:  # pragma: no cover
        logger.exception("Failed to audit reverse operation")
    return operation


def refund_operation(
    db: Session,
    *,
    original_operation_id: str,
    amount: int,
    reason: str | None = None,
) -> Operation:
    parent = _fetch_operation_by_ext_id(db, original_operation_id)
    if parent is None:
        raise InvalidOperationState("OPERATION_NOT_FOUND")
    if parent.status not in {OperationStatus.COMPLETED}:
        raise InvalidOperationState("INVALID_STATE")

    refunded_total = (
        db.query(Operation)
        .filter(
            Operation.parent_operation_id == parent.operation_id,
            Operation.operation_type == OperationType.REFUND,
        )
        .with_entities(Operation.amount)
        .all()
    )
    refunded_sum = sum(row[0] for row in refunded_total)
    if refunded_sum + amount > (parent.amount_settled or parent.amount):
        raise AmountExceeded("REFUND_TOO_LARGE")

    refund_ext_id = str(uuid4())
    refund_op = Operation(
        ext_operation_id=refund_ext_id,
        operation_id=refund_ext_id,
        operation_type=OperationType.REFUND,
        status=OperationStatus.REFUNDED,
        merchant_id=parent.merchant_id,
        terminal_id=parent.terminal_id,
        client_id=parent.client_id,
        card_id=parent.card_id,
        product_id=parent.product_id,
        amount=amount,
        amount_settled=amount,
        currency=parent.currency,
        product_type=parent.product_type,
        parent_operation_id=parent.operation_id,
        response_code="00",
        response_message="REFUNDED",
        reason=reason,
        mcc=parent.mcc,
        product_category=parent.product_category,
        tx_type=parent.tx_type,
        risk_result=parent.risk_result,
        risk_score=parent.risk_score,
        risk_payload=parent.risk_payload,
    )
    db.add(refund_op)
    db.commit()
    db.refresh(refund_op)
    try:
        services.audit_log(
            db,
            "system",
            "TX_REFUND",
            refund_op.operation_id,
            {"amount": amount, "reason": reason, "parent": parent.operation_id},
        )
    except Exception:  # pragma: no cover
        logger.exception("Failed to audit refund operation")
    return refund_op


def serialize_operation(op: Operation) -> OperationSchema:
    return OperationSchema.from_orm(op)
