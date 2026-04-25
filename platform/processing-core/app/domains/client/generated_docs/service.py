from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException

from app.clients.document_service import DocumentServiceRenderClient
from app.domains.client.generated_docs.models import GeneratedDocStatus
from app.domains.client.generated_docs.repo import ClientGeneratedDocumentsRepository
from app.domains.client.generated_docs.templates import ONBOARDING_TEMPLATES
from app.domains.client.onboarding.documents.storage import OnboardingDocumentsStorage
from app.domains.client.onboarding.models import ClientOnboardingApplication, OnboardingApplicationStatus

_ALLOWED_GENERATE_STATUSES = {
    OnboardingApplicationStatus.IN_REVIEW.value,
    OnboardingApplicationStatus.APPROVED.value,
}


@dataclass(slots=True)
class ClientGeneratedDocsService:
    docs_repo: ClientGeneratedDocumentsRepository
    document_client: DocumentServiceRenderClient
    storage: OnboardingDocumentsStorage

    def generate_for_application(self, application: ClientOnboardingApplication, actor_user_id: str | None = None):
        if application.status not in _ALLOWED_GENERATE_STATUSES:
            raise HTTPException(status_code=409, detail={"reason_code": "application_not_ready_for_doc_generation"})

        bucket = os.getenv("MINIO_BUCKET_CLIENT_GENERATED_DOCS", "client-generated-documents")
        self.storage.ensure_bucket(bucket)
        generated = []
        for template in ONBOARDING_TEMPLATES:
            version = self.docs_repo.get_last_version(
                application_id=str(application.id), client_id=application.client_id, doc_kind=template.doc_kind.value
            ) + 1
            payload = {
                "company_name": application.company_name,
                "inn": application.inn,
                "ogrn": application.ogrn,
                "email": application.email,
                "phone": application.phone,
                "application_id": str(application.id),
                "client_id": application.client_id,
            }
            pdf_bytes = self.document_client.render_pdf(
                template_id=template.template_id,
                data=payload,
                doc_type=template.doc_kind.value,
                version=version,
            )
            storage_key = f"client/onboarding/{application.id}/{template.doc_kind.value}/v{version}.pdf"
            self.storage.put_object(bucket, storage_key, pdf_bytes, "application/pdf")
            filename = template.filename_pattern.format(inn=application.inn or "unknown")
            status = GeneratedDocStatus.GENERATED.value
            platform_signed_at = None
            platform_signature_hash = None
            if self._sign_mode() == "mock":
                status = GeneratedDocStatus.SIGNED_BY_PLATFORM.value
                platform_signed_at = datetime.now(timezone.utc)
                platform_signature_hash = hashlib.sha256(f"platform:{storage_key}".encode("utf-8")).hexdigest()

            generated.append(
                self.docs_repo.create_document(
                    client_application_id=str(application.id),
                    client_id=application.client_id,
                    doc_kind=template.doc_kind.value,
                    version=version,
                    storage_key=storage_key,
                    filename=filename,
                    mime="application/pdf",
                    size=len(pdf_bytes),
                    status=status,
                    template_id=template.template_id,
                    checksum_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
                    created_by_user_id=actor_user_id,
                    platform_signed_at=platform_signed_at,
                    platform_signature_hash=platform_signature_hash,
                )
            )
        return generated

    def _sign_mode(self) -> str:
        mode = os.getenv("PLATFORM_DOC_SIGN_MODE")
        if mode:
            return mode
        app_env = os.getenv("APP_ENV", "prod").lower()
        return "mock" if app_env != "prod" else "disabled"
