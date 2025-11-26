from __future__ import annotations

from fastapi import APIRouter, HTTPException

from neft_shared.logging_setup import get_logger

from app.lib.core_api import proxy_terminal_auth
from app.schemas import TerminalAuthRequest, TerminalAuthResponse

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
