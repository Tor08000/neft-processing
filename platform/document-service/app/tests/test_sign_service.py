from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient
import pytest

import app.main as main
from app.sign.providers.base import SignedResult, VerifyResult
from app.sign.registry import ProviderRegistry
from app.storage import StoredObjectMetadata


class DummyStorage:
    _payloads: dict[tuple[str, str], bytes] = {}
    _metadata: dict[tuple[str, str], dict[str, str]] = {}

    def __init__(self, *, bucket: str | None = None) -> None:
        self.bucket = bucket or "neft-docs"

    def ensure_bucket(self) -> None:
        return None

    def put_bytes(self, object_key: str, payload: bytes, *, content_type: str, metadata: dict[str, str] | None = None) -> None:
        DummyStorage._payloads[(self.bucket, object_key)] = payload
        DummyStorage._metadata[(self.bucket, object_key)] = metadata or {}

    def head_object(self, object_key: str):
        payload = DummyStorage._payloads.get((self.bucket, object_key))
        if payload is None:
            return None
        metadata = DummyStorage._metadata.get((self.bucket, object_key), {})
        return StoredObjectMetadata(
            bucket=self.bucket,
            object_key=object_key,
            size_bytes=len(payload),
            content_type="application/pdf",
            sha256=metadata.get("sha256"),
        )

    def get_bytes(self, object_key: str) -> bytes | None:
        return DummyStorage._payloads.get((self.bucket, object_key))


@pytest.fixture(autouse=True)
def _reset_dummy_storage() -> None:
    DummyStorage._payloads.clear()
    DummyStorage._metadata.clear()


class DummyProvider:
    def sign(self, payload: bytes, meta: dict | None = None):
        signature = f"sig:{hashlib.sha256(payload).hexdigest()}".encode("utf-8")
        return SignedResult(
            signed_bytes=payload,
            signature_bytes=signature,
            provider_request_id="req-1",
            certificate=None,
        )

    def verify(self, payload: bytes, signature: bytes, meta: dict | None = None):
        return VerifyResult(verified=True)


def _seed_input(bucket: str, object_key: str, payload: bytes) -> None:
    storage = DummyStorage(bucket=bucket)
    storage.put_bytes(object_key, payload, content_type="application/pdf", metadata={"sha256": hashlib.sha256(payload).hexdigest()})


def test_sign_happy_path(monkeypatch):
    monkeypatch.setattr(main, "S3Storage", DummyStorage)
    main.app.dependency_overrides[main.get_sign_registry] = lambda: ProviderRegistry(
        providers={"provider_x": DummyProvider()}
    )

    client = TestClient(main.app)
    input_payload = b"PDF-BYTES"
    _seed_input("in-bucket", "documents/tenant-1/INVOICE/2024/05/doc-1/v1.pdf", input_payload)

    response = client.post(
        "/v1/sign",
        json={
            "document_id": "doc-1",
            "provider": "provider_x",
            "input": {"bucket": "in-bucket", "object_key": "documents/tenant-1/INVOICE/2024/05/doc-1/v1.pdf"},
            "output": {"bucket": "out-bucket", "prefix": "documents/tenant-1/INVOICE/2024/05/doc-1"},
            "idempotency_key": "idem-1",
            "meta": {"reason": "closing"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SIGNED"
    assert body["signed"]["object_key"].endswith("v1.signed.pdf")
    assert body["signature"]["object_key"].endswith("v1.sig.p7s")

    stored_signed = DummyStorage(bucket="out-bucket").get_bytes(body["signed"]["object_key"])
    assert stored_signed == input_payload
    main.app.dependency_overrides.clear()


def test_sign_provider_failure(monkeypatch):
    class FailingProvider:
        def sign(self, payload: bytes, meta: dict | None = None):
            raise TimeoutError("timeout")

    monkeypatch.setattr(main, "S3Storage", DummyStorage)
    main.app.dependency_overrides[main.get_sign_registry] = lambda: ProviderRegistry(
        providers={"provider_x": FailingProvider()}
    )

    client = TestClient(main.app)
    input_payload = b"PDF-BYTES"
    _seed_input("in-bucket", "documents/tenant-1/INVOICE/2024/05/doc-1/v1.pdf", input_payload)

    response = client.post(
        "/v1/sign",
        json={
            "document_id": "doc-1",
            "provider": "provider_x",
            "input": {"bucket": "in-bucket", "object_key": "documents/tenant-1/INVOICE/2024/05/doc-1/v1.pdf"},
            "output": {"bucket": "out-bucket-fail", "prefix": "documents/tenant-1/INVOICE/2024/05/doc-1"},
            "idempotency_key": "idem-1",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "sign_failed"
    main.app.dependency_overrides.clear()


def test_sign_provider_degraded_returns_structured_503(monkeypatch):
    class DegradedProvider:
        def sign(self, payload: bytes, meta: dict | None = None):
            from app.sign.providers.base import SignProviderDegradedError

            raise SignProviderDegradedError(
                "Provider X transport is disabled or degraded in document-service",
                code="provider_x_degraded",
            )

    monkeypatch.setattr(main, "S3Storage", DummyStorage)
    main.app.dependency_overrides[main.get_sign_registry] = lambda: ProviderRegistry(
        providers={"provider_x": DegradedProvider()}
    )
    monkeypatch.setenv("PROVIDER_X_MODE", "degraded")

    client = TestClient(main.app)
    input_payload = b"PDF-BYTES"
    _seed_input("in-bucket", "documents/tenant-1/INVOICE/2024/05/doc-1/v1.pdf", input_payload)

    response = client.post(
        "/v1/sign",
        json={
            "document_id": "doc-1",
            "provider": "provider_x",
            "input": {"bucket": "in-bucket", "object_key": "documents/tenant-1/INVOICE/2024/05/doc-1/v1.pdf"},
            "output": {"bucket": "out-bucket-fail", "prefix": "documents/tenant-1/INVOICE/2024/05/doc-1"},
            "idempotency_key": "idem-1",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"]["category"] == "degraded"
    assert response.json()["detail"]["error"] == "provider_x_degraded"
    main.app.dependency_overrides.clear()
