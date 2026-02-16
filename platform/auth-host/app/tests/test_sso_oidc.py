from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from app.services.oidc import OIDCService


def test_pkce_pair_has_s256_challenge() -> None:
    verifier, challenge = OIDCService.generate_pkce_pair()
    assert verifier
    assert challenge
    assert "=" not in challenge


def test_state_encode_decode_roundtrip(monkeypatch) -> None:
    monkeypatch.setenv("OIDC_STATE_SECRET", "test-secret")
    service = OIDCService()
    token = service.encode_state({"tenant_id": "tenant", "provider_key": "corp"}, ttl_minutes=5)
    payload = service.decode_state(token)
    assert payload["tenant_id"] == "tenant"
    assert payload["provider_key"] == "corp"


def test_state_ttl_enforced(monkeypatch) -> None:
    monkeypatch.setenv("OIDC_STATE_SECRET", "test-secret")
    service = OIDCService()
    token = service.encode_state({"tenant_id": "tenant"}, ttl_minutes=0)
    time.sleep(1)
    with pytest.raises(HTTPException):
        service.decode_state(token)
