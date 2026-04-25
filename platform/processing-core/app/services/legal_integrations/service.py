from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.client_actions import DocumentAcknowledgement
from app.models.documents import Document, DocumentFile, DocumentFileType, DocumentStatus
from app.models.legal_integrations import (
    Certificate,
    DocumentEnvelope,
    DocumentEnvelopeStatus,
    DocumentSignature,
    DocumentSignatureStatus,
    LegalProviderConfig,
    SignatureType,
)
from app.models.audit_log import AuditVisibility
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.services.legal_graph import GraphContext, LegalGraphBuilder, LegalGraphWriteFailure, audit_graph_write_failure
from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)
from app.services.crypto_verify.base import VerificationResult
from app.services.crypto_verify.gost_p7s import verify_p7s_signature
from app.services.decision import DecisionAction, DecisionContext, DecisionEngine, DecisionOutcome
from app.services.documents_storage import DocumentsStorage
from app.services.legal_integrations.base import EnvelopeStatus, SigningPayload
from app.services.legal_integrations.errors import EnvelopeNotFound, ProviderNotConfigured, SignatureVerificationError
from app.services.legal_integrations.registry import LegalAdapterRegistry, registry as default_registry
from app.services.policy import Action, PolicyEngine, audit_access_denied
from app.services.policy.actor import actor_from_token
from app.services.policy.resources import ResourceContext


@dataclass(frozen=True)
class ResolvedLegalConfig:
    signing_provider: str
    edo_provider: str
    require_signature_for_finalize: bool


