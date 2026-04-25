from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import requests
from fastapi import HTTPException

from app.domains.client.generated_docs.models import ClientGeneratedDocument, GeneratedDocStatus
from app.domains.client.docflow.notifications import ClientDocflowNotificationsService
from app.domains.client.generated_docs.repo import ClientGeneratedDocumentsRepository
from app.domains.client.signing.otp import generate_otp_code, generate_otp_salt, hash_otp_code, verify_otp_code
from app.domains.client.signing.repo import ClientSigningRepository

_ALLOWED_DOC_STATUSES = {GeneratedDocStatus.GENERATED.value, GeneratedDocStatus.SIGNED_BY_PLATFORM.value}


def _normalize_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(slots=True)
class ClientDocumentSigningService:
    docs_repo: ClientGeneratedDocumentsRepository
    sign_repo: ClientSigningRepository

    def _otp_enabled(self) -> bool:
        return os.getenv("OTP_ENABLED", "1") == "1"

    def _otp_channels_allowed(self) -> set[str]:
        return {item.strip().lower() for item in os.getenv("OTP_CHANNELS_ALLOWED", "sms,telegram").split(",") if item.strip()}

    def _otp_default_channel(self) -> str:
        return os.getenv("OTP_DEFAULT_CHANNEL", "sms").lower()

    def _otp_ttl_seconds(self) -> int:
        return int(os.getenv("OTP_TTL_SECONDS", "300"))

    def _otp_resend_cooldown_seconds(self) -> int:
        return int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "60"))

    def _otp_max_attempts(self) -> int:
        return int(os.getenv("OTP_MAX_ATTEMPTS", "5"))

    def _otp_rate_limit(self) -> int:
        return int(os.getenv("OTP_RATE_LIMIT_PER_USER_PER_MINUTE", "3"))

    def _otp_force_reauth_seconds(self) -> int:
        return int(os.getenv("OTP_FORCE_REAUTH_SECONDS", "600"))

    def _otp_pepper(self) -> str:
        return os.getenv("OTP_SERVER_PEPPER", "dev-pepper")

    def _hub_url(self) -> str:
        return os.getenv("INTEGRATION_HUB_URL", "http://integration-hub:8080").rstrip("/")

    def _hub_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        token = os.getenv("INTEGRATION_HUB_INTERNAL_TOKEN", "")
        if token:
            headers["X-Internal-Token"] = token
        return headers

    def _mask_destination(self, channel: str, destination: str) -> str:
        if channel == "sms":
            digits = "".join(ch for ch in destination if ch.isdigit())
            if len(digits) <= 4:
                return "*" * len(digits)
            return f"+{digits[0]}***{digits[-4:]}"
        if len(destination) <= 4:
            return "****"
        return f"{destination[:2]}***{destination[-2:]}"

    def _require_recent_auth(self, token_iat: int | None) -> None:
        if token_iat is None:
            raise HTTPException(status_code=401, detail={"error_code": "reauth_required", "message": "Recent authentication is required"})
        token_age = int(datetime.now(timezone.utc).timestamp()) - int(token_iat)
        if token_age > self._otp_force_reauth_seconds():
            raise HTTPException(status_code=401, detail={"error_code": "reauth_required", "message": "Recent authentication is required"})

    def request_otp(self, *, doc: ClientGeneratedDocument, user_id: str, channel: str | None, destination: str, token_iat: int | None, ip: str | None, user_agent: str | None) -> dict:
        if not self._otp_enabled():
            raise HTTPException(status_code=409, detail={"error_code": "otp_disabled", "message": "OTP signing is disabled"})
        self._validate_doc_ready_for_signing(doc)
        self._require_recent_auth(token_iat)

        selected_channel = (channel or self._otp_default_channel()).lower()
        if selected_channel not in self._otp_channels_allowed():
            raise HTTPException(status_code=400, detail={"error_code": "otp_channel_not_allowed", "message": "OTP channel is not allowed"})

        if self.sign_repo.count_recent_starts(user_id=user_id, window_seconds=60) >= self._otp_rate_limit():
            raise HTTPException(status_code=429, detail={"error_code": "otp_rate_limited", "message": "Too many OTP requests"})

        existing = self.sign_repo.get_active_challenge(document_id=str(doc.id), user_id=user_id)
        now = datetime.now(timezone.utc)
        if existing and _normalize_utc_datetime(existing.resend_available_at) > now:
            raise HTTPException(status_code=429, detail={"error_code": "otp_resend_cooldown", "message": "OTP resend cooldown is active"})
        if existing:
            existing.status = "EXPIRED"
            self.sign_repo.save_challenge(existing)

        code = "000000" if self._test_mode() else generate_otp_code()
        salt = generate_otp_salt()
        challenge = self.sign_repo.create_otp_challenge(
            purpose="DOC_SIGN",
            document_id=str(doc.id),
            client_id=str(doc.client_id) if doc.client_id is not None else None,
            user_id=user_id,
            channel=selected_channel,
            destination=destination,
            code_hash=hash_otp_code(code, salt=salt, pepper=self._otp_pepper()),
            salt=salt,
            status="PENDING",
            max_attempts=self._otp_max_attempts(),
            expires_at=now + timedelta(seconds=self._otp_ttl_seconds()),
            resend_available_at=now + timedelta(seconds=self._otp_resend_cooldown_seconds()),
            request_ip=ip,
            request_user_agent=user_agent,
        )
        try:
            provider_message_id = self._send_otp_to_hub(doc=doc, challenge_id=challenge.id, channel=selected_channel, destination=destination, code=code)
            challenge.status = "SENT"
            challenge.provider_message_id = provider_message_id
            self.sign_repo.save_challenge(challenge)
        except requests.RequestException:
            challenge.status = "FAILED"
            challenge.error_code = "otp_delivery_failed"
            self.sign_repo.save_challenge(challenge)
            raise HTTPException(status_code=503, detail={"error_code": "otp_delivery_failed", "message": "OTP delivery failed"})

        result = {
            "challenge_id": challenge.id,
            "expires_at": challenge.expires_at,
            "resend_available_at": challenge.resend_available_at,
            "channel": selected_channel,
            "masked_destination": self._mask_destination(selected_channel, destination),
        }
        if self._test_mode():
            result["otp_code"] = code
        return result

    def _send_otp_to_hub(self, *, doc: ClientGeneratedDocument, challenge_id: str, channel: str, destination: str, code: str) -> str:
        if self._test_mode():
            return f"otp-test:{challenge_id}"
        text = f"NEFT: код для подписи документа {code}. Действует {max(1, self._otp_ttl_seconds() // 60)} минут."
        payload = {
            "channel": channel,
            "destination": destination,
            "message": text,
            "idempotency_key": f"otp:{challenge_id}",
            "meta": {
                "client_id": str(doc.client_id) if doc.client_id is not None else None,
                "user_id": str(doc.client_application_id or ""),
                "document_id": str(doc.id),
            },
        }
        response = requests.post(f"{self._hub_url()}/api/int/v1/otp/send", json=payload, headers=self._hub_headers(), timeout=10)
        response.raise_for_status()
        return str(response.json()["provider_message_id"])

    def confirm_otp(self, *, doc: ClientGeneratedDocument, user_id: str, challenge_id: str, otp_code: str, ip: str | None, user_agent: str | None) -> ClientGeneratedDocument:
        self._validate_doc_ready_for_signing(doc)
        challenge = self.sign_repo.get_challenge(challenge_id)
        if challenge is None or str(challenge.document_id) != str(doc.id) or str(challenge.user_id) != user_id:
            raise HTTPException(status_code=404, detail={"error_code": "otp_not_found", "message": "OTP challenge not found"})
        if challenge.status == "USED":
            raise HTTPException(status_code=409, detail={"error_code": "otp_already_used", "message": "OTP challenge is already used"})
        if challenge.status == "LOCKED":
            raise HTTPException(status_code=429, detail={"error_code": "otp_locked", "message": "OTP challenge is locked"})
        if challenge.status not in {"SENT", "CONFIRMED"}:
            raise HTTPException(status_code=400, detail={"error_code": "otp_not_found", "message": "OTP challenge is not active"})

        now = datetime.now(timezone.utc)
        if _normalize_utc_datetime(challenge.expires_at) <= now:
            challenge.status = "EXPIRED"
            self.sign_repo.save_challenge(challenge)
            raise HTTPException(status_code=400, detail={"error_code": "otp_expired", "message": "OTP challenge expired"})

        if challenge.attempts >= challenge.max_attempts:
            challenge.status = "LOCKED"
            self.sign_repo.save_challenge(challenge)
            raise HTTPException(status_code=429, detail={"error_code": "otp_locked", "message": "OTP challenge is locked"})

        if not verify_otp_code(otp_code, challenge.code_hash, salt=challenge.salt, pepper=self._otp_pepper()):
            challenge.attempts += 1
            if challenge.attempts >= challenge.max_attempts:
                challenge.status = "LOCKED"
                self.sign_repo.save_challenge(challenge)
                raise HTTPException(status_code=429, detail={"error_code": "otp_locked", "message": "OTP challenge is locked"})
            self.sign_repo.save_challenge(challenge)
            raise HTTPException(status_code=400, detail={"error_code": "otp_invalid_code", "message": "Invalid OTP code"})

        challenge.status = "CONFIRMED"
        self.sign_repo.save_challenge(challenge)
        signature_hash = self._build_signature_hash(doc=doc, user_id=user_id, request_id=challenge_id)
        doc = self.docs_repo.mark_client_signed(doc, sign_method="SIMPLE_OTP", sign_phone=challenge.destination if challenge.channel == "sms" else None, signature_hash=signature_hash)
        challenge.status = "USED"
        challenge.used_at = now
        self.sign_repo.save_challenge(challenge)

        self.sign_repo.create_audit_event(
            client_id=doc.client_id,
            application_id=doc.client_application_id,
            doc_id=str(doc.id),
            event_type="DOC_SIGNED_BY_CLIENT",
            actor_user_id=user_id,
            actor_type="CLIENT_USER",
            ip=ip,
            user_agent=user_agent,
            meta_json={"challenge_id": challenge_id, "channel": challenge.channel, "masked_destination": self._mask_destination(challenge.channel, challenge.destination)},
        )
        notification_owner = str(doc.client_id or doc.client_application_id or "")
        if notification_owner:
            ClientDocflowNotificationsService(self.sign_repo.db).create(
                client_id=notification_owner,
                user_id=user_id,
                title="Документ подписан",
                body="Вы успешно подписали документ.",
                event_type="DOC_SIGNED_BY_CLIENT",
                meta_json={"doc_id": str(doc.id)},
            )
        return doc


    def sign_mode(self) -> str:
        return "otp"

    def checkbox_sign(self, *, doc: ClientGeneratedDocument, user_id: str, consent: bool, ip: str | None, user_agent: str | None) -> ClientGeneratedDocument:
        raise HTTPException(status_code=409, detail={"error_code": "checkbox_mode_disabled", "message": "Checkbox mode is disabled"})

    def _validate_doc_ready_for_signing(self, doc: ClientGeneratedDocument) -> None:
        if doc.status == GeneratedDocStatus.SIGNED_BY_CLIENT.value:
            raise HTTPException(status_code=409, detail={"error_code": "already_signed", "message": "Document is already signed"})
        if doc.status not in _ALLOWED_DOC_STATUSES:
            raise HTTPException(status_code=409, detail={"error_code": "doc_not_ready_to_sign", "message": "Document is not ready to sign"})

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

    def _test_mode(self) -> bool:
        return os.getenv("APP_ENV", "prod").lower() != "prod" and os.getenv("OTP_TEST_MODE", "0") == "1"
