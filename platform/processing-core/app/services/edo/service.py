from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.integrations.edo.credentials_store import CredentialsStore
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
from app.integrations.edo.sbis_provider import SbisProvider
from app.integrations.edo.sbis_status_mapper import map_sbis_status
from app.models.audit_log import ActorType
from app.models.documents import Document, DocumentFile, DocumentFileType
from app.models.edo import (
    EdoAccount,
    EdoArtifact,
    EdoArtifactType,
    EdoCounterparty,
    EdoDocument,
    EdoDocumentStatus,
    EdoInboundEvent,
    EdoInboundStatus,
    EdoOutbox,
    EdoOutboxStatus,
    EdoProvider,
    EdoTransition,
    EdoTransitionActorType,
)
from app.services.audit_service import AuditService, RequestContext
from app.services.documents_storage import DocumentsStorage
from app.services.edo.state_machine import EdoStateMachine, TransitionError
from app.db.types import new_uuid_str


MAX_ATTEMPTS = 5


class EdoService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.credentials_store = CredentialsStore()
        self.storage = DocumentsStorage()

    def _resolve_provider(self, provider: EdoProvider) -> EdoProvider:
        if provider == EdoProvider.SBIS:
            return SbisProvider(self.db, self.credentials_store)
        raise RuntimeError("unsupported_provider")

    def enqueue_send(
        self,
        *,
        edo_document: EdoDocument,
        dedupe_key: str,
        payload: dict[str, Any],
    ) -> EdoOutbox:
        existing = (
            self.db.query(EdoOutbox)
            .filter(EdoOutbox.dedupe_key == dedupe_key)
            .one_or_none()
        )
        if existing:
            return existing
        outbox = EdoOutbox(
            id=new_uuid_str(),
            event_type="EDO_SEND_REQUESTED",
            payload=payload,
            dedupe_key=dedupe_key,
            status=EdoOutboxStatus.PENDING,
        )
        self.db.add(outbox)
        return outbox

    def dispatch_outbox_item(self, outbox: EdoOutbox) -> EdoOutbox:
        if outbox.status not in {EdoOutboxStatus.PENDING, EdoOutboxStatus.FAILED}:
            return outbox
        edo_document = self.db.query(EdoDocument).get(outbox.id)
        if not edo_document:
            outbox.status = EdoOutboxStatus.FAILED
            outbox.last_error = "edo_document_not_found"
            return outbox
        try:
            request = EdoSendRequest(**outbox.payload)
            result = self.send(request)
            outbox.status = EdoOutboxStatus.SENT
            outbox.last_error = None
            return outbox
        except Exception as exc:  # noqa: BLE001
            outbox.attempts += 1
            outbox.last_error = str(exc)
            if outbox.attempts >= MAX_ATTEMPTS:
                outbox.status = EdoOutboxStatus.DEAD
                edo_document.requires_manual_intervention = True
            else:
                outbox.status = EdoOutboxStatus.FAILED
                outbox.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=30 * outbox.attempts)
            edo_document.status = EdoDocumentStatus.FAILED
            edo_document.last_error = str(exc)
            return outbox

    def send(self, request: EdoSendRequest) -> EdoSendResult:
        edo_document = self.db.query(EdoDocument).get(request.edo_document_id)
        if not edo_document:
            raise RuntimeError("edo_document_not_found")
        if edo_document.provider_doc_id:
            return EdoSendResult(
                provider_doc_id=edo_document.provider_doc_id,
                provider_message_id=None,
                status=edo_document.status,
                raw={"idempotent": True},
            )
        provider = self._resolve_provider(edo_document.provider)
        self._apply_transition(
            edo_document,
            EdoDocumentStatus.QUEUED,
            reason_code="EDO_SEND_REQUESTED",
            payload=request.meta or {},
            actor_type=EdoTransitionActorType.SYSTEM,
        )
        self._apply_transition(
            edo_document,
            EdoDocumentStatus.SENDING,
            reason_code="EDO_SENDING",
            payload=request.meta or {},
            actor_type=EdoTransitionActorType.SYSTEM,
        )
        edo_document.attempts_send = (edo_document.attempts_send or 0) + 1
        result = provider.send(request)
        edo_document.provider_doc_id = result.provider_doc_id
        self._apply_transition(
            edo_document,
            result.status,
            reason_code="EDO_SENT",
            payload=result.raw,
            actor_type=EdoTransitionActorType.PROVIDER,
        )
        return result

    def refresh_status(self, request: EdoStatusRequest) -> EdoStatusResult:
        edo_document = (
            self.db.query(EdoDocument)
            .filter(EdoDocument.provider_doc_id == request.provider_doc_id)
            .one_or_none()
        )
        if not edo_document:
            raise RuntimeError("edo_document_not_found")
        provider = self._resolve_provider(edo_document.provider)
        edo_document.attempts_status = (edo_document.attempts_status or 0) + 1
        result = provider.get_status(request)
        mapped = map_sbis_status(result.raw)
        edo_document.last_status_payload = mapped.last_status_payload
        if edo_document.status != mapped.status:
            self._apply_transition(
                edo_document,
                mapped.status,
                reason_code=f"SBIS_{mapped.provider_status}",
                payload=mapped.last_status_payload,
                actor_type=EdoTransitionActorType.PROVIDER,
            )
        if result.signed_artifacts:
            self._store_artifacts(edo_document, result.signed_artifacts)
        return result

    def receive(self, event: EdoInboundRequest) -> EdoReceiveResult:
        existing = (
            self.db.query(EdoInboundEvent)
            .filter(EdoInboundEvent.provider_event_id == event.provider_event_id)
            .one_or_none()
        )
        if existing:
            return EdoReceiveResult(handled=True, updated_documents=[], raw=event.payload)
        inbound = EdoInboundEvent(
            id=new_uuid_str(),
            provider=EdoProvider.SBIS,
            provider_event_id=event.provider_event_id,
            headers=event.headers,
            payload=event.payload,
            received_at=event.received_at,
            status=EdoInboundStatus.RECEIVED,
        )
        self.db.add(inbound)
        provider_doc_id = event.payload.get("provider_doc_id")
        updated: list[str] = []
        if provider_doc_id:
            edo_document = (
                self.db.query(EdoDocument)
                .filter(EdoDocument.provider_doc_id == provider_doc_id)
                .one_or_none()
            )
            if edo_document:
                mapped = map_sbis_status(event.payload)
                self._apply_transition(
                    edo_document,
                    mapped.status,
                    reason_code=f"SBIS_{mapped.provider_status}",
                    payload=mapped.last_status_payload,
                    actor_type=EdoTransitionActorType.PROVIDER,
                )
                updated.append(str(edo_document.id))
        inbound.status = EdoInboundStatus.PROCESSED
        inbound.processed_at = datetime.now(timezone.utc)
        return EdoReceiveResult(handled=True, updated_documents=updated, raw=event.payload)

    def revoke(self, request: EdoRevokeRequest) -> EdoRevokeResult:
        edo_document = (
            self.db.query(EdoDocument)
            .filter(EdoDocument.provider_doc_id == request.provider_doc_id)
            .one_or_none()
        )
        if not edo_document:
            raise RuntimeError("edo_document_not_found")
        if edo_document.status == EdoDocumentStatus.SIGNED:
            raise RuntimeError("revoke_not_allowed")
        provider = self._resolve_provider(edo_document.provider)
        result = provider.revoke(request)
        self._apply_transition(
            edo_document,
            result.status,
            reason_code="EDO_REVOKED",
            payload=result.raw,
            actor_type=EdoTransitionActorType.PROVIDER,
        )
        return result

    def verify_webhook_signature(self, secret: str, payload: bytes, signature: str) -> bool:
        digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, signature)

    def _apply_transition(
        self,
        edo_document: EdoDocument,
        to_status: EdoDocumentStatus,
        *,
        reason_code: str,
        payload: dict[str, Any],
        actor_type: EdoTransitionActorType,
        actor_id: str | None = None,
    ) -> None:
        from_status = edo_document.status
        if from_status and from_status != to_status:
            try:
                EdoStateMachine.assert_transition(from_status, to_status)
            except TransitionError:
                if to_status != EdoDocumentStatus.UNKNOWN:
                    raise
        edo_document.status = to_status
        transition = EdoTransition(
            id=new_uuid_str(),
            edo_document_id=edo_document.id,
            from_status=from_status,
            to_status=to_status,
            reason_code=reason_code,
            payload=payload,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        self.db.add(transition)
        self._audit_event(edo_document, to_status, reason_code, payload, actor_type)

    def _audit_event(
        self,
        edo_document: EdoDocument,
        status: EdoDocumentStatus,
        reason: str,
        payload: dict[str, Any],
        actor_type: EdoTransitionActorType,
    ) -> None:
        audit = AuditService(self.db)
        ctx = RequestContext(actor_type=ActorType.SYSTEM)
        audit.audit(
            event_type=f"EDO_{status.value}",
            entity_type="EDO_DOCUMENT",
            entity_id=str(edo_document.id),
            action=reason,
            before=None,
            after={
                "status": status.value,
                "provider_doc_id": edo_document.provider_doc_id,
                "document_registry_id": str(edo_document.document_registry_id),
            },
            external_refs={"payload_hash": hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()},
            request_ctx=ctx,
        )

    def _store_artifacts(self, edo_document: EdoDocument, artifacts: list[dict[str, Any]]) -> None:
        for artifact in artifacts:
            artifact_type = EdoArtifactType(artifact.get("artifact_type", EdoArtifactType.OTHER.value))
            content = artifact.get("content")
            url = artifact.get("url")
            content_type = artifact.get("content_type", "application/octet-stream")
            payload: bytes | None = None
            if content:
                payload = content.encode("utf-8") if isinstance(content, str) else content
            elif url:
                with httpx.Client(timeout=10.0) as client:
                    response = client.get(url)
                response.raise_for_status()
                payload = response.content
            if payload is None:
                continue
            file_type = {
                EdoArtifactType.SIGNED_PACKAGE: DocumentFileType.PDF,
                EdoArtifactType.SIGNATURE: DocumentFileType.P7S,
                EdoArtifactType.RECEIPT: DocumentFileType.EDI_XML,
                EdoArtifactType.PROTOCOL: DocumentFileType.PDF,
            }.get(artifact_type, DocumentFileType.PDF)
            document = self.db.query(Document).get(edo_document.document_registry_id)
            if not document:
                continue
            object_key = DocumentsStorage.build_signature_object_key(
                client_id=str(document.client_id),
                period_from=document.period_from,
                period_to=document.period_to,
                version=document.version,
                document_type=document.document_type,
                provider=edo_document.provider.value,
                file_type=file_type,
            )
            stored = self.storage.store_bytes(object_key=object_key, payload=payload, content_type=content_type)
            doc_file = DocumentFile(
                id=new_uuid_str(),
                document_id=document.id,
                file_type=file_type,
                bucket=stored.bucket,
                object_key=stored.object_key,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                content_type=stored.content_type,
                meta={"edo_artifact_type": artifact_type.value},
            )
            self.db.add(doc_file)
            artifact_record = EdoArtifact(
                id=new_uuid_str(),
                edo_document_id=edo_document.id,
                artifact_type=artifact_type,
                document_registry_id=document.id,
                content_hash=stored.sha256,
                provider_ref=artifact,
            )
            self.db.add(artifact_record)


__all__ = ["EdoService"]
