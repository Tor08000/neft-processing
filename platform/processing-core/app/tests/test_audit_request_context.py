from app.services.audit_service import request_context_from_request


class _Client:
    def __init__(self, host: str):
        self.host = host


class _Request:
    def __init__(self, host: str):
        self.client = _Client(host)
        self.headers = {}


def test_request_context_ignores_non_numeric_token_tenant_for_audit():
    ctx = request_context_from_request(
        None,
        token={"user_id": "admin-1", "tenant_id": "aaf19bab-c7ac-4cbf-9ad3-1d515fc6fb2c"},
    )

    assert ctx.actor_id == "admin-1"
    assert ctx.tenant_id is None


def test_request_context_allows_explicit_audit_tenant_override():
    ctx = request_context_from_request(
        None,
        token={"user_id": "admin-1", "tenant_id": "aaf19bab-c7ac-4cbf-9ad3-1d515fc6fb2c"},
        tenant_id_override=7,
    )

    assert ctx.tenant_id == 7


def test_request_context_keeps_valid_ip_for_audit():
    ctx = request_context_from_request(_Request("127.0.0.1"), token={"user_id": "admin-1"})

    assert ctx.ip == "127.0.0.1"


def test_request_context_drops_non_ip_testclient_host_for_audit():
    ctx = request_context_from_request(_Request("testclient"), token={"user_id": "admin-1"})

    assert ctx.ip is None
