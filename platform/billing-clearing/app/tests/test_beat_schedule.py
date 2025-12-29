from __future__ import annotations

from app.celery_app import celery_app


def test_beat_schedule_is_loaded() -> None:
    schedule = celery_app.conf.beat_schedule or {}
    assert schedule, "Beat schedule should not be empty"
    assert "billing-daily-summaries" in schedule
    assert "clearing-daily-batch" in schedule
