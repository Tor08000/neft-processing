from __future__ import annotations

import httpx
from celery import shared_task

from neft_shared.logging_setup import get_logger

from ..config import settings

logger = get_logger(__name__)


def _build_client() -> httpx.Client:
    return httpx.Client(timeout=settings.http_timeout)


@shared_task(name="ai.score_transaction", bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True)
def score_transaction(self, payload: dict) -> dict:
    """Отправляет транзакцию в ai-service и возвращает результат скоринга."""

    url = f"{settings.ai_service_url}/api/v1/score"
    logger.info("AI scoring requested", extra={"extra": {"url": url, "payload": payload}})

    try:
        with _build_client() as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info("AI scoring success", extra={"extra": {"response": data}})
            return data
    except Exception as exc:  # Celery will handle retries because of autoretry_for
        logger.error("AI scoring failed", extra={"extra": {"error": str(exc)}})
        raise

