from __future__ import annotations

from app.tests._client_docflow_onboarding_harness import (
    create_onboarding_application,
    docflow_api_client,
    prepare_signed_generated_doc,
    setup_docflow_env,
)


def test_timeline_contains_sign_events_for_application(monkeypatch) -> None:
    setup_docflow_env(monkeypatch)
    with docflow_api_client() as (api_client, session_factory):
        application_id, token = create_onboarding_application(api_client, prefix="docflow")
        doc_id = prepare_signed_generated_doc(api_client, session_factory, token, application_id)

        timeline = api_client.get(
            f"/api/core/client/docflow/timeline?application_id={application_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert timeline.status_code == 200
        items = timeline.json()["items"]
        assert any(item["event_type"] == "DOC_SIGNED_BY_CLIENT" for item in items)
        assert any(item["doc_id"] == doc_id for item in items)
        assert all(item["application_id"] == application_id for item in items)


def test_timeline_forbidden_for_other_application(monkeypatch) -> None:
    setup_docflow_env(monkeypatch)
    with docflow_api_client() as (api_client, session_factory):
        application_id, _ = create_onboarding_application(api_client, prefix="docflow")
        _, other_token = create_onboarding_application(api_client, prefix="docflow")
        forbidden = api_client.get(
            f"/api/core/client/docflow/timeline?application_id={application_id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"]["reason_code"] == "onboarding_token_app_mismatch"
