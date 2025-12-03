from __future__ import annotations

from fastapi import APIRouter, HTTPException

from neft_shared.logging_setup import get_logger

from app.lib.core_api import capture_operation_via_core_api, proxy_terminal_auth
from app.schemas import (
    TerminalAuthRequest,
    TerminalAuthResponse,
    TerminalCaptureRequest,
    TerminalCaptureResponse,
)

router = APIRouter(prefix="/api/v1/processing", tags=["processing"])
logger = get_logger(__name__)


@router.post("/terminal-auth", response_model=TerminalAuthResponse)
async def terminal_auth(payload: TerminalAuthRequest) -> dict:
    try:
        logger.info(
            "Proxying terminal auth request", 
            extra={
                "merchant_id": payload.merchant_id,
                "terminal_id": payload.terminal_id,
                "client_id": payload.client_id,
                "amount": payload.amount,
                "currency": payload.currency,
            },
        )
        return await proxy_terminal_auth(payload)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception(
            "Unexpected error during terminal auth proxy", 
            extra={
                "merchant_id": payload.merchant_id,
                "terminal_id": payload.terminal_id,
                "client_id": payload.client_id,
            },
        )
        raise HTTPException(status_code=502, detail="core_api_unavailable") from exc


@router.post("/terminal-capture", response_model=TerminalCaptureResponse)
async def terminal_capture(payload: TerminalCaptureRequest) -> dict:
    try:
        logger.info(
            "Proxying terminal capture request",
            extra={
                "auth_operation_id": payload.auth_operation_id,
                "amount": payload.amount,
            },
        )
        amount_minor = int(payload.amount) if payload.amount is not None else None
        body = await capture_operation_via_core_api(
            auth_operation_id=payload.auth_operation_id, amount=amount_minor
        )
        return {
            "operation_id": body.get("operation_id"),
            "status": body.get("status"),
            "approved": True,
            "response_code": "00",
            "response_message": "approved",
        }
    except HTTPException as exc:
        logger.warning(
            "Terminal capture failed", extra={"detail": exc.detail, "status": exc.status_code}
        )
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception(
            "Unexpected error during terminal capture proxy", extra={"auth_operation_id": payload.auth_operation_id}
        )
        raise HTTPException(status_code=502, detail="core_api_unavailable") from exc
