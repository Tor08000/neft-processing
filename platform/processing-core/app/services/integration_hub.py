from __future__ import annotations

import time
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from neft_shared.logging_setup import get_logger

from app.models.card import Card
from app.models.operation import Operation, OperationStatus, RiskResult
from app.models.partner import Partner
from app.models.terminal import Terminal
from app.schemas.intake import IntakeAuthorizeRequest, IntakeResponse
from app.services import transactions_service
from app.services.integration_metrics import metrics
from app.services.integration_monitoring import log_external_request

logger = get_logger(__name__)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def validate_partner_request(db: Session, request: Request, partner_id: str) -> Partner:
    client_ip = _client_ip(request)
    return _validate_partner(db, partner_id, request.headers.get("x-partner-token"), client_ip)


def _validate_partner(db: Session, partner_id: str, token: Optional[str], client_ip: str) -> Partner:
    partner = db.query(Partner).filter(Partner.id == partner_id).first()
    if partner is None or partner.status != "active":
        metrics.mark_partner_error()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="partner_not_active")

    if not token or token != partner.token:
        metrics.mark_partner_error()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid_partner_token")

    if partner.allowed_ips and client_ip not in partner.allowed_ips:
        metrics.mark_partner_error()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ip_not_allowed")

    return partner


def _resolve_terminal(db: Session, terminal_id: str) -> Terminal:
    terminal = db.query(Terminal).filter(Terminal.id == terminal_id).first()
    if terminal is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="terminal_not_found")
    return terminal


def _resolve_card(db: Session, card_id: str) -> Card:
    card = db.query(Card).filter(Card.id == card_id).first()
    if card is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="card_not_found")
    return card


def _operation_to_response(operation: Operation) -> IntakeResponse:
    approved_statuses = {
        OperationStatus.AUTHORIZED,
        OperationStatus.APPROVED,
        OperationStatus.POSTED,
    }
    risk_code: str | None = None
    if isinstance(operation.risk_result, RiskResult):
        risk_code = operation.risk_result.value
    elif operation.response_code and operation.response_code.startswith("RISK"):
        risk_code = operation.response_code

    limit_code = operation.response_code if operation.response_code and "LIMIT" in operation.response_code else None

    return IntakeResponse(
        approved=operation.status in approved_statuses,
        operation_id=str(operation.operation_id),
        posting_status=operation.status.value,
        risk_code=risk_code,
        limit_code=limit_code,
        response_code=operation.response_code,
    )


def authorize_intake(db: Session, request: Request, payload: IntakeAuthorizeRequest) -> IntakeResponse:
    metrics.mark_request("authorize")
    partner = validate_partner_request(db, request, payload.external_partner_id)
    client_ip = _client_ip(request)

    terminal_id = payload.terminal_id or payload.azs_id
    if not terminal_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="terminal_id_required")

    logger.info(
        "intake_received",
        extra={
            "partner_id": partner.id,
            "terminal_id": terminal_id,
            "card_identifier": payload.card_identifier,
            "amount": payload.amount,
            "liters": payload.liters,
            "client_ip": client_ip,
        },
    )

    normalized_started = time.perf_counter()
    terminal = _resolve_terminal(db, terminal_id)
    card = _resolve_card(db, payload.card_identifier)

    ext_operation_id = f"{partner.id}-{uuid4()}"
    normalized_payload = {
        "client_id": str(card.client_id),
        "card_id": card.id,
        "terminal_id": terminal.id,
        "merchant_id": terminal.merchant_id,
        "product_id": payload.product_id,
        "product_type": None,
        "amount": payload.amount,
        "currency": payload.currency,
        "ext_operation_id": ext_operation_id,
        "quantity": payload.liters,
        "unit_price": None,
        "product_category": "FUEL",
        "tx_type": "PURCHASE",
    }

    logger.debug("intake_normalized", extra=normalized_payload)
    metrics.observe_normalization(time.perf_counter() - normalized_started)

    try:
        operation = transactions_service.authorize_operation(
            db,
            **normalized_payload,
            risk_evaluation=None,
            simulate_posting_error=payload.simulate_posting_error,
        )
    except transactions_service.PostingFailed:
        failed = db.query(Operation).filter(Operation.operation_id == ext_operation_id).first()
        if failed:
            metrics.mark_posting_error()
            return _operation_to_response(failed)
        metrics.mark_posting_error()
        raise

    metrics.mark_response(operation.status.value)
    latency_ms = (time.perf_counter() - normalized_started) * 1000
    metrics.observe_request_latency(partner.id, latency_ms)

    reason_category: str | None = None
    risk_code: str | None = getattr(operation.risk_result, "value", None)
    limit_code: str | None = None
    if operation.response_code and "LIMIT" in operation.response_code:
        limit_code = operation.response_code
    if risk_code:
        reason_category = "RISK"
    elif limit_code:
        reason_category = "LIMIT"
    elif operation.status in {OperationStatus.ERROR}:
        reason_category = "TECHNICAL"

    log_external_request(
        db,
        partner_id=partner.id,
        azs_id=payload.azs_id,
        terminal_id=terminal.id,
        operation_id=str(operation.operation_id),
        request_type="AUTHORIZE",
        amount=payload.amount,
        liters=payload.liters,
        currency=payload.currency,
        status="APPROVED" if operation.status in {OperationStatus.POSTED, OperationStatus.AUTHORIZED, OperationStatus.APPROVED} else "DECLINED" if operation.status == OperationStatus.DECLINED else "ERROR",
        reason_category=reason_category,
        risk_code=risk_code,
        limit_code=limit_code,
        latency_ms=latency_ms,
    )
    logger.info(
        "intake_result",
        extra={
            "partner_id": partner.id,
            "operation_id": operation.operation_id,
            "status": operation.status.value,
            "response_code": operation.response_code,
            "risk_result": getattr(operation.risk_result, "value", None),
        },
    )
    return _operation_to_response(operation)
