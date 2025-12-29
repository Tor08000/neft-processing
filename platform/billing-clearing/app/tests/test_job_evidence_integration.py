from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from app import job_evidence
from app.tasks import billing


class _BillingRowResult:
    def mappings(self):
        return [
            {
                "op_date": date.today(),
                "merchant_id": "merchant-1",
                "total_amount": 1500,
                "operations_count": 2,
            }
        ]


class _BillingEngine:
    def begin(self):
        return _BillingConnection()


class _BillingConnection:
    def __init__(self):
        self._calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover
        return False

    def execute(self, *_args, **_kwargs):
        self._calls += 1
        if self._calls == 1:
            return _BillingRowResult()
        return SimpleNamespace(rowcount=1)


@pytest.mark.integration
def test_job_execution_evidence_written(tmp_path, monkeypatch):
    db_path = Path(tmp_path) / "scheduler_evidence.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    job_evidence.reset_engine()

    monkeypatch.setattr(billing, "_engine", _BillingEngine())

    result = billing.build_daily_summaries.apply().get()
    assert result["rows"] == 1

    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT job_name, status FROM scheduler_job_runs")
        ).mappings()
        payload = list(rows)

    assert any(
        row["job_name"] == "billing.build_daily_summaries" and row["status"] == "SUCCESS"
        for row in payload
    )