class LegalIntegrationsService:
    def __init__(
        self,
        db: Session,
        *,
        registry: LegalAdapterRegistry | None = None,
        storage: DocumentsStorage | None = None,
        decision_engine: DecisionEngine | None = None,
        policy_engine: PolicyEngine | None = None,
        now_provider=None,
    ) -> None:
        self.db = db
        self.registry = registry or default_registry
        self.storage = storage
        self.decision_engine = decision_engine or DecisionEngine(db)
        self.policy_engine = policy_engine or PolicyEngine()
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def resolve_config(self, *, tenant_id: int, client_id: str) -> ResolvedLegalConfig:
        config = (
            self.db.query(LegalProviderConfig)
            .filter(LegalProviderConfig.tenant_id == tenant_id)
            .filter(LegalProviderConfig.client_id == client_id)
            .one_or_none()
        )
        if config is None:
            return ResolvedLegalConfig(signing_provider="none", edo_provider="none", require_signature_for_finalize=False)
        return ResolvedLegalConfig(
            signing_provider=config.signing_provider,
            edo_provider=config.edo_provider,
            require_signature_for_finalize=config.require_signature_for_finalize,
        )

    def send_document_for_signing(
        self,
        *,
        document_id: str,
        provider_override: str | None = None,
        token: dict | None = None,
        request=None,
        override_risk: bool = False,
        use_edo: bool = False,
    ) -> DocumentEnvelope:
        document = self._get_document(document_id)
        if document.status != DocumentStatus.ISSUED:
            raise ValueError("document_status_invalid")
        config = self.resolve_config(tenant_id=document.tenant_id, client_id=document.client_id)
        provider = provider_override or (config.edo_provider if use_edo else config.signing_provider)
        if not provider or provider == "none":
            raise ProviderNotConfigured("provider_not_configured")

        actor = actor_from_token(token or {})
        resource = ResourceContext(
            resource_type="DOCUMENT",
            tenant_id=document.tenant_id,
            client_id=document.client_id,
            status=document.status.value,
        )
        decision_context = DecisionContext(
            tenant_id=document.tenant_id,
            client_id=document.client_id,
            actor_type="ADMIN",
            action=DecisionAction.DOCUMENT_SEND_FOR_SIGNING,
            amount=0,
            history={},
            metadata={"subject_id": str(document.id), "provider": provider},
        )
        risk_decision = self.decision_engine.evaluate(decision_context)
        if risk_decision.outcome != DecisionOutcome.ALLOW:
            if override_risk:
                self._audit_event(
                    event_type="LEGAL_OVERRIDE_APPLIED",
                    document=document,
                    payload={"action": "send_for_signing", "provider": provider},
                    request=request,
                    token=token,
                )
            else:
                self._audit_event(
                    event_type="LEGAL_ACTION_BLOCKED_BY_RISK",
                    document=document,
                    payload={"action": "send_for_signing", "provider": provider, "risk": risk_decision.explain},
                    request=request,
                    token=token,
                )
                self._audit_event(
                    event_type="RISK_BLOCK",
                    document=document,
                    payload={"action": "send_for_signing", "provider": provider, "risk": risk_decision.explain},
                    request=request,
                    token=token,
                )
                raise PermissionError("risk_block")

        policy_decision = self.policy_engine.check(actor=actor, action=Action.DOCUMENT_SEND_FOR_SIGNING, resource=resource)
        if not policy_decision.allowed:
            audit_access_denied(
                self.db, actor=actor, action=Action.DOCUMENT_SEND_FOR_SIGNING, resource=resource, decision=policy_decision, token=token
            )
            raise PermissionError(policy_decision.reason or "forbidden")

        pdf_file = self._get_document_file(document, DocumentFileType.PDF)
        payload = SigningPayload(
            document_id=str(document.id),
            document_hash=pdf_file.sha256,
            document_type=document.document_type.value,
            client_id=document.client_id,
            tenant_id=document.tenant_id,
        )
        adapter = self.registry.get(provider)
        envelope_ref = adapter.send_for_signing(str(document.id), payload)
        envelope = self._upsert_envelope(document=document, provider=provider, envelope_id=envelope_ref.envelope_id)
        envelope.status = envelope_ref.status
        envelope.sent_at = envelope.sent_at or self.now_provider()
        envelope.last_status_at = envelope.last_status_at or self.now_provider()
        self.db.commit()

        self._audit_event(
            event_type="DOCUMENT_SENT_TO_EDO" if use_edo else "DOCUMENT_SENT_FOR_SIGNING",
            document=document,
            payload={"provider": provider, "envelope_id": envelope.envelope_id, "status": envelope.status.value},
            request=request,
            token=token,
        )
        return envelope

    def update_envelope_status(
        self,
        *,
        provider: str,
        envelope_id: str,
        status: EnvelopeStatus,
        request=None,
        token: dict | None = None,
        use_edo: bool = False,
    ) -> DocumentEnvelope:
        envelope = (
            self.db.query(DocumentEnvelope)
            .filter(DocumentEnvelope.provider == provider)
            .filter(DocumentEnvelope.envelope_id == envelope_id)
            .one_or_none()
        )
        if envelope is None:
            raise EnvelopeNotFound("envelope_not_found")
        status_at = status.status_at or self.now_provider()
        if envelope.last_status_at and status_at <= envelope.last_status_at:
            return envelope

        envelope.status = status.status
        envelope.last_status_at = status_at
        envelope.error_message = status.error_message
        envelope.meta = status.meta
        self.db.commit()

        self._audit_event(
            event_type="DOCUMENT_EDO_STATUS_UPDATED" if use_edo else "DOCUMENT_SIGNING_STATUS_UPDATED",
            document_id=envelope.document_id,
            payload={"provider": provider, "envelope_id": envelope.envelope_id, "status": status.status.value},
            request=request,
            token=token,
        )

        if status.status == DocumentEnvelopeStatus.SIGNED:
            self._store_signed_artifacts(envelope=envelope, provider=provider, request=request, token=token)
        return envelope

    def poll_provider(self, *, provider: str, use_edo: bool = False) -> list[DocumentEnvelope]:
        adapter = self.registry.get(provider)
        envelopes = (
            self.db.query(DocumentEnvelope)
            .filter(DocumentEnvelope.provider == provider)
            .filter(DocumentEnvelope.status.in_([DocumentEnvelopeStatus.SENT, DocumentEnvelopeStatus.DELIVERED]))
            .all()
        )
        updated: list[DocumentEnvelope] = []
        for envelope in envelopes:
            status = adapter.get_status(envelope.envelope_id)
            updated.append(
                self.update_envelope_status(
                    provider=provider,
                    envelope_id=envelope.envelope_id,
                    status=status,
                    use_edo=use_edo,
                )
            )
        return updated

    def _store_signed_artifacts(
        self,
        *,
        envelope: DocumentEnvelope,
        provider: str,
        request=None,
        token: dict | None = None,
    ) -> None:
        adapter = self.registry.get(provider)
        artifacts = adapter.fetch_signed_artifacts(envelope.envelope_id)
        if not artifacts:
            raise SignatureVerificationError("signed_artifacts_missing")

        document = self._get_document(str(envelope.document_id))
        pdf_file = self._get_document_file(document, DocumentFileType.PDF)
        signed_at = self.now_provider()
        if self.storage is None:
            self.storage = DocumentsStorage()
        for artifact in artifacts:
            existing_signature = (
                self.db.query(DocumentSignature)
                .filter(DocumentSignature.document_id == document.id)
                .filter(DocumentSignature.provider == provider)
                .filter(DocumentSignature.signature_type == artifact.signature_type)
                .one_or_none()
            )
            if existing_signature:
                continue
            object_key = DocumentsStorage.build_signature_object_key(
                client_id=document.client_id,
                period_from=document.period_from,
                period_to=document.period_to,
                version=document.version,
                document_type=document.document_type,
                provider=provider,
                file_type=artifact.file_type,
            )
            stored = self.storage.store_bytes(
                object_key=object_key,
                payload=artifact.payload,
                content_type=artifact.content_type,
            )
            file_record = DocumentFile(
                document_id=document.id,
                file_type=artifact.file_type,
                bucket=stored.bucket,
                object_key=stored.object_key,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                content_type=stored.content_type,
                meta=artifact.meta,
            )
            self.db.add(file_record)
            self.db.flush()
            verification = self._verify_signature(
                artifact=artifact,
                document_hash=pdf_file.sha256,
            )
            certificate_id = None
            if verification.certificate:
                certificate = Certificate(
                    subject_dn=verification.certificate.subject_dn,
                    issuer_dn=verification.certificate.issuer_dn,
                    serial_number=verification.certificate.serial_number,
                    thumbprint_sha256=verification.certificate.thumbprint_sha256,
                    valid_from=verification.certificate.valid_from,
                    valid_to=verification.certificate.valid_to,
                )
                self.db.add(certificate)
                self.db.flush()
                certificate_id = certificate.id

            signature_record = DocumentSignature(
                document_id=document.id,
                provider=provider,
                version=document.version,
                request_id=envelope.envelope_id,
                status=DocumentSignatureStatus.VERIFIED if verification.verified else DocumentSignatureStatus.REJECTED,
                input_object_key=pdf_file.object_key,
                input_sha256=pdf_file.sha256,
                signed_object_key=stored.object_key if artifact.file_type == DocumentFileType.PDF else None,
                signed_sha256=stored.sha256 if artifact.file_type == DocumentFileType.PDF else None,
                signature_object_key=stored.object_key if artifact.file_type in {DocumentFileType.SIG, DocumentFileType.P7S} else None,
                signature_sha256=stored.sha256 if artifact.file_type in {DocumentFileType.SIG, DocumentFileType.P7S} else None,
                attempt=1,
                started_at=signed_at,
                finished_at=signed_at,
                signature_type=artifact.signature_type,
                file_id=file_record.id,
                signature_hash_sha256=stored.sha256,
                signed_at=artifact.signed_at or signed_at,
                certificate_id=certificate_id,
                verified=verification.verified,
                verification_details=verification.details,
            )
            self.db.add(signature_record)
            self.db.flush()

            self._audit_event(
                event_type="DOCUMENT_SIGNED_ARTIFACTS_SAVED",
                document=document,
                payload={
                    "provider": provider,
                    "file_type": artifact.file_type.value,
                    "signature_type": artifact.signature_type.value,
                    "signature_hash": stored.sha256,
                },
                request=request,
                token=token,
            )
            self._audit_event(
                event_type="DOCUMENT_SIGNATURE_VERIFIED" if verification.verified else "DOCUMENT_SIGNATURE_VERIFY_FAILED",
                document=document,
                payload={
                    "provider": provider,
                    "signature_type": artifact.signature_type.value,
                    "verified": verification.verified,
                    "details": verification.details,
                },
                request=request,
                token=token,
            )

        acknowledgement = (
            self.db.query(DocumentAcknowledgement)
            .filter(DocumentAcknowledgement.client_id == document.client_id)
            .filter(DocumentAcknowledgement.document_type == document.document_type.value)
            .filter(DocumentAcknowledgement.document_id == str(document.id))
            .one_or_none()
        )
        if acknowledgement is None:
            acknowledgement = DocumentAcknowledgement(
                tenant_id=document.tenant_id,
                client_id=document.client_id,
                document_type=document.document_type.value,
                document_id=str(document.id),
                document_object_key=pdf_file.object_key,
                document_hash=pdf_file.sha256,
                ack_by_email=f"{provider}@external",
                ack_at=signed_at,
                ack_method="LEGAL_SIGNING",
            )
            self.db.add(acknowledgement)
        if document.status == DocumentStatus.ISSUED:
            document.status = DocumentStatus.ACKNOWLEDGED
            document.ack_at = signed_at

        self.db.commit()
        try:
            request_ctx = request_context_from_request(request, token=_sanitize_token_for_audit(token))
            graph_context = GraphContext(tenant_id=document.tenant_id, request_ctx=request_ctx)
            LegalGraphBuilder(self.db, context=graph_context).ensure_document_ack_graph(
                document=document,
                acknowledgement=acknowledgement,
                meta={
                    "actor_email": acknowledgement.ack_by_email,
                    "ack_method": acknowledgement.ack_method,
                    "ack_at": acknowledgement.ack_at,
                },
            )
        except Exception as exc:  # noqa: BLE001 - graph must not block signature flow
            logger.warning(
                "legal_graph_signature_ack_failed",
                extra={"document_id": str(document.id), "error": str(exc)},
            )
            audit_graph_write_failure(
                self.db,
                failure=LegalGraphWriteFailure(
                    entity_type="document_acknowledgement",
                    entity_id=str(acknowledgement.id),
                    error=str(exc),
                ),
                request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
            )

    def _verify_signature(self, *, artifact, document_hash: str):
        if artifact.signature_type in {SignatureType.GOST_P7S, SignatureType.KEP}:
            return verify_p7s_signature(artifact.payload, document_hash=document_hash)
        return VerificationResult(
            verified=True,
            details={"structural": True, "document_hash": document_hash},
            certificate=None,
        )

    def _upsert_envelope(self, *, document: Document, provider: str, envelope_id: str) -> DocumentEnvelope:
        envelope = (
            self.db.query(DocumentEnvelope)
            .filter(DocumentEnvelope.provider == provider)
            .filter(DocumentEnvelope.envelope_id == envelope_id)
            .one_or_none()
        )
        if envelope is None:
            envelope = DocumentEnvelope(
                document_id=document.id,
                provider=provider,
                envelope_id=envelope_id,
                status=DocumentEnvelopeStatus.CREATED,
                sent_at=self.now_provider(),
                last_status_at=self.now_provider(),
            )
            self.db.add(envelope)
            self.db.flush()
        return envelope

    def _get_document(self, document_id: str) -> Document:
        document = self.db.query(Document).filter(Document.id == document_id).one_or_none()
        if document is None:
            raise ValueError("document_not_found")
        return document

    def _get_document_file(self, document: Document, file_type: DocumentFileType) -> DocumentFile:
        file_record = (
            self.db.query(DocumentFile)
            .filter(DocumentFile.document_id == document.id)
            .filter(DocumentFile.file_type == file_type)
            .one_or_none()
        )
        if file_record is None:
            raise ValueError("document_file_not_found")
        return file_record

    def _audit_event(
        self,
        *,
        event_type: str,
        document: Document | None = None,
        document_id: str | None = None,
        payload: dict | None = None,
        request=None,
        token: dict | None = None,
    ) -> None:
        entity_id = document_id or (str(document.id) if document else "")
        AuditService(self.db).audit(
            event_type=event_type,
            entity_type="document",
            entity_id=entity_id,
            action="UPDATE",
            visibility=AuditVisibility.PUBLIC,
            after=payload or {},
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
        )


__all__ = ["LegalIntegrationsService", "ResolvedLegalConfig"]
