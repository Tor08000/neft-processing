from __future__ import annotations

from app.tests._client_docflow_onboarding_harness import (
    create_onboarding_application,
    docflow_api_client,
    move_onboarding_to_in_review,
    setup_docflow_env,
)


def _create_in_review_application(api_client, session_factory, *, prefix: str) -> tuple[str, str]:
    application_id, token = create_onboarding_application(api_client, prefix=prefix)
    move_onboarding_to_in_review(session_factory, application_id)
    return application_id, token


def test_generated_docs_happy_path_and_access_control(monkeypatch) -> None:
    setup_docflow_env(monkeypatch)

    with docflow_api_client() as (api_client, session_factory):
        application_id, token = _create_in_review_application(
            api_client,
            session_factory,
            prefix="gen-docs",
        )

        generated = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{application_id}/generate-docs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert generated.status_code == 200
        assert len(generated.json()["items"]) == 3

        listed = api_client.get(
            f"/api/core/client/v1/onboarding/applications/{application_id}/generated-docs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 3
        doc_id = listed.json()["items"][0]["id"]

        download = api_client.get(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert download.status_code == 200
        assert download.content.startswith(b"%PDF-1.7")

        _, token_other = create_onboarding_application(api_client, prefix="other-docs")
        forbidden = api_client.get(
            f"/api/core/client/v1/onboarding/generated-docs/{doc_id}/download",
            headers={"Authorization": f"Bearer {token_other}"},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"]["reason_code"] == "onboarding_token_app_mismatch"


def test_generated_docs_versioning(monkeypatch) -> None:
    setup_docflow_env(monkeypatch)

    with docflow_api_client() as (api_client, session_factory):
        application_id, token = _create_in_review_application(
            api_client,
            session_factory,
            prefix="gen-docs",
        )

        first = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{application_id}/generate-docs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first.status_code == 200

        second = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{application_id}/generate-docs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert second.status_code == 200

        listed = api_client.get(
            f"/api/core/client/v1/onboarding/applications/{application_id}/generated-docs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listed.status_code == 200
        versions = sorted({(item["doc_kind"], item["version"]) for item in listed.json()["items"]})
        assert ("OFFER", 1) in versions
        assert ("OFFER", 2) in versions


def test_generated_docs_prod_mode_without_sign(monkeypatch) -> None:
    setup_docflow_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("PLATFORM_DOC_SIGN_MODE", "disabled")

    with docflow_api_client() as (api_client, session_factory):
        application_id, token = _create_in_review_application(
            api_client,
            session_factory,
            prefix="gen-docs",
        )

        generated = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{application_id}/generate-docs",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert generated.status_code == 200
    statuses = {item["status"] for item in generated.json()["items"]}
    assert statuses == {"GENERATED"}
