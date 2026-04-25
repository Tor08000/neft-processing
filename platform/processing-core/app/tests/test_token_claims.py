from app.services.token_claims import resolve_token_tenant_id, token_email, token_tenant_id


def test_token_email_prefers_explicit_email_claim():
    assert token_email({"email": "client@example.com", "sub": "client@neft.local"}) == "client@example.com"


def test_token_email_falls_back_to_email_like_subject():
    assert token_email({"sub": "client@neft.local"}) == "client@neft.local"
    assert token_email({"sub": "00000000-0000-0000-0000-000000000001"}) is None


def test_token_tenant_id_accepts_integer_and_digit_string():
    assert token_tenant_id({"tenant_id": 7}) == 7
    assert token_tenant_id({"tenant_id": "42"}) == 42


def test_token_tenant_id_rejects_uuid_like_claim():
    assert token_tenant_id({"tenant_id": "aaf19bab-c7ac-4cbf-9ad3-1d515fc6fb2c"}) is None


def test_resolve_token_tenant_id_falls_back_to_explicit_default_for_uuid_like_claim():
    assert (
        resolve_token_tenant_id(
            {"tenant_id": "aaf19bab-c7ac-4cbf-9ad3-1d515fc6fb2c"},
            default=1,
        )
        == 1
    )
