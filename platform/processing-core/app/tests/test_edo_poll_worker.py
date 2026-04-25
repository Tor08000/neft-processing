from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.domains.documents.edo_service import DocumentEdoService
from app.domains.documents.models import Document, DocumentDirection, DocumentEdoState, DocumentStatus, DocumentTimelineEvent
from app.domains.documents.repo import DocumentsRepository


def _clone_tables_without_duplicate_indexes(*tables):
    metadata = MetaData()
    cloned_tables = []
    for table in tables:
        cloned = table.to_metadata(metadata)
        seen = set()
        for index in list(cloned.indexes):
            if index.name in seen:
                cloned.indexes.remove(index)
            else:
                seen.add(index.name)
        cloned_tables.append(cloned)
    return cloned_tables


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    for table in _clone_tables_without_duplicate_indexes(
        Document.__table__,
        DocumentTimelineEvent.__table__,
        DocumentEdoState.__table__,
    ):
        table.create(bind=engine, checkfirst=True)

    testing_session_local = sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_poll_worker_transitions_and_updates_document(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    doc = Document(
        id="00000000-0000-0000-0000-000000000201",
        tenant_id=0,
        client_id="client-a",
        document_type="ACT",
        period_from=date(2025, 1, 1),
        period_to=date(2025, 1, 1),
        direction=DocumentDirection.OUTBOUND.value,
        title="doc",
        status=DocumentStatus.SENT.value,
        version=1,
    )
    db_session.add(doc)
    state = DocumentEdoState(
        id="00000000-0000-0000-0000-000000000202",
        document_id=str(doc.id),
        client_id="client-a",
        provider="diadok",
        provider_mode="mock",
        edo_status="QUEUED",
        edo_message_id="m-202",
        next_poll_at=now - timedelta(seconds=1),
    )
    db_session.add(state)
    db_session.commit()

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
                "provider_status_raw": {"provider": "diadok"},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

    import app.domains.documents.edo_service as edo_module

    monkeypatch.setattr(edo_module.requests, "get", lambda *a, **k: _Resp(next(statuses)))

    service = DocumentEdoService(repo=DocumentsRepository(db=db_session))
    first = service.poll_states(limit=10)

    assert first["processed"] == 1

    refreshed_state = db_session.query(DocumentEdoState).filter(DocumentEdoState.id == state.id).one()
    assert refreshed_state.edo_status == "SENT"
    assert refreshed_state.next_poll_at is not None

    refreshed_state.next_poll_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    second = service.poll_states(limit=10)
    assert second["processed"] == 1

    refreshed_state = db_session.query(DocumentEdoState).filter(DocumentEdoState.id == state.id).one()
    refreshed_doc = db_session.query(Document).filter(Document.id == doc.id).one()

    assert refreshed_state.edo_status == "DELIVERED"
    assert refreshed_state.next_poll_at is None
    assert refreshed_doc.status == "DELIVERED"

    events = [
        row.event_type
        for row in db_session.execute(
            text("select event_type from document_timeline_events where document_id=:d"),
            {"d": str(doc.id)},
        ).all()
    ]
    assert "EDO_STATUS_CHANGED" in events
