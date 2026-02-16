from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import requests
from fastapi import HTTPException

from app.domains.documents.models import Document, DocumentDirection, DocumentEdoState, DocumentStatus, EdoStatus
from app.domains.documents.repo import DocumentsRepository
from app.domains.documents.timeline_service import DocumentTimelineService, TimelineActorType, TimelineEventType


@dataclass(slots=True)
class EdoHubSendResult:
    edo_message_id: str
    edo_status: str
    provider: str
    provider_mode: str


@dataclass(slots=True)
class EdoHubStatusResult:
    edo_message_id: str
    edo_status: str
    provider_status_raw: dict
    updated_at: datetime | None


class DocumentEdoService:
    def __init__(self, repo: DocumentsRepository):
        self.repo = repo
        self.timeline = DocumentTimelineService(repo=repo)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _is_prod() -> bool:
        return os.getenv("APP_ENV", "dev").lower() == "prod"

    @staticmethod
    def _provider_mode() -> str:
        return os.getenv("EDO_MODE", "real").lower()

    @staticmethod
    def _provider() -> str:
        return os.getenv("EDO_PROVIDER", "").strip().lower()

    @staticmethod
    def _hub_url() -> str:
        return os.getenv("INTEGRATION_HUB_URL", "http://integration-hub:8080").rstrip("/")

    @staticmethod
    def _hub_headers() -> dict[str, str]:
        token = os.getenv("INTEGRATION_HUB_INTERNAL_TOKEN", "")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Internal-Token"] = token
        return headers

    def _poll_interval_seconds(self) -> int:
        if self._is_prod():
            return int(os.getenv("EDO_POLL_INTERVAL_PROD_SECONDS", "30"))
        return int(os.getenv("EDO_POLL_INTERVAL_DEV_SECONDS", "15"))

    def _validate_send_preconditions(self, document: Document, files_count: int) -> None:
        if document.direction != DocumentDirection.OUTBOUND.value:
            raise HTTPException(status_code=409, detail={"error_code": "DOC_NOT_OUTBOUND", "message": "Only outbound documents can be sent"})
        if document.status != DocumentStatus.READY_TO_SEND.value:
            raise HTTPException(status_code=409, detail={"error_code": "DOC_NOT_READY", "message": "Document must be READY_TO_SEND"})
        if files_count < 1:
            raise HTTPException(status_code=409, detail={"error_code": "DOC_FILES_REQUIRED", "message": "At least one file is required"})

    def _guard_prod(self) -> None:
        if not self._is_prod():
            return
        if not self._provider() or self._provider_mode() == "mock":
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "EDO_NOT_CONFIGURED",
                    "message": "EDO provider is not configured for production",
                },
            )

    def _send_to_hub(self, *, document: Document, files: list) -> EdoHubSendResult:
        payload = {
            "idempotency_key": f"doc:{document.id}:v1",
            "provider": self._provider() or "mock",
            "document": {
                "document_id": str(document.id),
                "client_id": str(document.client_id),
                "title": document.title,
                "category": document.category,
                "files": [
                    {
                        "storage_key": file.storage_key,
                        "filename": file.filename,
                        "sha256": file.sha256,
                        "mime": file.mime,
                        "size": file.size,
                    }
                    for file in files
                ],
                "meta": {
                    "counterparty_inn": document.counterparty_inn,
                },
            },
        }
        response = requests.post(
            f"{self._hub_url()}/api/int/v1/edo/send",
            json=payload,
            headers=self._hub_headers(),
            timeout=10,
        )
        response.raise_for_status()
        body = response.json()
        return EdoHubSendResult(
            edo_message_id=body["edo_message_id"],
            edo_status=str(body["edo_status"]).upper(),
            provider=str(body.get("provider") or payload["provider"]).lower(),
            provider_mode=str(body.get("provider_mode") or self._provider_mode()).lower(),
        )

    def _status_from_hub(self, *, edo_message_id: str, provider: str) -> EdoHubStatusResult:
        response = requests.get(
            f"{self._hub_url()}/api/int/v1/edo/{edo_message_id}/status",
            params={"provider": provider},
            headers=self._hub_headers(),
            timeout=10,
        )
        response.raise_for_status()
        body = response.json()
        updated_at = body.get("updated_at")
        parsed_updated = None
        if isinstance(updated_at, str) and updated_at:
            parsed_updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        return EdoHubStatusResult(
            edo_message_id=body["edo_message_id"],
            edo_status=str(body["edo_status"]).upper(),
            provider_status_raw=body.get("provider_status_raw") or {},
            updated_at=parsed_updated,
        )

    def get_edo_state_for_client(self, *, client_id: str, document_id: str) -> DocumentEdoState | None:
        document = self.repo.get_document(client_id=client_id, document_id=document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="document_not_found")
        return self.repo.get_edo_state_for_client(client_id=client_id, document_id=document_id)

    def send_document(self, *, client_id: str, document_id: str, actor_user_id: str | None = None) -> DocumentEdoState:
        document = self.repo.get_document(client_id=client_id, document_id=document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="document_not_found")
        files = self.repo.list_document_files(document_id=document_id)

        self._validate_send_preconditions(document, len(files))
        self._guard_prod()

        existing = self.repo.get_edo_state(document_id=document_id)
        idempotent_statuses = {EdoStatus.SENT.value, EdoStatus.DELIVERED.value, EdoStatus.SIGNED.value, EdoStatus.QUEUED.value, EdoStatus.SENDING.value}
        if existing and existing.edo_status in idempotent_statuses:
            return existing

        now = self._now()
        if existing is None:
            existing = self.repo.create_edo_state(
                id=str(uuid4()),
                document_id=document_id,
                client_id=document.client_id,
                provider=self._provider() or "mock",
                provider_mode=self._provider_mode(),
                edo_status=EdoStatus.NEW.value,
                attempts_send=0,
                attempts_poll=0,
                last_status_at=now,
            )

        existing.edo_status = EdoStatus.SENDING.value
        existing.last_error_code = None
        existing.last_error_message = None
        existing.attempts_send = int(existing.attempts_send or 0) + 1
        existing.last_status_at = now
        self.repo.save_edo_state(existing)
        self.timeline.append_event(
            document,
            event_type="EDO_SEND_REQUESTED",
            meta={"attempt": existing.attempts_send},
            actor_type=TimelineActorType.USER,
            actor_user_id=actor_user_id,
        )

        try:
            result = self._send_to_hub(document=document, files=files)
        except requests.RequestException as exc:
            existing.edo_status = EdoStatus.PROVIDER_UNAVAILABLE.value
            existing.last_error_code = "PROVIDER_UNAVAILABLE"
            existing.last_error_message = str(exc)
            existing.next_poll_at = now + timedelta(seconds=self._poll_interval_seconds())
            self.repo.save_edo_state(existing)
            self.timeline.append_event(
                document,
                event_type="EDO_SEND_FAILED",
                meta={"error_code": "PROVIDER_UNAVAILABLE"},
                actor_type=TimelineActorType.SYSTEM,
                actor_user_id=actor_user_id,
            )
            raise HTTPException(status_code=503, detail={"error_code": "PROVIDER_UNAVAILABLE", "message": "EDO provider unavailable"}) from exc

        existing.provider = result.provider
        existing.provider_mode = result.provider_mode
        existing.edo_status = result.edo_status
        existing.edo_message_id = result.edo_message_id
        existing.last_status_at = now
        existing.next_poll_at = now + timedelta(seconds=self._poll_interval_seconds())
        self.repo.save_edo_state(existing)

        if result.edo_status in {EdoStatus.SENT.value, EdoStatus.QUEUED.value}:
            self.repo.update_document_status(document=document, status=DocumentStatus.SENT.value)

        self.timeline.append_event(
            document,
            event_type="EDO_SEND_ACCEPTED",
            meta={"edo_message_id": result.edo_message_id, "edo_status": result.edo_status},
            actor_type=TimelineActorType.SYSTEM,
            actor_user_id=actor_user_id,
        )
        return existing

    @staticmethod
    def _terminal(edo_status: str) -> bool:
        return edo_status in {EdoStatus.DELIVERED.value, EdoStatus.SIGNED.value, EdoStatus.REJECTED.value}

    @staticmethod
    def _poll_backoff_seconds(attempt: int) -> int:
        schedule = [60, 120, 300, 600, 1800]
        idx = min(max(attempt - 1, 0), len(schedule) - 1)
        return schedule[idx]

    def poll_states(self, *, limit: int = 100) -> dict[str, int]:
        now = self._now()
        items = self.repo.list_edostates_for_poll(now=now, limit=limit)
        processed = 0
        success = 0
        failed = 0

        for state in items:
            processed += 1
            state.attempts_poll = int(state.attempts_poll or 0) + 1
            state.last_polled_at = now
            doc = self.repo.get_document_by_id(document_id=str(state.document_id))
            if doc is None:
                self.repo.save_edo_state(state)
                continue

            if not state.edo_message_id:
                state.edo_status = EdoStatus.ERROR.value
                state.last_error_code = "EDO_POLL_FAILED_NO_MESSAGE_ID"
                state.last_error_message = "Missing edo_message_id"
                state.next_poll_at = now + timedelta(seconds=self._poll_backoff_seconds(state.attempts_poll))
                self.repo.save_edo_state(state)
                self.timeline.append_event(doc, event_type="EDO_POLL_FAILED_NO_MESSAGE_ID", actor_type=TimelineActorType.SYSTEM)
                failed += 1
                continue

            prev_status = state.edo_status
            try:
                status = self._status_from_hub(edo_message_id=state.edo_message_id, provider=state.provider or self._provider() or "mock")
                state.edo_status = status.edo_status
                state.last_status_at = status.updated_at or now
                state.last_error_code = None
                state.last_error_message = None
                success += 1
            except requests.RequestException as exc:
                state.edo_status = EdoStatus.PROVIDER_UNAVAILABLE.value
                state.last_error_code = "PROVIDER_UNAVAILABLE"
                state.last_error_message = str(exc)
                failed += 1

            if state.edo_status in {EdoStatus.QUEUED.value, EdoStatus.SENT.value, EdoStatus.SENDING.value}:
                state.next_poll_at = now + timedelta(seconds=self._poll_interval_seconds())
            elif self._terminal(state.edo_status):
                state.next_poll_at = None
            else:
                state.next_poll_at = now + timedelta(seconds=self._poll_backoff_seconds(state.attempts_poll))

            if state.edo_status != prev_status:
                state.last_status_at = now
                self.timeline.append_event(
                    doc,
                    event_type="EDO_STATUS_CHANGED",
                    meta={"from": prev_status, "to": state.edo_status},
                    actor_type=TimelineActorType.SYSTEM,
                )

            if state.edo_status == EdoStatus.DELIVERED.value:
                self.repo.update_document_status(document=doc, status=DocumentStatus.DELIVERED.value)
            elif state.edo_status == EdoStatus.SIGNED.value:
                self.repo.update_document_status(document=doc, status=DocumentStatus.DELIVERED.value)
            elif state.edo_status == EdoStatus.REJECTED.value:
                self.repo.update_document_status(document=doc, status=DocumentStatus.REJECTED.value)

            self.repo.save_edo_state(state)

        return {"processed": processed, "success": success, "failed": failed}
