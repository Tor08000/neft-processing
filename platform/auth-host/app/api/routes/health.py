from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.healthcheck import build_health_response
from app.schemas.auth import HealthResponse

router = APIRouter(prefix="/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    response, status_code = build_health_response()
    content = response.model_dump(exclude_none=True)
    if status_code != status.HTTP_200_OK:
        return JSONResponse(status_code=status_code, content=content)
    return JSONResponse(status_code=status_code, content=content)


@router.get("/ready", response_model=HealthResponse)
def ready() -> HealthResponse:
    response, status_code = build_health_response()
    content = response.model_dump(exclude_none=True)
    if status_code != status.HTTP_200_OK:
        return JSONResponse(status_code=status_code, content=content)
    return JSONResponse(status_code=status_code, content=content)
