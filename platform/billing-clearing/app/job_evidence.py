from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from neft_shared.logging_setup import get_logger
from neft_shared.settings import get_settings

logger = get_logger(__name__)

_ENGINE: Engine | None = None


def _get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    settings = get_settings()
    connect_args: dict[str, Any] = {"prepare_threshold": 0}
    schema = os.getenv("NEFT_DB_SCHEMA", "public")
    if settings.database_url.startswith("postgresql"):
        connect_args["options"] = f"-c search_path={schema}"

    _ENGINE = create_engine(
        settings.database_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    return _ENGINE


def _ensure_tables(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS scheduler_job_runs (
                    id VARCHAR(36) PRIMARY KEY,
                    job_name VARCHAR(255) NOT NULL,
                    scheduled_at TIMESTAMP WITH TIME ZONE NULL,
                    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    finished_at TIMESTAMP WITH TIME ZONE NULL,
                    status VARCHAR(32) NOT NULL,
                    error TEXT NULL,
                    celery_task_id VARCHAR(255) NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS scheduler_state (
                    id VARCHAR(64) PRIMARY KEY,
                    schedule_task_count INTEGER NOT NULL DEFAULT 0,
                    schedule_loaded_at TIMESTAMP WITH TIME ZONE NULL,
                    last_heartbeat_at TIMESTAMP WITH TIME ZONE NULL
                )
                """
            )
        )


def _safe_execute(callable_fn, context: str) -> None:
    try:
        callable_fn()
    except Exception as exc:
        logger.warning("Job evidence write skipped (%s): %s", context, exc)


def record_job_start(
    job_name: str,
    scheduled_at: datetime | None,
    celery_task_id: str | None,
) -> str | None:
    engine = _get_engine()

    def _write() -> None:
        _ensure_tables(engine)
        run_id = str(uuid4())
        now = datetime.now(timezone.utc)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO scheduler_job_runs (
                        id, job_name, scheduled_at, started_at, status, celery_task_id
                    ) VALUES (:id, :job_name, :scheduled_at, :started_at, :status, :celery_task_id)
                    """
                ),
                {
                    "id": run_id,
                    "job_name": job_name,
                    "scheduled_at": scheduled_at,
                    "started_at": now,
                    "status": "STARTED",
                    "celery_task_id": celery_task_id,
                },
            )

        nonlocal_holder["run_id"] = run_id

    nonlocal_holder: dict[str, str] = {}
    _safe_execute(_write, f"record_job_start:{job_name}")
    return nonlocal_holder.get("run_id")


def record_job_finish(run_id: str | None, status: str, error: str | None = None) -> None:
    if not run_id:
        return
    engine = _get_engine()

    def _write() -> None:
        _ensure_tables(engine)
        now = datetime.now(timezone.utc)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE scheduler_job_runs
                    SET finished_at = :finished_at,
                        status = :status,
                        error = :error
                    WHERE id = :id
                    """
                ),
                {
                    "id": run_id,
                    "finished_at": now,
                    "status": status,
                    "error": error,
                },
            )

    _safe_execute(_write, f"record_job_finish:{run_id}")


def record_schedule_loaded(task_count: int) -> None:
    engine = _get_engine()

    def _write() -> None:
        _ensure_tables(engine)
        now = datetime.now(timezone.utc)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO scheduler_state (
                        id, schedule_task_count, schedule_loaded_at, last_heartbeat_at
                    ) VALUES (:id, :count, :now, :now)
                    ON CONFLICT(id) DO UPDATE SET
                        schedule_task_count = excluded.schedule_task_count,
                        schedule_loaded_at = excluded.schedule_loaded_at,
                        last_heartbeat_at = COALESCE(scheduler_state.last_heartbeat_at, excluded.last_heartbeat_at)
                    """
                ),
                {"id": "beat", "count": task_count, "now": now},
            )

    _safe_execute(_write, "record_schedule_loaded")


def record_scheduler_heartbeat() -> None:
    engine = _get_engine()

    def _write() -> None:
        _ensure_tables(engine)
        now = datetime.now(timezone.utc)
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO scheduler_state (
                        id, schedule_task_count, schedule_loaded_at, last_heartbeat_at
                    ) VALUES (:id, 0, NULL, :now)
                    ON CONFLICT(id) DO UPDATE SET
                        last_heartbeat_at = excluded.last_heartbeat_at,
                        schedule_task_count = scheduler_state.schedule_task_count,
                        schedule_loaded_at = scheduler_state.schedule_loaded_at
                    """
                ),
                {"id": "beat", "now": now},
            )

    _safe_execute(_write, "record_scheduler_heartbeat")


def reset_engine() -> None:
    global _ENGINE
    _ENGINE = None
