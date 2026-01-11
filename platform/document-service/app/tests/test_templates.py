from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main
from app.schemas import RenderRequest
from app.tests.test_service import DummyRenderer, DummyStorage


def test_list_templates() -> None:
    client = TestClient(main.app)
    response = client.get("/v1/templates")

    assert response.status_code == 200
    payload = response.json()
    assert {item["code"] for item in payload} == {
        "contract_main",
        "annex",
        "invoice",
        "act_monthly",
        "reconciliation_act",
        "closing_package_cover_letter",
    }


def test_get_template_details() -> None:
    client = TestClient(main.app)
    response = client.get("/v1/templates/contract_main")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == "contract_main"
    assert payload["schema"]["title"] == "Contract main template variables"


def test_render_template_code(monkeypatch) -> None:
    storage = DummyStorage()
    renderer = DummyRenderer()

    main.app.dependency_overrides[main.get_storage] = lambda: storage
    main.app.dependency_overrides[main.get_renderer] = lambda: renderer

    client = TestClient(main.app)
    payload = RenderRequest(
        template_code="invoice",
        variables={
            "invoice_number": "INV-1",
            "client_name": "ACME",
            "issue_date": "2024-01-15",
            "items": [
                {"description": "Service", "quantity": 1, "unit_price": 100, "amount": 100}
            ],
            "total_amount": 100,
            "currency": "RUB",
        },
        output_format="PDF",
        tenant_id=1,
        client_id="client-1",
        idempotency_key="idem-2",
        meta={"source": "tests"},
        doc_id="doc-456",
        doc_type="INVOICE",
        version=1,
    )
    response = client.post("/v1/render", json=payload.model_dump())

    assert response.status_code == 200
    body = response.json()
    assert body["template_hash"]
    assert body["schema_hash"]
    assert renderer.calls == 1
    main.app.dependency_overrides.clear()


def test_render_template_validation_error(monkeypatch) -> None:
    storage = DummyStorage()
    renderer = DummyRenderer()

    main.app.dependency_overrides[main.get_storage] = lambda: storage
    main.app.dependency_overrides[main.get_renderer] = lambda: renderer

    client = TestClient(main.app)
    payload = RenderRequest(
        template_code="invoice",
        variables={
            "invoice_number": "INV-2",
            "client_name": "ACME",
            "issue_date": "2024-01-15",
            "items": [],
            "total_amount": 100,
            "currency": "RUB",
        },
        output_format="PDF",
        tenant_id=1,
        client_id="client-1",
        idempotency_key="idem-3",
        meta={"source": "tests"},
        doc_id="doc-789",
        doc_type="INVOICE",
        version=1,
    )
    response = client.post("/v1/render", json=payload.model_dump())

    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["error"] == "schema_validation_failed"
    main.app.dependency_overrides.clear()
