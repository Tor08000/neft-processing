from __future__ import annotations

from app.tests._client_docflow_onboarding_harness import (
    create_onboarding_application,
    docflow_api_client,
    move_onboarding_to_in_review,
    setup_docflow_env,
)


def test_upload_list_download_happy_path(monkeypatch) -> None:
    setup_docflow_env(monkeypatch)

    with docflow_api_client() as (api_client, _session_factory):
        application_id, token = create_onboarding_application(api_client, prefix="docs")
        upload = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{application_id}/documents",
            files={"file": ("sample.pdf", b"%PDF-1.7 test", "application/pdf")},
            data={"doc_type": "EGRUL"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert upload.status_code == 201
        doc_id = upload.json()["id"]

        listed = api_client.get(
            f"/api/core/client/v1/onboarding/applications/{application_id}/documents",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 1

        download = api_client.get(
            f"/api/core/client/v1/onboarding/documents/{doc_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert download.status_code == 200
    assert download.content == b"%PDF-1.7 test"
    assert download.headers["content-type"].startswith("application/pdf")


def test_access_control_forbidden(monkeypatch) -> None:
    setup_docflow_env(monkeypatch)

    with docflow_api_client() as (api_client, _session_factory):
        application_id, token_a = create_onboarding_application(api_client, prefix="docs-a")
        _, token_b = create_onboarding_application(api_client, prefix="docs-b")
        upload = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{application_id}/documents",
            files={"file": ("sample.pdf", b"%PDF-1.7 test", "application/pdf")},
            data={"doc_type": "EGRUL"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert upload.status_code == 201
        doc_id = upload.json()["id"]

        forbidden = api_client.get(
            f"/api/core/client/v1/onboarding/documents/{doc_id}/download",
            headers={"Authorization": f"Bearer {token_b}"},
        )

    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["reason_code"] == "onboarding_token_app_mismatch"


def test_upload_restricted_state(monkeypatch) -> None:
    setup_docflow_env(monkeypatch)

    with docflow_api_client() as (api_client, session_factory):
        application_id, token = create_onboarding_application(api_client, prefix="docs")
        move_onboarding_to_in_review(session_factory, application_id)

        blocked = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{application_id}/documents",
            files={"file": ("sample.pdf", b"%PDF-1.7 test", "application/pdf")},
            data={"doc_type": "EGRUL"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert blocked.status_code == 409
    assert blocked.json()["detail"]["reason_code"] == "application_not_editable"


def test_upload_mime_and_size(monkeypatch) -> None:
    setup_docflow_env(monkeypatch)
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")

    with docflow_api_client() as (api_client, _session_factory):
        application_id, token = create_onboarding_application(api_client, prefix="docs")
        bad_mime = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{application_id}/documents",
            files={"file": ("bad.txt", b"hello", "text/plain")},
            data={"doc_type": "EGRUL"},
            headers={"Authorization": f"Bearer {token}"},
        )
        too_big = api_client.post(
            f"/api/core/client/v1/onboarding/applications/{application_id}/documents",
            files={"file": ("big.pdf", b"0" * (1024 * 1024 + 1), "application/pdf")},
            data={"doc_type": "EGRUL"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert bad_mime.status_code == 415
    assert bad_mime.json()["detail"]["reason_code"] == "unsupported_mime"
    assert too_big.status_code == 413
    assert too_big.json()["detail"]["reason_code"] == "file_too_large"
