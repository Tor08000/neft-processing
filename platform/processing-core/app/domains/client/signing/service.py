from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.domains.client.generated_docs.models import ClientGeneratedDocument, GeneratedDocStatus
from app.domains.client.docflow.notifications import ClientDocflowNotificationsService
from app.domains.client.generated_docs.repo import ClientGeneratedDocumentsRepository
from app.domains.client.signing.otp import generate_otp_code, hash_otp_code, verify_otp_code
from app.domains.client.signing.repo import ClientSigningRepository

_ALLOWED_DOC_STATUSES = {
    GeneratedDocStatus.GENERATED.value,
    GeneratedDocStatus.SIGNED_BY_PLATFORM.value,
}


@dataclass(slots=True)
class ClientDocumentSigningService:
    docs_repo: ClientGeneratedDocumentsRepository
    sign_repo: ClientSigningRepository

    def sign_mode(self) -> str:
        mode = os.getenv("CLIENT_SIGN_MODE")
        if mode:
            return mode
        app_env = os.getenv("APP_ENV", "prod").lower()
        return "otp" if app_env == "prod" else "otp"

    def request_otp(
        self,
        *,
        doc: ClientGeneratedDocument,
        user_id: str,
        phone: str,
        consent: bool,
        ip: str | None,
        user_agent: str | None,
    ) -> dict:
        if not consent:
            raise HTTPException(status_code=400, detail={"reason_code": "consent_required"})
        self._validate_doc_ready_for_signing(doc)

        ttl = int(os.getenv("OTP_TTL_SECONDS", "300"))
        max_attempts = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
        code = generate_otp_code()
        req = self.sign_repo.create_sign_request(
            doc_id=str(doc.id),
            user_id=user_id,
            phone=phone,
            otp_hash=hash_otp_code(code),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl),
            max_attempts=max_attempts,
            request_ip=ip,
            request_user_agent=user_agent,
        )
        self.sign_repo.create_audit_event(
            client_id=doc.client_id,
            application_id=doc.client_application_id,
            doc_id=str(doc.id),
            event_type="DOC_SIGN_REQUESTED",
            actor_user_id=user_id,
            actor_type="CLIENT_USER",
            ip=ip,
            user_agent=user_agent,
            meta_json={"request_id": req.id, "phone": phone},
        )

        result = {"request_id": str(req.id), "expires_at": req.expires_at}
        if self._allow_echo_otp():
            result["otp_code"] = code
        return result

    def confirm_otp(
        self,
        *,
        doc: ClientGeneratedDocument,
        user_id: str,
        request_id: str,
        otp_code: str,
        ip: str | None,
        user_agent: str | None,
    ) -> ClientGeneratedDocument:
        self._validate_doc_ready_for_signing(doc)
        req = self.sign_repo.get_request(request_id)
        if req is None or str(req.doc_id) != str(doc.id) or str(req.user_id) != user_id:
            raise HTTPException(status_code=403, detail={"reason_code": "sign_request_forbidden"})

        now = datetime.now(timezone.utc)
        if req.status != "PENDING":
            if req.status == "EXPIRED":
                raise HTTPException(status_code=400, detail={"reason_code": "otp_expired"})
            if req.attempts >= req.max_attempts:
                raise HTTPException(status_code=429, detail={"reason_code": "too_many_attempts"})
            raise HTTPException(status_code=400, detail={"reason_code": "invalid_request_status"})

        if req.expires_at <= now:
            self.sign_repo.mark_expired(req)
            raise HTTPException(status_code=400, detail={"reason_code": "otp_expired"})

        if not verify_otp_code(otp_code, req.otp_hash):
            req = self.sign_repo.increment_attempts(req)
            self.sign_repo.create_audit_event(
                client_id=doc.client_id,
                application_id=doc.client_application_id,
                doc_id=str(doc.id),
                event_type="DOC_SIGN_FAILED",
                actor_user_id=user_id,
                actor_type="CLIENT_USER",
                ip=ip,
                user_agent=user_agent,
                meta_json={"request_id": request_id, "attempts": req.attempts},
            )
            if req.attempts >= req.max_attempts:
                raise HTTPException(status_code=429, detail={"reason_code": "too_many_attempts"})
            raise HTTPException(status_code=400, detail={"reason_code": "otp_invalid"})

        self.sign_repo.mark_verified(req)
        self.sign_repo.create_audit_event(
            client_id=doc.client_id,
            application_id=doc.client_application_id,
            doc_id=str(doc.id),
            event_type="DOC_SIGN_VERIFIED",
            actor_user_id=user_id,
            actor_type="CLIENT_USER",
            ip=ip,
            user_agent=user_agent,
            meta_json={"request_id": request_id},
        )
        signature_hash = self._build_signature_hash(doc=doc, user_id=user_id, request_id=request_id)
        doc = self.docs_repo.mark_client_signed(
            doc,
            sign_method="OTP",
            sign_phone=req.phone,
            signature_hash=signature_hash,
        )
        self.sign_repo.create_audit_event(
            client_id=doc.client_id,
            application_id=doc.client_application_id,
            doc_id=str(doc.id),
            event_type="DOC_SIGNED_BY_CLIENT",
            actor_user_id=user_id,
            actor_type="CLIENT_USER",
            ip=ip,
            user_agent=user_agent,
            meta_json={"request_id": request_id, "signature_hash": signature_hash},
        )
        self.sign_repo.create_audit_event(
            client_id=doc.client_id,
            application_id=doc.client_application_id,
            doc_id=str(doc.id),
            event_type="DOC_EFFECTIVE",
            actor_user_id=user_id,
            actor_type="CLIENT_USER",
            ip=ip,
            user_agent=user_agent,
            meta_json={"request_id": request_id},
        )
        if doc.client_id:
            ClientDocflowNotificationsService(self.sign_repo.db).create(
                client_id=str(doc.client_id),
                user_id=user_id,
                title="Документ подписан",
                body="Вы успешно подписали документ.",
                event_type="DOC_SIGNED_BY_CLIENT",
                meta_json={"doc_id": str(doc.id)},
            )
        return doc

    def checkbox_sign(self, *, doc: ClientGeneratedDocument, user_id: str, consent: bool, ip: str | None, user_agent: str | None) -> ClientGeneratedDocument:
        if not consent:
            raise HTTPException(status_code=400, detail={"reason_code": "consent_required"})
        self._validate_doc_ready_for_signing(doc)
        signature_hash = self._build_signature_hash(doc=doc, user_id=user_id, request_id=f"checkbox:{doc.id}")
        doc = self.docs_repo.mark_client_signed(
            doc,
            sign_method="CHECKBOX",
            sign_phone=None,
            signature_hash=signature_hash,
        )
        self.sign_repo.create_audit_event(
            client_id=doc.client_id,
            application_id=doc.client_application_id,
            doc_id=str(doc.id),
            event_type="DOC_SIGNED_BY_CLIENT",
            actor_user_id=user_id,
            actor_type="CLIENT_USER",
            ip=ip,
            user_agent=user_agent,
            meta_json={"signature_hash": signature_hash, "sign_method": "CHECKBOX"},
        )
        self.sign_repo.create_audit_event(
            client_id=doc.client_id,
            application_id=doc.client_application_id,
            doc_id=str(doc.id),
            event_type="DOC_EFFECTIVE",
            actor_user_id=user_id,
            actor_type="CLIENT_USER",
            ip=ip,
            user_agent=user_agent,
            meta_json={"sign_method": "CHECKBOX"},
        )
        if doc.client_id:
            ClientDocflowNotificationsService(self.sign_repo.db).create(
                client_id=str(doc.client_id),
                user_id=user_id,
                title="Документ подписан",
                body="Вы успешно подписали документ.",
                event_type="DOC_SIGNED_BY_CLIENT",
                meta_json={"doc_id": str(doc.id)},
            )
        return doc

    def _validate_doc_ready_for_signing(self, doc: ClientGeneratedDocument) -> None:
        if doc.status == GeneratedDocStatus.SIGNED_BY_CLIENT.value:
            raise HTTPException(status_code=409, detail={"reason_code": "already_signed"})
        if doc.status not in _ALLOWED_DOC_STATUSES:
            raise HTTPException(status_code=409, detail={"reason_code": "document_not_signable"})

    def _build_signature_hash(self, *, doc: ClientGeneratedDocument, user_id: str, request_id: str) -> str:
        payload = {
            "doc_id": str(doc.id),
            "doc_kind": doc.doc_kind,
            "version": doc.version,
            "storage_key": doc.storage_key,
            "checksum_sha256": doc.checksum_sha256,
            "user_id": user_id,
            "request_id": request_id,
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _allow_echo_otp(self) -> bool:
        app_env = os.getenv("APP_ENV", "prod").lower()
        if app_env == "prod":
            return False
        return os.getenv("OTP_PROVIDER_STUB_ECHO_CODE", "0") == "1"
