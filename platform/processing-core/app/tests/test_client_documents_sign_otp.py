from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domains.client.signing.repo import ClientSigningRepository
from app.tests._client_docflow_onboarding_harness import (
    create_onboarding_application,
    docflow_api_client,
    setup_docflow_env,
)


def _prepare_unsigned_doc(api_client, session_factory, token: str, application_id: str) -> str:
    from app.tests._client_docflow_onboarding_harness import move_onboarding_to_in_review

    move_onboarding_to_in_review(session_factory, application_id)
    generated = api_client.post(
        f"/api/core/client/v1/onboarding/applications/{application_id}/generate-docs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert generated.status_code == 200
    listed = api_client.get(
        f"/api/core/client/v1/onboarding/applications/{application_id}/generated-docs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    return listed.json()["items"][0]["id"]


def test_start_and_confirm_otp(monkeypatch) -> None:
    setup_docflow_env(monkeypatch)
    with docflow_api_client() as (api_client, session_factory):
        application_id, token = create_onboarding_application(api_client, prefix="otp-docs")
        doc_id = _prepare_unsigned_doc(api_client, session_factory, token, application_id)

        start = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": "sms", "destination": "+79990000000"},
        )
        assert start.status_code == 200
        body = start.json()
        confirm = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"challenge_id": body["challenge_id"], "code": "000000"},
        )
        assert confirm.status_code == 200
        assert confirm.json()["doc"]["status"] == "SIGNED_BY_CLIENT"


def test_wrong_code_locks(monkeypatch) -> None:
    setup_docflow_env(monkeypatch)
    monkeypatch.setenv("OTP_MAX_ATTEMPTS", "2")
    with docflow_api_client() as (api_client, session_factory):
        application_id, token = create_onboarding_application(api_client, prefix="otp-docs")
        doc_id = _prepare_unsigned_doc(api_client, session_factory, token, application_id)
        start = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": "sms", "destination": "+79990000000"},
        )
        assert start.status_code == 200
        challenge_id = start.json()["challenge_id"]

        bad_1 = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"challenge_id": challenge_id, "code": "111111"},
        )
        assert bad_1.status_code == 400
        bad_2 = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"challenge_id": challenge_id, "code": "111111"},
        )
        assert bad_2.status_code == 429
        assert bad_2.json()["detail"]["error_code"] == "otp_locked"

        db = session_factory()
        try:
            challenge = ClientSigningRepository(db).get_challenge(challenge_id)
            assert challenge is not None
            assert challenge.status == "LOCKED"
        finally:
            db.close()


def test_expired(monkeypatch) -> None:
    setup_docflow_env(monkeypatch)
    with docflow_api_client() as (api_client, session_factory):
        application_id, token = create_onboarding_application(api_client, prefix="otp-docs")
        doc_id = _prepare_unsigned_doc(api_client, session_factory, token, application_id)
        start = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": "sms", "destination": "+79990000000"},
        )
        assert start.status_code == 200
        challenge_id = start.json()["challenge_id"]

        db = session_factory()
        try:
            repo = ClientSigningRepository(db)
            challenge = repo.get_challenge(challenge_id)
            assert challenge is not None
            challenge.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.add(challenge)
            db.commit()
        finally:
            db.close()

        confirm = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"challenge_id": challenge_id, "code": "000000"},
        )
        assert confirm.status_code == 400
        assert confirm.json()["detail"]["error_code"] == "otp_expired"
