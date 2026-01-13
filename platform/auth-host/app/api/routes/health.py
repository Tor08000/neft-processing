from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.healthcheck import build_health_response
from app.schemas.auth import HealthResponse

router = APIRouter(prefix="/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    response, status_code = build_health_response()
    if status_code != status.HTTP_200_OK:
        return JSONResponse(status_code=status_code, content=response.model_dump())
    return response
