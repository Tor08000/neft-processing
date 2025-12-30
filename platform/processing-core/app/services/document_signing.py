from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from neft_shared.settings import get_settings

from app.models.audit_log import AuditVisibility
from app.models.documents import Document, DocumentFile, DocumentFileType
from app.models.legal_integrations import DocumentSignature, DocumentSignatureStatus, SignatureType
from app.services.audit_service import AuditService, _sanitize_token_for_audit, request_context_from_request
from app.services.document_service_client import (
    DocumentServiceClient,
    DocumentSignRequest,
    DocumentStorageRef,
    DocumentVerifyRequest,
)
from app.services.policy import Action, PolicyEngine, audit_access_denied
from app.services.policy.actor import actor_from_token
from app.services.policy.resources import ResourceContext

settings = get_settings()


@dataclass(frozen=True)
class SignResult:
    signature: DocumentSignature


@dataclass(frozen=True)
class VerifyResult:
    signature: DocumentSignature
    verified: bool
    status: str


class DocumentSigningService:
    def __init__(
        self,
        db: Session,
        *,
        document_client: DocumentServiceClient | None = None,
        policy_engine: PolicyEngine | None = None,
        now_provider=None,
    ) -> None:
        self.db = db
        self.document_client = document_client or DocumentServiceClient()
        self.policy_engine = policy_engine or PolicyEngine()
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def request_sign(
        self,
        *,
        document_id: str,
        provider: str,
        meta: dict[str, Any] | None,
        idempotency_key: str | None,
        request=None,
        token: dict | None = None,
    ) -> SignResult:
        document = self._get_document(document_id)
        actor = actor_from_token(token or {})
        resource = ResourceContext(
            resource_type="DOCUMENT",
            tenant_id=document.tenant_id,
            client_id=document.client_id,
            status=document.status.value,
        )
        decision = self.policy_engine.check(actor=actor, action=Action.DOCUMENT_SIGN_REQUEST, resource=resource)
        if not decision.allowed:
            audit_access_denied(
                self.db,
                actor=actor,
                action=Action.DOCUMENT_SIGN_REQUEST,
                resource=resource,
                decision=decision,
                token=token,
            )
            raise PermissionError(decision.reason or "forbidden")

        pdf_file = self._get_document_file(document, DocumentFileType.PDF)
        version = self._next_version(document.id)
        request_id = idempotency_key or f"sign-{uuid4()}"
        signature_record = DocumentSignature(
            document_id=document.id,
            provider=provider,
            version=version,
            request_id=None,
            status=DocumentSignatureStatus.REQUESTED,
            input_object_key=pdf_file.object_key,
            input_sha256=pdf_file.sha256,
            attempt=1,
            started_at=self.now_provider(),
            meta=self._merge_meta(meta, {"input_bucket": pdf_file.bucket}),
            signature_type=SignatureType.ESIGN,
            signature_hash_sha256="pending",
        )
        self.db.add(signature_record)
        self.db.flush()

        AuditService(self.db).audit(
            event_type="DOCUMENT_SIGNING_REQUESTED",
            entity_type="document",
            entity_id=str(document.id),
            action="CREATE",
            visibility=AuditVisibility.PUBLIC,
            after={
                "signature_id": str(signature_record.id),
                "provider": provider,
                "version": version,
                "status": signature_record.status.value,
            },
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
        )

        signature_record.status = DocumentSignatureStatus.SIGNING
        self.db.commit()

        try:
            sign_result = self.document_client.sign(
                DocumentSignRequest(
                    document_id=str(document.id),
                    provider=provider,
                    input=DocumentStorageRef(
                        bucket=pdf_file.bucket,
                        object_key=pdf_file.object_key,
                        sha256=pdf_file.sha256,
                    ),
                    output_bucket=pdf_file.bucket,
                    output_prefix=pdf_file.object_key.rsplit("/", 1)[0],
                    idempotency_key=request_id,
                    meta=meta,
                )
            )
        except Exception as exc:  # noqa: BLE001
            signature_record.status = DocumentSignatureStatus.FAILED
            signature_record.error_code = exc.__class__.__name__
            signature_record.error_message = str(exc)
            signature_record.finished_at = self.now_provider()
            self.db.commit()
            AuditService(self.db).audit(
                event_type="DOCUMENT_SIGN_FAILED",
                entity_type="document",
                entity_id=str(document.id),
                action="UPDATE",
                visibility=AuditVisibility.PUBLIC,
                after={
                    "signature_id": str(signature_record.id),
                    "provider": provider,
                    "status": signature_record.status.value,
                    "error_code": signature_record.error_code,
                },
                request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
            )
            raise

        signature_record.status = DocumentSignatureStatus.SIGNED
        signature_record.request_id = sign_result.provider_request_id
        signature_record.signed_object_key = sign_result.signed.object_key
        signature_record.signed_sha256 = sign_result.signed.sha256
        signature_record.signature_object_key = sign_result.signature.object_key
        signature_record.signature_sha256 = sign_result.signature.sha256
        signature_record.signature_hash_sha256 = sign_result.signature.sha256 or signature_record.signature_hash_sha256
        signature_record.finished_at = self.now_provider()
        signature_record.meta = self._merge_meta(
            signature_record.meta,
            {
                "signed_bucket": sign_result.signed.bucket,
                "signature_bucket": sign_result.signature.bucket,
                "certificate": sign_result.certificate,
            },
        )
        self.db.commit()

        AuditService(self.db).audit(
            event_type="DOCUMENT_SIGNED",
            entity_type="document",
            entity_id=str(document.id),
            action="UPDATE",
            visibility=AuditVisibility.PUBLIC,
            after={
                "signature_id": str(signature_record.id),
                "provider": provider,
                "status": signature_record.status.value,
                "request_id": signature_record.request_id,
            },
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
        )

        return SignResult(signature=signature_record)

    def verify_signature(
        self,
        *,
        document_id: str,
        signature_id: str,
        request=None,
        token: dict | None = None,
    ) -> VerifyResult:
        signature_record = (
            self.db.query(DocumentSignature)
            .filter(DocumentSignature.document_id == document_id)
            .filter(DocumentSignature.id == signature_id)
            .one_or_none()
        )
        if signature_record is None:
            raise ValueError("signature_not_found")
        if not signature_record.signature_object_key or not signature_record.input_object_key:
            raise ValueError("signature_artifact_missing")

        input_bucket = self._bucket_from_meta(signature_record.meta, "input_bucket")
        signature_bucket = self._bucket_from_meta(signature_record.meta, "signature_bucket")
        signed_bucket = self._bucket_from_meta(signature_record.meta, "signed_bucket")

        try:
            verify_result = self.document_client.verify(
                DocumentVerifyRequest(
                    provider=signature_record.provider,
                    input=DocumentStorageRef(
                        bucket=input_bucket,
                        object_key=signature_record.input_object_key,
                        sha256=signature_record.input_sha256,
                    ),
                    signature=DocumentStorageRef(
                        bucket=signature_bucket,
                        object_key=signature_record.signature_object_key,
                        sha256=signature_record.signature_sha256,
                    ),
                    signed=(
                        DocumentStorageRef(
                            bucket=signed_bucket,
                            object_key=signature_record.signed_object_key,
                            sha256=signature_record.signed_sha256,
                        )
                        if signature_record.signed_object_key
                        else None
                    ),
                    meta=signature_record.meta,
                )
            )
        except Exception as exc:  # noqa: BLE001
            signature_record.status = DocumentSignatureStatus.FAILED
            signature_record.error_code = exc.__class__.__name__
            signature_record.error_message = str(exc)
            signature_record.finished_at = self.now_provider()
            self.db.commit()
            AuditService(self.db).audit(
                event_type="DOCUMENT_SIGNATURE_VERIFY_FAILED",
                entity_type="document",
                entity_id=str(document_id),
                action="UPDATE",
                visibility=AuditVisibility.PUBLIC,
                after={
                    "signature_id": str(signature_record.id),
                    "provider": signature_record.provider,
                    "status": signature_record.status.value,
                    "error_code": signature_record.error_code,
                },
                request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
            )
            raise

        signature_record.status = (
            DocumentSignatureStatus.VERIFIED if verify_result.verified else DocumentSignatureStatus.REJECTED
        )
        signature_record.error_code = verify_result.error_code
        signature_record.finished_at = self.now_provider()
        self.db.commit()

        AuditService(self.db).audit(
            event_type="DOCUMENT_SIGNATURE_VERIFIED" if verify_result.verified else "DOCUMENT_SIGNATURE_REJECTED",
            entity_type="document",
            entity_id=str(document_id),
            action="UPDATE",
            visibility=AuditVisibility.PUBLIC,
            after={
                "signature_id": str(signature_record.id),
                "provider": signature_record.provider,
                "status": signature_record.status.value,
                "verified": verify_result.verified,
            },
            request_ctx=request_context_from_request(request, token=_sanitize_token_for_audit(token)),
        )

        return VerifyResult(signature=signature_record, verified=verify_result.verified, status=verify_result.status)

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
        if not file_record.sha256:
            raise ValueError("document_hash_missing")
        return file_record

    def _next_version(self, document_id: str) -> int:
        current = self.db.query(func.max(DocumentSignature.version)).filter(DocumentSignature.document_id == document_id).scalar()
        return (current or 0) + 1

    @staticmethod
    def _merge_meta(base: dict[str, Any] | None, extra: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base or {})
        merged.update(extra)
        return merged

    @staticmethod
    def _bucket_from_meta(meta: dict[str, Any] | None, key: str) -> str:
        if meta and meta.get(key):
            return str(meta[key])
        return settings.NEFT_S3_BUCKET_DOCUMENTS
