from __future__ import annotations

import httpx
from fastapi import HTTPException

from neft_shared.logging_setup import get_logger

from app.config import CORE_API
from app.schemas import TerminalAuthRequest, TerminalCaptureRequest

logger = get_logger(__name__)


async def proxy_terminal_auth(payload: TerminalAuthRequest) -> dict:
    url = f"{CORE_API}/processing/terminal-auth"
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(url, json=payload.model_dump())

    if response.status_code >= 400:
        detail = _extract_detail(response)
        logger.warning(
            "Core API terminal auth failed",
            extra={
                "status_code": response.status_code,
                "detail": detail,
                "merchant_id": payload.merchant_id,
                "terminal_id": payload.terminal_id,
                "client_id": payload.client_id,
            },
        )
        raise HTTPException(status_code=response.status_code, detail=detail)

    body = response.json()
    logger.info(
        "Core API terminal auth success",
        extra={
            "merchant_id": payload.merchant_id,
            "terminal_id": payload.terminal_id,
            "client_id": payload.client_id,
            "operation_id": body.get("operation_id"),
            "status": body.get("status"),
        },
    )
    return body


def _extract_detail(response: httpx.Response) -> str:
    try:
        json_body = response.json()
        detail = json_body.get("detail")
        return detail if isinstance(detail, str) else response.text
    except Exception:
        return response.text


async def capture_operation_via_core_api(
    *, auth_operation_id: str, amount: int | None = None
) -> dict:
    payload = {"amount": amount} if amount is not None else {}
    url = f"{CORE_API}/transactions/{auth_operation_id}/capture"
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(url, json=payload)

    if response.status_code >= 400:
        detail = _extract_detail(response)
        logger.warning(
            "Core API capture failed",
            extra={
                "status_code": response.status_code,
                "detail": detail,
                "auth_operation_id": auth_operation_id,
            },
        )
        raise HTTPException(status_code=response.status_code, detail=detail)

    body = response.json()
    logger.info(
        "Core API capture success",
        extra={
            "auth_operation_id": auth_operation_id,
            "operation_id": body.get("operation_id"),
            "status": body.get("status"),
        },
    )
    return body
