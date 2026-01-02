from app.services.audit_signing import VaultTransitSigner


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.responses: list[_FakeResponse] = []

    def queue(self, payload: dict) -> None:
        self.responses.append(_FakeResponse(payload))

    def request(self, method: str, url: str, json=None, headers=None, timeout=None):  # noqa: A002
        self.requests.append(
            {"method": method, "url": url, "json": json, "headers": headers or {}, "timeout": timeout}
        )
        return self.responses.pop(0)


def test_vault_transit_sign_and_verify() -> None:
    session = _FakeSession()
    session.queue({"data": {"signature": "vault:v1:abc123"}})
    session.queue({"data": {"valid": True}})
    signer = VaultTransitSigner(
        alg="ed25519",
        key_id="audit-key",
        vault_addr="https://vault.local",
        vault_token="token",
        mount="transit",
        verify_mode="vault",
        namespace="team",
        session=session,
    )
    signature = signer.sign(b"payload")
    assert signature == "abc123"
    assert signer.verify(b"payload", signature) is True
    assert session.requests[0]["headers"]["X-Vault-Token"] == "token"
    assert session.requests[0]["headers"]["X-Vault-Namespace"] == "team"
    assert session.requests[1]["json"]["signature"] == "vault:v1:abc123"
