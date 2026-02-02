
import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


def _is_admin_request(request: Request) -> bool:
    return str(request.url.path).startswith(("/api/core/v1/admin", "/api/v1/admin"))


def _admin_error_payload(
    request: Request,
    *,
    error: str,
    message: str,
    required_roles: list[str] | None = None,
    error_id: str | None = None,
    reason_code: str | None = None,
) -> dict:
    payload = {
        "error": error,
        "message": message,
        "request_id": request.headers.get("x-request-id"),
    }
    if required_roles:
        payload["required_roles"] = required_roles
    if error_id:
        payload["error_id"] = error_id
    if reason_code:
        payload["reason_code"] = reason_code
    return payload

logger = logging.getLogger(__name__)


def _resolve_actor_type(request: Request) -> str | None:
    if getattr(request.state, "service_principal", None) is not None:
        return "service"
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer svc_"):
        return "service"
    if _is_admin_request(request):
        return "admin"
    return None


def add_exception_handlers(app: FastAPI):
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if _is_admin_request(request) and exc.status_code in {401, 403}:
            error = "admin_unauthorized" if exc.status_code == 401 else "admin_forbidden"
            required_roles = None
            message = exc.detail if isinstance(exc.detail, str) else None
            if isinstance(exc.detail, dict):
                message = exc.detail.get("message") or exc.detail.get("detail")
                required_roles = exc.detail.get("required_roles")
            return JSONResponse(
                status_code=exc.status_code,
                content=_admin_error_payload(
                    request,
                    error=error,
                    message=message or ("Insufficient role" if exc.status_code == 403 else "Unauthorized"),
                    required_roles=required_roles,
                ),
            )
        if isinstance(exc.detail, dict) and "detail" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            payload = dict(exc.detail)
            payload.setdefault("message", exc.detail.get("detail"))
            payload["request_id"] = payload.get("request_id") or request.headers.get("x-request-id")
            return JSONResponse(status_code=exc.status_code, content=payload)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "type": "http_error",
                    "message": exc.detail,
                },
                "meta": {
                    "correlation_id": getattr(request.state, "correlation_id", None),
                    "path": str(request.url.path),
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        if _is_admin_request(request):
            return JSONResponse(
                status_code=422,
                content=_admin_error_payload(
                    request,
                    error="admin_validation_error",
                    message="Validation failed",
                ),
            )
        return JSONResponse(
            status_code=422,
            content={
                "error": {"type": "validation_error", "message": "Validation failed", "details": exc.errors()},
                "meta": {
                    "correlation_id": getattr(request.state, "correlation_id", None),
                    "path": str(request.url.path),
                },
            },
        )

    @app.middleware("http")
    async def add_default_error_boundary(request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            error_id = getattr(exc, "error_id", None) or str(uuid4())
            reason_code = getattr(exc, "reason_code", None) or "internal_error"
            actor_type = _resolve_actor_type(request)
            logger.exception(
                "Unhandled application error",
                extra={
                    "error_id": error_id,
                    "reason_code": reason_code,
                    "path": str(request.url.path),
                    "method": request.method,
                    "actor_type": actor_type,
                },
            )
            if _is_admin_request(request):
                return JSONResponse(
                    status_code=500,
                    content=_admin_error_payload(
                        request,
                        error="admin_internal_error",
                        message="Internal Server Error",
                        required_roles=None,
                        error_id=error_id,
                        reason_code=reason_code,
                    ),
                )
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "type": "internal_error",
                        "message": "Internal Server Error",
                        "error_id": error_id,
                        "reason_code": reason_code,
                    },
                    "meta": {
                        "correlation_id": getattr(request.state, "correlation_id", None),
                        "request_id": request.headers.get("x-request-id"),
                        "path": str(request.url.path),
                    },
                },
            )
