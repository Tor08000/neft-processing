from fastapi.testclient import TestClient

from app.main import app
from app.services.billing_metrics import metrics as billing_metrics


def test_metrics_endpoint_returns_prometheus_text():
    billing_metrics.reset()
    billing_metrics.mark_generated()

    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "core_api_up 1" in body
    assert "core_api_billing_generated_total 1" in body
    assert "event_outbox_pending_total" in body


def test_metric_alias_is_supported():
    billing_metrics.reset()
    billing_metrics.mark_generated()

    client = TestClient(app)
    response = client.get("/metric")

    assert response.status_code == 200
    assert "core_api_billing_generated_total 1" in response.text
