from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.config import settings
from app.db import Base, engine, get_sessionmaker
from app.models.accounting_export_batch import (
    AccountingExportBatch,
    AccountingExportFormat,
    AccountingExportState,
    AccountingExportType,
)
from app.models.audit_log import AuditLog
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.services.accounting_export.metrics import metrics as export_metrics
from app.services.accounting_export.monitoring import check_overdue_batches


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _make_period() -> BillingPeriod:
    period_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    period_end = datetime(2024, 1, 31, tzinfo=timezone.utc)
    return BillingPeriod(
        id=str(uuid4()),
        period_type=BillingPeriodType.ADHOC,
        start_at=period_start,
        end_at=period_end,
        tz="UTC",
        status=BillingPeriodStatus.FINALIZED,
        finalized_at=period_start,
    )


def test_accounting_export_sla_breach_emits_audit_and_metrics():
    session = get_sessionmaker()()
    export_metrics.reset()

    period = _make_period()
    session.add(period)
    session.commit()

    now = datetime.now(timezone.utc)
    created_batch = AccountingExportBatch(
        id=str(uuid4()),
        tenant_id=1,
        billing_period_id=period.id,
        export_type=AccountingExportType.CHARGES,
        format=AccountingExportFormat.CSV,
        state=AccountingExportState.CREATED,
        idempotency_key="sla-created",
        created_at=now - timedelta(minutes=settings.ACCOUNTING_EXPORT_SLA_GENERATE_MINUTES + 5),
    )
    generated_batch = AccountingExportBatch(
        id=str(uuid4()),
        tenant_id=1,
        billing_period_id=period.id,
        export_type=AccountingExportType.SETTLEMENT,
        format=AccountingExportFormat.JSON,
        state=AccountingExportState.GENERATED,
        idempotency_key="sla-generated",
        created_at=now - timedelta(hours=settings.ACCOUNTING_EXPORT_SLA_CONFIRM_HOURS + 1),
        generated_at=now - timedelta(hours=settings.ACCOUNTING_EXPORT_SLA_CONFIRM_HOURS + 1),
    )
    session.add_all([created_batch, generated_batch])
    session.commit()

    result = check_overdue_batches(session)
    session.commit()

    assert result == {"overdue": 1, "unconfirmed": 1}
    assert export_metrics.overdue_batches_total == 1
    assert export_metrics.unconfirmed_batches_total == 1

    events = session.query(AuditLog).filter(AuditLog.event_type == "ACCOUNTING_EXPORT_SLA_BREACH").all()
    assert len(events) == 2
    session.close()
