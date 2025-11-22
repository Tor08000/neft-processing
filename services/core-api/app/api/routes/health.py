from fastapi import APIRouter
from celery import Celery
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Simple health check")
async def health_root():
    """
    Простой health-check для Docker: не трогает Celery, просто возвращает OK.
    """
    return {"status": "ok"}


@router.get("/ping", summary="Health check with Celery")
async def health_ping():
    """
    Расширенный health-check: логирование + базовая проверка.
    """
    logger.info("health_ping called")
    return {"status": "ok"}
