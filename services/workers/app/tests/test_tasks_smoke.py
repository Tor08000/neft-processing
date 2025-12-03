from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from celery import current_app as celery_default_app

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SHARED_DIR = Path(__file__).resolve().parents[4] / "shared" / "python"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")

from app.celery_app import celery_app
from app.settings import settings
from app.tasks import ai, billing, clearing, limits, ping


@pytest.fixture(autouse=True)
def enable_eager_tasks():
    targets = [celery_app, celery_default_app]
    previous = {}

    for target in targets:
        previous[target] = {
            "task_always_eager": target.conf.task_always_eager,
            "task_eager_propagates": target.conf.task_eager_propagates,
            "task_store_eager_result": target.conf.task_store_eager_result,
            "broker_url": target.conf.broker_url,
            "result_backend": target.conf.result_backend,
        }

        target.conf.task_always_eager = True
        target.conf.task_eager_propagates = True
        target.conf.task_store_eager_result = True
        target.conf.broker_url = "memory://"
        target.conf.result_backend = "cache+memory://"
    yield
    for target in targets:
        target.conf.task_always_eager = previous[target]["task_always_eager"]
        target.conf.task_eager_propagates = previous[target]["task_eager_propagates"]
        target.conf.task_store_eager_result = previous[target]["task_store_eager_result"]
        target.conf.broker_url = previous[target]["broker_url"]
        target.conf.result_backend = previous[target]["result_backend"]


class _DummyResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:  # pragma: no cover - compatibility
        return None

    def json(self) -> dict:
        return self._payload


class _DummyClient:
    def __init__(self, response_payload: dict):
        self._payload = response_payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover - compatibility
        return False

    def post(self, url: str, json: dict) -> _DummyResponse:  # noqa: A002 - payload name
        assert "/api/v1/score" in url
        assert "client_id" in json
        return _DummyResponse(self._payload)


class _BillingRowResult:
    def __init__(self):
        self._rows = [
            {
                "op_date": date.today(),
                "merchant_id": "merchant-1",
                "total_amount": 1500,
                "operations_count": 2,
            }
        ]

    def mappings(self):
        return self._rows


class _BillingEngine:
    def begin(self):
        return _BillingConnection()


class _BillingConnection:
    def __init__(self):
        self._calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover - compatibility
        return False

    def execute(self, *_args, **_kwargs):
        self._calls += 1
        if self._calls == 1:
            return _BillingRowResult()
        return SimpleNamespace(rowcount=1)


class _ClearingScalars:
    def scalars(self):
        return ["merchant-42"]


class _ClearingMappings:
    def __init__(self):
        self._rows = [
            {"operation_id": "op-1", "amount": 200},
            {"operation_id": "op-2", "amount": 300},
        ]

    def mappings(self):
        return self._rows


class _ClearingEngine:
    def begin(self):
        return _ClearingConnection()


class _ClearingConnection:
    def __init__(self):
        self._calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover - compatibility
        return False

    def execute(self, *_args, **_kwargs):
        sql_text = str(_args[0]) if _args else ""
        if "UPDATE billing_summary" in sql_text:
            return SimpleNamespace(rowcount=1)

        self._calls += 1
        if self._calls == 1:
            return _ClearingScalars()
        if self._calls == 2:
            return _ClearingMappings()
        return SimpleNamespace(rowcount=1)


def test_ping_task_runs_eagerly():
    result = ping.delay(3)
    assert result.get(timeout=1) == {"pong": 3}


def test_ping_task_via_signature_apply():
    signature = celery_app.signature("workers.ping", kwargs={"x": 2})
    assert signature.apply().get(timeout=1) == {"pong": 2}


def test_ai_score_task(monkeypatch):
    fake_payload = {"score": 0.98, "decision": "allow"}
    monkeypatch.setattr(ai, "_build_client", lambda: _DummyClient(fake_payload))

    result = ai.score_transaction.delay({"client_id": "1", "amount": 100})

    assert result.get(timeout=1) == fake_payload


def test_limits_tasks_eager_mode():
    reserve_result = limits.check_and_reserve_limit.delay(
        client_id="client-1", card_id="card-1", amount=100
    ).get(timeout=1)

    assert reserve_result["allowed"] is True
    assert reserve_result["new_used_today"] == reserve_result["used_today"] + 100

    recalc_result = limits.recalc_limits_for_all.delay([
        {"client_id": "c-1", "profile": {"daily_limit": 5000, "per_transaction_limit": 1500}}
    ]).get(timeout=1)

    assert recalc_result["processed"] == 1
    assert recalc_result["updated"] == 1


def test_billing_and_clearing_tasks(monkeypatch):
    monkeypatch.setattr(billing, "_engine", _BillingEngine())
    monkeypatch.setattr(clearing, "_engine", _ClearingEngine())

    billing_summary = billing.build_daily_summaries.delay().get(timeout=1)
    assert billing_summary["rows"] == 1

    clearing_batch = clearing.build_daily_batch.delay().get(timeout=1)
    assert clearing_batch["batches"] == 1


def test_celery_config_hardening_defaults():
    assert celery_app.conf.worker_max_tasks_per_child == settings.worker_max_tasks_per_child
    assert celery_app.conf.worker_prefetch_multiplier == settings.worker_prefetch_multiplier
    assert celery_app.conf.task_soft_time_limit == settings.task_soft_time_limit
    assert celery_app.conf.task_time_limit == settings.task_time_limit
    assert celery_app.conf.task_default_queue == settings.task_default_queue
