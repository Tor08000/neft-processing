from __future__ import annotations

import pytest

from app.models.billing_job_run import BillingJobRun, BillingJobStatus, BillingJobType
from app.models.billing_task_link import BillingTaskLink, BillingTaskStatus, BillingTaskType
from app.services.billing_task_links import BillingTaskLinkService
from app.tests._scoped_router_harness import scoped_session_context


@pytest.fixture
def session():
    with scoped_session_context(tables=(BillingJobRun.__table__, BillingTaskLink.__table__)) as db:
        yield db


def test_task_link_upsert_updates_status(session):
    job_run = BillingJobRun(job_type=BillingJobType.MANUAL_RUN, status=BillingJobStatus.STARTED)
    session.add(job_run)
    session.commit()
    session.refresh(job_run)

    service = BillingTaskLinkService(session)
    link = service.upsert(
        task_id="task-1",
        task_name="task",
        job_run_id=str(job_run.id),
        task_type=BillingTaskType.PDF_GENERATE,
        status=BillingTaskStatus.QUEUED,
        invoice_id="inv-1",
    )
    session.commit()
    assert link.status == BillingTaskStatus.QUEUED

    updated = service.upsert(
        task_id="task-1",
        task_name="task",
        job_run_id=str(job_run.id),
        task_type=BillingTaskType.PDF_GENERATE,
        status=BillingTaskStatus.SUCCESS,
        invoice_id="inv-1",
    )
    session.commit()

    stored = session.query(BillingTaskLink).filter_by(invoice_id="inv-1").one()
    assert updated.status == BillingTaskStatus.SUCCESS
    assert stored.status == BillingTaskStatus.SUCCESS
