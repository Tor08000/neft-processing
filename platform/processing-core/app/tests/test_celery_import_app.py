from __future__ import annotations

import importlib


def test_celery_app_importable(monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "memory://")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "cache+memory://")

    module = importlib.reload(importlib.import_module("app.celery_client"))

    assert hasattr(module, "celery_client")
    assert module.celery_client.main == "neft-core-api"
    assert "billing.generate_invoice_pdf" in module.celery_client.conf.task_routes
