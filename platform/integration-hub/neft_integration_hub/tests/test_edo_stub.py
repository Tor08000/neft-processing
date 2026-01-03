from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytest.importorskip("neft_integration_hub")

from neft_integration_hub.db import Base
from neft_integration_hub.models import EdoStubStatus
from neft_integration_hub.services.edo_stub import create_stub_document, get_stub_document, simulate_status


def _make_sqlite_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)()


def test_stub_document_lifecycle_with_simulation():
    db = _make_sqlite_session()
    record = create_stub_document(
        db,
        document_id="doc-1",
        counterparty={"inn": "7700000000"},
        payload_ref="payload-1",
    )

    assert record.status == EdoStubStatus.SENT.value

    record = simulate_status(db, record.id, EdoStubStatus.SIGNED)
    assert record is not None
    assert record.status == EdoStubStatus.SIGNED.value

    refreshed = get_stub_document(db, record.id)
    assert refreshed is not None
    assert refreshed.status == EdoStubStatus.SIGNED.value
