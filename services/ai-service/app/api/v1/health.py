from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "ai-service"}


@router.get("/live")
def live():
    return {"status": "ok", "service": "ai-service"}


@router.get("/ready")
def ready():
    return {"status": "ok", "service": "ai-service"}
