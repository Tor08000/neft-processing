import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.services.audit_signing import AuditSigningService


@pytest.fixture()
def signing_key() -> bytes:
    private_key = Ed25519PrivateKey.generate()
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def test_self_check_fails_when_required_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_SIGNING_MODE", "local")
    monkeypatch.setenv("AUDIT_SIGNING_REQUIRED", "true")
    monkeypatch.setenv("AUDIT_SIGNING_PRIVATE_KEY_B64", "")
    service = AuditSigningService()
    assert service.self_check() is False


def test_self_check_passes_with_local_key(monkeypatch: pytest.MonkeyPatch, signing_key: bytes) -> None:
    monkeypatch.setenv("AUDIT_SIGNING_MODE", "local")
    monkeypatch.setenv("AUDIT_SIGNING_REQUIRED", "true")
    monkeypatch.setenv("AUDIT_SIGNING_PRIVATE_KEY_B64", base64.b64encode(signing_key).decode("utf-8"))
    service = AuditSigningService()
    assert service.self_check() is True
