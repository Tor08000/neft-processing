from __future__ import annotations

import base64
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.integrations.edo.credentials_store import CredentialsStore, SbisCredentials
from app.integrations.edo.dtos import (
    EdoInboundRequest,
    EdoReceiveResult,
    EdoRevokeRequest,
    EdoRevokeResult,
    EdoSendRequest,
    EdoSendResult,
    EdoStatusRequest,
    EdoStatusResult,
)
from app.integrations.edo.provider import EdoProvider
from app.integrations.edo.sbis_status_mapper import map_sbis_status
from app.models.documents import Document, DocumentFile, DocumentFileType
from app.models.edo import EdoAccount, EdoDocumentStatus
from app.services.documents_storage import DocumentsStorage


class SbisProvider(EdoProvider):
    def __init__(self, db: Session, credentials_store: CredentialsStore) -> None:
        self.db = db
        self.credentials_store = credentials_store
        self.storage = DocumentsStorage()

    def send(self, request: EdoSendRequest) -> EdoSendResult:
        account = self.db.query(EdoAccount).get(request.account_id)
        if not account:
            raise RuntimeError("edo_account_not_found")
        credentials = self.credentials_store.get_credentials(account.credentials_ref)
        document = self.db.query(Document).get(request.document_registry_id)
        if not document:
            raise RuntimeError("document_not_found")
        file_record = (
            self.db.query(DocumentFile)
            .filter(DocumentFile.document_id == document.id)
            .filter(DocumentFile.file_type == DocumentFileType.PDF)
            .one_or_none()
        )
        if not file_record:
            raise RuntimeError("document_file_not_found")
        payload = self.storage.fetch_bytes(file_record.object_key)
        if payload is None:
            raise RuntimeError("document_payload_not_found")
        send_path = self._endpoint(credentials, "send_path", "/edo/send")
        response = self._request(
            credentials,
            "POST",
            send_path,
            json_data={
                "account_box_id": account.box_id,
                "counterparty_id": request.counterparty_id,
                "doc_type": request.doc_type,
                "meta": request.meta,
                "document_registry_id": request.document_registry_id,
                "content_b64": base64.b64encode(payload).decode("utf-8"),
            },
        )
        provider_doc_id = response.get("provider_doc_id") or response.get("doc_id") or response.get("id")
        if not provider_doc_id:
            raise RuntimeError("provider_doc_id_missing")
        mapped = map_sbis_status(response)
        status = mapped.status if mapped.status != EdoDocumentStatus.UNKNOWN else EdoDocumentStatus.SENT
        return EdoSendResult(
            provider_doc_id=str(provider_doc_id),
            provider_message_id=response.get("message_id"),
            status=status or EdoDocumentStatus.SENT,
            raw=response,
        )

    def get_status(self, request: EdoStatusRequest) -> EdoStatusResult:
        credentials = self._credentials_for_account(request.account_id)
        status_path = self._endpoint(credentials, "status_path", "/edo/status")
        response = self._request(
            credentials,
            "POST",
            status_path,
            json_data={"provider_doc_id": request.provider_doc_id},
        )
        mapped = map_sbis_status(response)
        return EdoStatusResult(
            status=mapped.status,
            provider_status=mapped.provider_status,
            raw=response,
            signed_artifacts=response.get("artifacts"),
        )

    def receive(self, event: EdoInboundRequest) -> EdoReceiveResult:
        return EdoReceiveResult(handled=True, updated_documents=[], raw=event.payload)

    def revoke(self, request: EdoRevokeRequest) -> EdoRevokeResult:
        credentials = self._credentials_for_account(request.account_id)
        revoke_path = self._endpoint(credentials, "revoke_path", "/edo/revoke")
        response = self._request(
            credentials,
            "POST",
            revoke_path,
            json_data={"provider_doc_id": request.provider_doc_id, "reason": request.reason},
        )
        mapped = map_sbis_status(response)
        return EdoRevokeResult(status=mapped.status, raw=response)

    def _credentials_for_account(self, account_id: str) -> SbisCredentials:
        account = self.db.query(EdoAccount).get(account_id)
        if not account:
            raise RuntimeError("edo_account_not_found")
        return self.credentials_store.get_credentials(account.credentials_ref)

    def _endpoint(self, credentials: SbisCredentials, key: str, default_path: str) -> str:
        if credentials.meta and credentials.meta.get(key):
            return str(credentials.meta[key])
        return default_path

    def _request(self, credentials: SbisCredentials, method: str, path: str, json_data: dict[str, Any]) -> dict[str, Any]:
        url = credentials.base_url.rstrip("/") + path
        headers: dict[str, str] = {"content-type": "application/json"}
        auth = None
        if credentials.token:
            headers["authorization"] = f"Bearer {credentials.token}"
        elif credentials.login and credentials.password:
            auth = httpx.BasicAuth(credentials.login, credentials.password)
        with httpx.Client(timeout=30.0) as client:
            response = client.request(method, url, json=json_data, headers=headers, auth=auth)
        response.raise_for_status()
        return response.json()


__all__ = ["SbisProvider"]
