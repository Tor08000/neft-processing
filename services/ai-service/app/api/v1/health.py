# services/ai-service/app/api/v1/health.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["health"])

@router.get("/health")
def health():
    return {"status": "ok", "service": "ai-service"}
