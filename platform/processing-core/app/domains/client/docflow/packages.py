from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.types import new_uuid_str
from app.domains.client.docflow.models import ClientDocumentPackage, ClientDocumentPackageItem
from app.domains.client.generated_docs.models import ClientGeneratedDocument
from app.domains.client.onboarding.documents.storage import OnboardingDocumentsStorage
from app.domains.client.signing.repo import ClientSigningRepository


@dataclass(slots=True)
class ClientDocflowPackagesService:
    db: Session
    storage: OnboardingDocumentsStorage

    def create_onboarding_signed_package(
        self,
        *,
        client_id: str,
        application_id: str | None,
        created_by_user_id: str | None,
        doc_ids: list[str] | None = None,
        package_kind: str = "ONBOARDING_SIGNED_SET",
    ) -> ClientDocumentPackage:
        selected_ids = doc_ids or [
            str(row.id)
            for row in self.db.execute(
                select(ClientGeneratedDocument.id).where(
                    ClientGeneratedDocument.client_id == client_id,
                    ClientGeneratedDocument.status == "SIGNED_BY_CLIENT",
                )
            ).scalars().all()
        ]
        package = self.create_documents_package(client_id=client_id, created_by_user_id=created_by_user_id, doc_ids=selected_ids)
        return self.build_package(package.id)

    def create_documents_package(
        self,
        *,
        client_id: str,
        created_by_user_id: str | None,
        doc_ids: list[str],
    ) -> ClientDocumentPackage:
        docs = self._select_docs(client_id=client_id, doc_ids=doc_ids)
        if len(docs) != len(set(doc_ids)):
            raise HTTPException(status_code=403, detail={"reason_code": "document_forbidden"})

        package = ClientDocumentPackage(
            id=new_uuid_str(),
            client_id=client_id,
            application_id=None,
            package_kind="DOCUMENTS_EXPORT",
            status="CREATING",
            created_by_user_id=created_by_user_id,
        )
        self.db.add(package)
        self.db.commit()
        self.db.refresh(package)

        for doc in docs:
            self.db.add(
                ClientDocumentPackageItem(
                    id=new_uuid_str(),
                    package_id=package.id,
                    doc_id=str(doc.id),
                    source_kind="GENERATED_DOC",
                    storage_key=doc.storage_key,
                    filename=doc.filename,
                    mime=doc.mime,
                    checksum_sha256=doc.checksum_sha256,
                )
            )
        self.db.commit()
        return package

    def build_package(self, package_id: str) -> ClientDocumentPackage:
        package = self.get_package(package_id)
        if package is None:
            raise HTTPException(status_code=404, detail={"reason_code": "package_not_found"})
        items = list(
            self.db.execute(select(ClientDocumentPackageItem).where(ClientDocumentPackageItem.package_id == package_id)).scalars().all()
        )
        try:
            zip_payload, checksum = self._build_zip(items)
            key = f"client-doc-packages/{package.client_id}/{package.id}.zip"
            self.storage.ensure_bucket("client-generated-documents")
            self.storage.put_object("client-generated-documents", key, zip_payload, "application/zip")
            package.storage_key = key
            package.filename = f"documents-package-{package.id}.zip"
            package.size = len(zip_payload)
            package.checksum_sha256 = checksum
            package.sha256 = checksum
            package.status = "READY"
            package.error_code = None
            package.updated_at = datetime.now(timezone.utc)
            self.db.add(package)
            self.db.commit()
            self.db.refresh(package)
            return package
        except Exception:
            package.status = "FAILED"
            package.error_code = "package_build_failed"
            self.db.add(package)
            self.db.commit()
            raise

    def list_packages(self, *, client_id: str, application_id: str | None = None) -> list[ClientDocumentPackage]:
        stmt = select(ClientDocumentPackage).where(ClientDocumentPackage.client_id == client_id)
        if application_id:
            stmt = stmt.where(ClientDocumentPackage.application_id == application_id)
        stmt = stmt.order_by(ClientDocumentPackage.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def get_package(self, package_id: str) -> ClientDocumentPackage | None:
        return self.db.get(ClientDocumentPackage, package_id)

    def _select_docs(self, *, client_id: str, doc_ids: list[str]) -> list[ClientGeneratedDocument]:
        if not doc_ids:
            raise HTTPException(status_code=400, detail={"reason_code": "empty_ids"})
        stmt = select(ClientGeneratedDocument).where(
            ClientGeneratedDocument.client_id == client_id,
            ClientGeneratedDocument.id.in_(doc_ids),
        )
        return list(self.db.execute(stmt).scalars().all())

    def _build_zip(self, items: list[ClientDocumentPackageItem]) -> tuple[bytes, str]:
        output = io.BytesIO()
        with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in items:
                stream = self.storage.get_object_stream("client-generated-documents", item.storage_key)
                payload = stream.read()
                doc_kind = "DOC"
                doc_title = (item.filename or "document").replace(".pdf", "")
                prefix = "outbound"
                filename = f"{prefix}/{datetime.now(timezone.utc).date()}_{doc_kind}_{doc_title}_{str(item.doc_id)[:8]}.pdf"
                archive.writestr(filename, payload)
                archive.writestr(
                    f"signatures/{item.doc_id}.json",
                    json.dumps({"doc_id": item.doc_id, "checksum": item.checksum_sha256}, ensure_ascii=False),
                )
        raw = output.getvalue()
        return raw, hashlib.sha256(raw).hexdigest()
