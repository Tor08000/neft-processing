from __future__ import annotations

from app.tests._client_docflow_onboarding_harness import (
    create_onboarding_application,
    docflow_api_client,
    move_onboarding_to_in_review,
    setup_docflow_env,
)


def test_sign_event_creates_notification_and_mark_read(monkeypatch) -> None:
    setup_docflow_env(monkeypatch)

    with docflow_api_client() as (api_client, session_factory):
        application_id, token = create_onboarding_application(api_client, prefix="notify")
        move_onboarding_to_in_review(session_factory, application_id)

        generated = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{application_id}/generate-docs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert generated.status_code == 200

        listed_docs = api_client.get(
            f"/api/core/client/v1/onboarding/applications/{application_id}/generated-docs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listed_docs.status_code == 200
        doc_id = listed_docs.json()["items"][0]["id"]

        start = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/start",
            headers={"Authorization": f"Bearer {token}"},
            json={"channel": "sms", "destination": "+79990000000"},
        )
        assert start.status_code == 200
        challenge = start.json()

        confirm = api_client.post(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/sign/otp/confirm",
            headers={"Authorization": f"Bearer {token}"},
            json={"challenge_id": challenge["challenge_id"], "code": challenge["otp_code"]},
        )
        assert confirm.status_code == 200

        listed = api_client.get(
            "/api/core/client/docflow/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listed.status_code == 200
        payload = listed.json()
        assert payload["unread_count"] >= 1
        item = payload["items"][0]
        assert item["kind"] == "DOC_SIGNED_BY_CLIENT"
        assert item["payload"]["doc_id"] == doc_id

        marked = api_client.post(
            f"/api/core/client/docflow/notifications/{item['id']}/read",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert marked.status_code == 200
        assert marked.json()["read_at"] is not None
