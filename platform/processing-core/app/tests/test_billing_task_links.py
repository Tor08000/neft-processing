from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.billing_task_link import BillingTaskLink, BillingTaskStatus, BillingTaskType
from app.services.billing_task_links import BillingTaskLinkService


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_task_link_upsert_updates_status(session):
    service = BillingTaskLinkService(session)
    link = service.upsert(
        invoice_id="inv-1",
        task_type=BillingTaskType.PDF_GENERATE,
        task_id="task-1",
        status=BillingTaskStatus.QUEUED,
    )
    session.commit()
    assert link.status == BillingTaskStatus.QUEUED

    updated = service.upsert(
        invoice_id="inv-1",
        task_type=BillingTaskType.PDF_GENERATE,
        task_id="task-1",
        status=BillingTaskStatus.SUCCESS,
    )
    session.commit()

    stored = session.query(BillingTaskLink).filter_by(invoice_id="inv-1").one()
    assert updated.status == BillingTaskStatus.SUCCESS
    assert stored.status == BillingTaskStatus.SUCCESS
