from __future__ import annotations

import sys
import types

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

pytest.importorskip("neft_integration_hub")


class _Metric:
    def labels(self, *args, **kwargs):
        return self

    def inc(self, *args, **kwargs):
        return None

    def set(self, *args, **kwargs):
        return None

    def observe(self, *args, **kwargs):
        return None


if "prometheus_client" not in sys.modules:
    sys.modules["prometheus_client"] = types.SimpleNamespace(
        CONTENT_TYPE_LATEST="text/plain",
        Counter=lambda *args, **kwargs: _Metric(),
        Gauge=lambda *args, **kwargs: _Metric(),
        Histogram=lambda *args, **kwargs: _Metric(),
        generate_latest=lambda: b"",
    )

import neft_integration_hub.main as main_module
from neft_integration_hub.models import EdoDocument, EdoStubDocument
from neft_integration_hub.providers.base import ProviderStatus
from neft_integration_hub.tests._db import EDO_TABLES, make_sqlite_session_factory


def _make_session_factory() -> sessionmaker[Session]:
    return make_sqlite_session_factory(*EDO_TABLES, static_pool=True)


@pytest.fixture()
def db_session_factory():
    testing_session_local = _make_session_factory()

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[main_module.get_db] = override_get_db
    object.__setattr__(main_module.settings, "app_env", "dev")
    object.__setattr__(main_module.settings, "use_stub_edo", False)
    object.__setattr__(main_module.settings, "diadok_mode", "mock")
    try:
        yield testing_session_local
    finally:
        main_module.app.dependency_overrides.clear()


class _FakeProvider:
    def send(self, document_bytes: bytes, meta: dict) -> str:
        return "provider-message-1"

    def poll(self, provider_message_id: str) -> ProviderStatus:
        return ProviderStatus(status="SIGNED_BY_COUNTERPARTY", provider_document_id="provider-doc-1")

    def download_signed(self, provider_message_id: str):
        return None


class _FakeRegistry:
    def get(self, provider: str):
        assert provider == "DIADOK"
        return _FakeProvider()


class _FakeSbisRegistry:
    def get(self, provider: str):
        assert provider == "SBIS"
        return _FakeProvider()


def _payload() -> dict:
    return {
        "idempotency_key": "doc:1:v1",
        "provider": "diadok",
        "document": {
            "document_id": "11111111-1111-1111-1111-111111111111",
            "client_id": "client-a",
            "title": "doc",
            "category": "closing",
            "files": [
                {
                    "storage_key": "client/client-a/documents/111/file.pdf",
                    "filename": "file.pdf",
                    "sha256": "abc",
                    "mime": "application/pdf",
                    "size": 1,
                }
            ],
            "meta": {"counterparty_inn": "7700000000"},
        },
    }


def test_internal_edo_send_uses_real_document_path(db_session_factory, monkeypatch):
    monkeypatch.setattr("neft_integration_hub.services.edo_service._load_artifact_bytes", lambda *_args, **_kwargs: b"payload")
    monkeypatch.setattr("neft_integration_hub.services.edo_service.get_registry", lambda: _FakeRegistry())

    with TestClient(main_module.app) as client:
        resp = client.post("/api/int/v1/edo/send", json=_payload())

    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "diadok"
    assert body["provider_mode"] == "mock"
    assert body["edo_status"] == "SENT"
    assert body["retrying"] is False

    with db_session_factory() as db:
        assert db.query(EdoDocument).count() == 1
        assert db.query(EdoStubDocument).count() == 0


def test_internal_edo_status_maps_real_provider_state(db_session_factory, monkeypatch):
    monkeypatch.setattr("neft_integration_hub.services.edo_service._load_artifact_bytes", lambda *_args, **_kwargs: b"payload")
    monkeypatch.setattr("neft_integration_hub.services.edo_service.get_registry", lambda: _FakeRegistry())

    with TestClient(main_module.app) as client:
        send_resp = client.post("/api/int/v1/edo/send", json=_payload())
        edo_message_id = send_resp.json()["edo_message_id"]
        status_resp = client.get(f"/api/int/v1/edo/{edo_message_id}/status", params={"provider": "diadok"})

    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["edo_message_id"] == edo_message_id
    assert body["edo_status"] == "SIGNED"
    assert body["provider_status_raw"]["status"] == "SIGNED_BY_COUNTERPARTY"
    assert body["provider_status_raw"]["provider_mode"] == "mock"


def test_internal_edo_send_rejects_mock_provider_name(db_session_factory):
    payload = _payload()
    payload["provider"] = "mock"

    with TestClient(main_module.app) as client:
        resp = client.post("/api/int/v1/edo/send", json=payload)

    assert resp.status_code == 422
    assert resp.json()["detail"] == "edo_provider_not_configured"


def test_internal_edo_send_supports_sbis_sandbox_provider(db_session_factory, monkeypatch):
    payload = _payload()
    payload["provider"] = "sbis"
    object.__setattr__(main_module.settings, "sbis_mode", "sandbox")
    monkeypatch.setattr("neft_integration_hub.services.edo_service._load_artifact_bytes", lambda *_args, **_kwargs: b"payload")
    monkeypatch.setattr("neft_integration_hub.services.edo_service.get_registry", lambda: _FakeSbisRegistry())

    with TestClient(main_module.app) as client:
        resp = client.post("/api/int/v1/edo/send", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "sbis"
    assert body["provider_mode"] == "sandbox"
    assert body["edo_status"] == "SENT"


def test_internal_edo_send_fails_fast_when_provider_is_disabled(db_session_factory, monkeypatch):
    from neft_integration_hub.providers.diadok import UnavailableDiadokProvider

    class _DisabledRegistry:
        def get(self, provider: str):
            assert provider == "DIADOK"
            return UnavailableDiadokProvider("disabled")

    object.__setattr__(main_module.settings, "diadok_mode", "disabled")
    monkeypatch.setattr("neft_integration_hub.services.edo_service._load_artifact_bytes", lambda *_args, **_kwargs: b"payload")
    monkeypatch.setattr("neft_integration_hub.services.edo_service.get_registry", lambda: _DisabledRegistry())

    with TestClient(main_module.app) as client:
        resp = client.post("/api/int/v1/edo/send", json=_payload())

    assert resp.status_code == 503
    assert resp.json()["detail"] == {
        "category": "degraded",
        "error": "diadok_disabled",
        "message": "DIADOK provider is disabled",
        "provider": "diadok",
        "mode": "disabled",
        "retryable": False,
    }
