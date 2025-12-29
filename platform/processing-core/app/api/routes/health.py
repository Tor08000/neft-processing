# app/api/routes/health.py

import os
from datetime import datetime, timezone

from anyio import to_thread
from celery import Celery
from celery.exceptions import TimeoutError as CeleryTimeoutError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.db import get_db

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

router = APIRouter(prefix="/health", tags=["health"])

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


@router.get("/scheduler")
def scheduler_health(db: Session = Depends(get_db)) -> dict:
    state = db.execute(
        text(
            """
            SELECT schedule_task_count, schedule_loaded_at, last_heartbeat_at
            FROM scheduler_state
            WHERE id = :id
            """
        ),
        {"id": "beat"},
    ).mappings().first()

    task_count = 0
    schedule_loaded_at = None
    last_heartbeat_at = None

    if state:
        task_count = state.get("schedule_task_count") or 0
        schedule_loaded_at = state.get("schedule_loaded_at")
        last_heartbeat_at = state.get("last_heartbeat_at")

    schedule_loaded = task_count > 0
    alive = False
    if last_heartbeat_at:
        now = datetime.now(timezone.utc)
        heartbeat_value = last_heartbeat_at
        if heartbeat_value.tzinfo is None:
            heartbeat_value = heartbeat_value.replace(tzinfo=timezone.utc)
        heartbeat_delta = (now - heartbeat_value).total_seconds()
        alive = heartbeat_delta <= 120

    job_names = {
        "billing": "billing.build_daily_summaries",
        "clearing": "clearing.build_daily_batch",
        "billing_finalize": "clearing.finalize_billing",
    }

    stmt = text(
        """
        SELECT job_name, MAX(finished_at) AS last_run_at
        FROM scheduler_job_runs
        WHERE job_name IN :job_names
        GROUP BY job_name
        """
    ).bindparams(bindparam("job_names", expanding=True))
    results = db.execute(stmt, {"job_names": list(job_names.values())}).mappings().all()
    last_runs = {row["job_name"]: row["last_run_at"] for row in results}

    return {
        "status": "ok" if schedule_loaded else "degraded",
        "beat": {
            "alive": alive,
            "last_heartbeat_at": last_heartbeat_at,
            "schedule_loaded_at": schedule_loaded_at,
        },
        "schedule": {"loaded": schedule_loaded, "task_count": task_count},
        "jobs": {
            "billing": {"last_run_at": last_runs.get(job_names["billing"])},
            "clearing": {"last_run_at": last_runs.get(job_names["clearing"])},
            "billing_finalize": {"last_run_at": last_runs.get(job_names["billing_finalize"])},
        },
    }
