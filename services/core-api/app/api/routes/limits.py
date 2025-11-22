# services/core-api/app/api/routes/limits.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import os
from typing import Any, Dict, Optional

from celery import Celery
from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

# ---------- Celery-клиент для core-api ----------

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
RESULT_URL = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

celery = Celery(
    "neft-core-api",
    broker=BROKER_URL,
    backend=RESULT_URL,
)

# ---------- Pydantic-схемы ----------


class LimitsProfile(BaseModel):
    """
    Профиль клиента для расчёта лимитов.
    Все поля опциональны, можно передавать только то, что есть.
    """
    risk_score: Optional[float] = None
    avg_monthly_turnover: Optional[int] = None
    has_overdue: Optional[bool] = None


class LimitsRecalcRequest(BaseModel):
    profile: Optional[LimitsProfile] = None


# ---------- Router ----------

router = APIRouter(
    prefix="/limits",
    tags=["limits"],
)


def _send_limits_task(
    task_name: str,
    *args: Any,
    wait: bool = False,
    timeout: float = 10.0,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Универсальная обвязка для вызова задач лимитов:
    - limits.recalc_for_client
    - limits.recalc_all
    и т.д.
    """
    async_result = celery.send_task(task_name, args=args, kwargs=kwargs)

    if not wait:
        return {"task_id": async_result.id}

    try:
        result = async_result.get(timeout=timeout)
    except Exception as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Task '{task_name}' timeout or error: {exc}",
        )

    return {
        "task_id": async_result.id,
        "result": result,
    }


@router.post("/recalc/{client_id}")
def recalc_limits_for_client(
    client_id: str,
    body: LimitsRecalcRequest = Body(default_factory=LimitsRecalcRequest),
    wait: bool = Query(
        False,
        description="Если true — дождаться результата Celery-задачи",
    ),
    timeout: float = Query(
        10.0,
        description="Таймаут ожидания результата задачи (секунды)",
    ),
) -> Dict[str, Any]:
    """
    Запустить пересчёт лимитов для одного клиента.

    POST /api/v1/limits/recalc/CLIENT-123
    {
      "profile": {
        "risk_score": 0.3,
        "avg_monthly_turnover": 3000000,
        "has_overdue": false
      }
    }

    Параметр ?wait=true — дождаться результата от Celery.
    """
    profile_dict: Dict[str, Any] = {}
    if body.profile is not None:
        profile_dict = body.profile.dict(exclude_none=True)

    return _send_limits_task(
        "limits.recalc_for_client",
        client_id,
        profile=profile_dict,
        wait=wait,
        timeout=timeout,
    )
