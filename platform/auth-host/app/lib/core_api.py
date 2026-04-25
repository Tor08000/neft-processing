from __future__ import annotations

import httpx
from fastapi import HTTPException

from neft_shared.logging_setup import get_logger

from app.settings import CORE_API
from app.schemas import TerminalAuthRequest, TerminalCaptureRequest

logger = get_logger(__name__)


def _core_root_url() -> str:
    normalized = CORE_API.rstrip("/")
    for suffix in ("/api/core/v1", "/api/v1", "/api/core", "/api"):
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)] or normalized
    return normalized


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


async def emit_admin_user_audit_via_core_api(
    *,
    admin_bearer_token: str,
    action: str,
    user_id: str,
    before: dict | None,
    after: dict | None,
    reason: str | None,
    correlation_id: str | None,
    request_id: str | None = None,
    trace_id: str | None = None,
) -> dict:
    url = f"{_core_root_url()}/api/internal/admin/audit/users"
    headers = {
        "Authorization": admin_bearer_token,
        "Content-Type": "application/json",
    }
    if request_id:
        headers["x-request-id"] = request_id
    if trace_id:
        headers["x-trace-id"] = trace_id

    payload = {
        "action": action,
        "user_id": user_id,
        "before": before,
        "after": after,
        "reason": reason,
        "correlation_id": correlation_id,
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning(
            "Core API admin-user audit write failed",
            extra={
                "reason": "request_error",
                "action": action,
                "user_id": user_id,
                "correlation_id": correlation_id,
            },
        )
        raise HTTPException(status_code=503, detail="core_audit_unavailable") from exc

    if response.status_code >= 400:
        detail = _extract_detail(response)
        logger.warning(
            "Core API admin-user audit rejected",
            extra={
                "status_code": response.status_code,
                "detail": detail,
                "action": action,
                "user_id": user_id,
                "correlation_id": correlation_id,
            },
        )
        raise HTTPException(status_code=503, detail="core_audit_rejected")

    return response.json()


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
