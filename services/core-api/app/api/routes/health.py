# app/api/routes/health.py

import os

from anyio import to_thread
from celery import Celery
from celery.exceptions import TimeoutError as CeleryTimeoutError
from fastapi import APIRouter, HTTPException

# -----------------------------
# Celery-клиент для core-api
# -----------------------------
# Должен быть настроен ТАК ЖЕ, как у workers/beat:
#   broker: redis://redis:6379/0
#   backend: redis://redis:6379/1
#   default queue: celery
# -----------------------------

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_URL = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
DEFAULT_QUEUE = os.getenv("CELERY_DEFAULT_QUEUE", "celery")

celery_app = Celery(
    "neft-workers",
    broker=BROKER_URL,
    backend=RESULT_URL,
)

# В логах воркера видно, что default queue называется "default",
# а не "celery". Поэтому настраиваем те же значения тут.
celery_app.conf.update(
    task_default_queue=DEFAULT_QUEUE,
    task_default_exchange=DEFAULT_QUEUE,
    task_default_routing_key=DEFAULT_QUEUE,
    broker_connection_retry_on_startup=True,
)

router = APIRouter(prefix="/api/v1/health", tags=["health"])

CELERY_HEALTH_TIMEOUT = 10.0  # секунд ожидания результата от Celery


@router.get("")
async def health_root():
    """Простой health-чек самого core-api."""
    return {"status": "ok"}


@router.get("/enqueue")
async def health_enqueue(wait: bool = False):
    """
    Тест связки core-api ↔ Celery ↔ Redis ↔ workers.

    - GET /api/v1/health/enqueue
      Ставит задачу в очередь и сразу отвечает:
      {
        "task": "<task_id>",      # UUID
        "result": {"queued": true}
      }

    - GET /api/v1/health/enqueue?wait=true
      Ждёт выполнения (до CELERY_HEALTH_TIMEOUT секунд) и возвращает:
      {
        "task": "<task_id>",
        "result": {"pong": 1}
      }
    """

    # 1. Ставим задачу ping в очередь
    try:
        # Имя задачи — как в воркере / Flower: "workers.ping"
        async_result = celery_app.send_task(
            "workers.ping",
            kwargs={"x": 1},
        )
    except Exception as e:
        # Ошибка при публикации задачи в брокер
        raise HTTPException(
            status_code=500,
            detail=f"Failed to enqueue Celery task: {e}",
        )

    # Если ждать результата не нужно — сразу отвечаем
    if not wait:
        return {
            "task": async_result.id,    # тут теперь UUID, а не "ping"
            "result": {"queued": True},
        }

    # 2. Ждём выполнения результата в отдельном потоке,
    # чтобы не блокировать event-loop FastAPI
    try:
        result = await to_thread.run_sync(
            async_result.get,
            timeout=CELERY_HEALTH_TIMEOUT,
        )
        # Если всё ок — отдаём результат
        return {
            "task": async_result.id,
            "result": result,
        }

    except CeleryTimeoutError:
        # Воркеры задачу не выполнили / результат не сохранился за timeout
        raise HTTPException(
            status_code=504,
            detail=f"Celery task timeout (no worker response in {CELERY_HEALTH_TIMEOUT} seconds)",
        )

    except Exception as e:
        # Любая другая ошибка Celery/Redis
        raise HTTPException(
            status_code=500,
            detail=f"Celery error: {e}",
        )
