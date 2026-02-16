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
        package = ClientDocumentPackage(
            id=new_uuid_str(),
            client_id=client_id,
            application_id=application_id,
            package_kind=package_kind,
            status="BUILDING",
            created_by_user_id=created_by_user_id,
        )
        self.db.add(package)
        self.db.commit()
        self.db.refresh(package)

        try:
            docs = self._select_docs(client_id=client_id, application_id=application_id, doc_ids=doc_ids)
            if not docs:
                raise HTTPException(status_code=400, detail={"reason_code": "no_signed_documents"})
            zip_payload, manifest = self._build_zip(docs)
            checksum = hashlib.sha256(zip_payload).hexdigest()
            key = f"client-doc-packages/{client_id}/{package.id}.zip"
            self.storage.ensure_bucket("client-generated-documents")
            self.storage.put_object("client-generated-documents", key, zip_payload, "application/zip")
            package.storage_key = key
            package.filename = f"signed-documents-{package.id}.zip"
            package.size = len(zip_payload)
            package.checksum_sha256 = checksum
            package.status = "READY"
            package.updated_at = datetime.now(timezone.utc)
            self.db.add(package)
            for idx, item in enumerate(manifest["documents"], start=1):
                self.db.add(
                    ClientDocumentPackageItem(
                        id=new_uuid_str(),
                        package_id=package.id,
                        doc_id=item["doc_id"],
                        source_kind="GENERATED_DOC",
                        storage_key=item["storage_key"],
                        filename=f"{idx:02d}_{item['filename']}",
                        mime="application/pdf",
                        checksum_sha256=item.get("checksum_sha256"),
                    )
                )
            self.db.commit()
            self.db.refresh(package)
            ClientSigningRepository(self.db).create_audit_event(
                client_id=client_id,
                application_id=application_id,
                doc_id=None,
                event_type="PACKAGE_READY",
                actor_user_id=created_by_user_id,
                actor_type="CLIENT_USER",
                ip=None,
                user_agent=None,
                meta_json={"package_id": package.id, "package_kind": package_kind},
            )
            return package
        except Exception:
            package.status = "FAILED"
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

    def _select_docs(self, *, client_id: str, application_id: str | None, doc_ids: list[str] | None) -> list[ClientGeneratedDocument]:
        stmt = select(ClientGeneratedDocument).where(
            ClientGeneratedDocument.client_id == client_id,
            ClientGeneratedDocument.status == "SIGNED_BY_CLIENT",
        )
        if application_id:
            stmt = stmt.where(ClientGeneratedDocument.client_application_id == application_id)
        docs = list(self.db.execute(stmt.order_by(ClientGeneratedDocument.created_at.asc())).scalars().all())
        if doc_ids:
            allowed = set(doc_ids)
            docs = [item for item in docs if str(item.id) in allowed]
        return docs

    def _build_zip(self, docs: list[ClientGeneratedDocument]) -> tuple[bytes, dict]:
        manifest_docs: list[dict] = []
        output = io.BytesIO()
        with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for idx, doc in enumerate(docs, start=1):
                stream = self.storage.get_object_stream("client-generated-documents", doc.storage_key)
                payload = stream.read()
                filename = f"{idx:02d}_{doc.doc_kind}_v{doc.version}_signed.pdf"
                archive.writestr(filename, payload)
                manifest_docs.append(
                    {
                        "doc_id": str(doc.id),
                        "doc_kind": doc.doc_kind,
                        "version": doc.version,
                        "status": doc.status,
                        "storage_key": doc.storage_key,
                        "filename": filename,
                        "checksum_sha256": doc.checksum_sha256,
                        "signed_at": doc.client_signed_at.isoformat() if doc.client_signed_at else None,
                        "sign_method": doc.client_sign_method,
                    }
                )
            manifest = {"documents": manifest_docs, "generated_at": datetime.now(timezone.utc).isoformat()}
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
        return output.getvalue(), manifest
