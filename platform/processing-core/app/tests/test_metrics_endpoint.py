from fastapi.testclient import TestClient

from app import main
from app.main import app
from app.services.event_outbox_metrics import load_event_outbox_metrics
from app.services.audit_metrics import metrics as audit_metrics
from app.services.billing_metrics import metrics as billing_metrics


def test_metrics_endpoint_returns_prometheus_text():
    billing_metrics.reset()
    billing_metrics.mark_generated()
    audit_metrics.reset()
    audit_metrics.mark_event("partner_legal_status_changed")

    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "core_api_up 1" in body
    assert "core_api_billing_generated_total 1" in body
    assert 'core_api_audit_events_total{event_type="partner_legal_status_changed"} 1' in body
    assert "event_type='partner_legal_status_changed'" not in body
    assert "event_outbox_pending_total" in body


def test_metric_alias_is_supported():
    billing_metrics.reset()
    billing_metrics.mark_generated()

    client = TestClient(app)
    response = client.get("/metric")

    assert response.status_code == 200
    assert "core_api_billing_generated_total 1" in response.text


def test_queue_metrics_uses_schema_qualified_tables(monkeypatch):
    class _Result:
        def __init__(self, value):
            self._value = value

        def scalar(self):
            return self._value

    class _Dialect:
        name = "postgresql"

    class _Bind:
        dialect = _Dialect()

    class _Session:
        def __init__(self):
            self.calls: list[str] = []
            self.values = [_Result(2), _Result(None)]

        def get_bind(self):
            return _Bind()

        def execute(self, statement, params=None):
            self.calls.append(str(statement))
            return self.values.pop(0)

        def close(self):
            pass

    session = _Session()
    monkeypatch.setattr(main, "get_sessionmaker", lambda: lambda: session)
    monkeypatch.setattr(main, "_metrics_table_exists", lambda db, table_name: True)

    lines = main._queue_metrics()

    assert "email_outbox_backlog 2" in lines
    assert any('"processing_core"."email_outbox"' in call for call in session.calls)
    assert any('"processing_core"."export_jobs"' in call for call in session.calls)


def test_queue_metrics_returns_zero_when_optional_tables_missing(monkeypatch):
    class _Dialect:
        name = "postgresql"

    class _Bind:
        dialect = _Dialect()

    class _Session:
        def get_bind(self):
            return _Bind()

        def execute(self, statement, params=None):  # pragma: no cover - should not query missing tables
            raise AssertionError("optional metrics table should not be queried")

        def close(self):
            pass

    session = _Session()
    monkeypatch.setattr(main, "get_sessionmaker", lambda: lambda: session)
    monkeypatch.setattr(main, "_metrics_table_exists", lambda db, table_name: False)

    lines = main._queue_metrics()

    assert "email_outbox_backlog 0" in lines
    assert "export_jobs_running_age_seconds 0.0" in lines


def test_event_outbox_metrics_returns_zero_when_table_missing(monkeypatch):
    class _Session:
        def close(self):
            pass

    session = _Session()
    monkeypatch.setattr(main, "get_sessionmaker", lambda: lambda: session)
    monkeypatch.setattr(main, "_metrics_table_exists", lambda db, table_name: False)
    monkeypatch.setattr(
        main,
        "load_event_outbox_metrics",
        lambda db: (_ for _ in ()).throw(AssertionError("missing table should not be queried")),
    )

    lines = main._event_outbox_metrics()

    assert "event_outbox_pending_total 0" in lines
    assert "event_outbox_failed_total 0" in lines
    assert "event_outbox_published_total 0" in lines


def test_event_outbox_metrics_uses_schema_qualified_table():
    class _Result:
        def __init__(self, value):
            self._value = value

        def scalar(self):
            return self._value

    class _Dialect:
        name = "postgresql"

    class _Bind:
        dialect = _Dialect()

    class _Session:
        def __init__(self):
            self.calls: list[str] = []
            self.values = [_Result(3), _Result(1), _Result(5), _Result(8), _Result(12.5)]

        def get_bind(self):
            return _Bind()

        def execute(self, statement, params=None):
            self.calls.append(str(statement))
            return self.values.pop(0)

    session = _Session()

    snapshot = load_event_outbox_metrics(session)

    assert snapshot.pending_total == 3
    assert snapshot.failed_total == 1
    assert snapshot.published_total == 5
    assert snapshot.retry_total == 8
    assert snapshot.lag_seconds == 12.5
    assert session.calls
    assert all('"processing_core"."event_outbox"' in call for call in session.calls)
