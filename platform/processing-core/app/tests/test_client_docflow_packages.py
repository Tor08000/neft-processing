from __future__ import annotations

import io
import zipfile

from app.tests._client_docflow_onboarding_harness import (
    create_onboarding_application,
    docflow_api_client,
    prepare_signed_generated_doc,
    setup_docflow_env,
)


def test_create_and_download_package(monkeypatch) -> None:
    setup_docflow_env(monkeypatch)
    with docflow_api_client() as (api_client, session_factory):
        application_id, token = create_onboarding_application(api_client, prefix="package")
        doc_id = prepare_signed_generated_doc(api_client, session_factory, token, application_id)

        created = api_client.post(
            "/api/core/client/docflow/packages",
            headers={"Authorization": f"Bearer {token}"},
            json={"application_id": application_id, "doc_ids": [doc_id]},
        )
        assert created.status_code == 200
        package = created.json()
        assert package["status"] == "READY"
        package_id = package["id"]

        listed = api_client.get(
            f"/api/core/client/docflow/packages?application_id={application_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listed.status_code == 200
        assert any(item["id"] == package_id for item in listed.json()["items"])

        downloaded = api_client.get(
            f"/api/core/client/docflow/packages/{package_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert downloaded.status_code == 200
        archive = zipfile.ZipFile(io.BytesIO(downloaded.content))
        names = set(archive.namelist())
        assert any(name.startswith("outbound/") for name in names)
        assert any(name.startswith("signatures/") for name in names)


def test_cannot_download_foreign_package(monkeypatch) -> None:
    setup_docflow_env(monkeypatch)
    with docflow_api_client() as (api_client, session_factory):
        application_id, token = create_onboarding_application(api_client, prefix="package")
        doc_id = prepare_signed_generated_doc(api_client, session_factory, token, application_id)
        created = api_client.post(
            "/api/core/client/docflow/packages",
            headers={"Authorization": f"Bearer {token}"},
            json={"application_id": application_id, "doc_ids": [doc_id]},
        )
        assert created.status_code == 200
        package_id = created.json()["id"]

        _, other_token = create_onboarding_application(api_client, prefix="package")
        forbidden = api_client.get(
            f"/api/core/client/docflow/packages/{package_id}/download",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"]["reason_code"] == "package_forbidden"
