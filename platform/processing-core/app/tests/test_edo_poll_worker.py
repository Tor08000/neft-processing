from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domains.documents.edo_service import DocumentEdoService
from app.domains.documents.models import Document, DocumentDirection, DocumentEdoState, DocumentStatus
from app.domains.documents.repo import DocumentsRepository


def test_poll_worker_transitions_and_updates_document(test_db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    doc = Document(
        id="00000000-0000-0000-0000-000000000201",
        client_id="client-a",
        direction=DocumentDirection.OUTBOUND.value,
        title="doc",
        status=DocumentStatus.SENT.value,
    )
    test_db_session.add(doc)
    state = DocumentEdoState(
        id="00000000-0000-0000-0000-000000000202",
        document_id=str(doc.id),
        client_id="client-a",
        provider="mock",
        provider_mode="mock",
        edo_status="QUEUED",
        edo_message_id="m-202",
        next_poll_at=now - timedelta(seconds=1),
    )
    test_db_session.add(state)
    test_db_session.commit()

    statuses = iter(["SENT", "DELIVERED"])

    class _Resp:
        status_code = 200

        def __init__(self, status: str):
            self._status = status

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "edo_message_id": "m-202",
                "edo_status": self._status,
                "provider_status_raw": {"stub": True},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

    import app.domains.documents.edo_service as edo_module

    monkeypatch.setattr(edo_module.requests, "get", lambda *a, **k: _Resp(next(statuses)))

    service = DocumentEdoService(repo=DocumentsRepository(db=test_db_session))
    first = service.poll_states(limit=10)
    second = service.poll_states(limit=10)

    assert first["processed"] == 1
    assert second["processed"] == 1

    refreshed_state = test_db_session.query(DocumentEdoState).filter(DocumentEdoState.id == state.id).one()
    refreshed_doc = test_db_session.query(Document).filter(Document.id == doc.id).one()

    assert refreshed_state.edo_status == "DELIVERED"
    assert refreshed_state.next_poll_at is None
    assert refreshed_doc.status == "DELIVERED"

    events = [row.event_type for row in test_db_session.execute("select event_type from document_timeline_events where document_id=:d", {"d": str(doc.id)}).all()]
    assert "EDO_STATUS_CHANGED" in events
