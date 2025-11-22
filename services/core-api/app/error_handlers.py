
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

def add_exception_handlers(app: FastAPI):
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
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
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "error": {"type": "internal_error", "message": "Internal Server Error"},
                    "meta": {
                        "correlation_id": getattr(request.state, "correlation_id", None),
                        "path": str(request.url.path),
                    },
                },
            )
