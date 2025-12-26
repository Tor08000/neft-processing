from datetime import datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.accounting_export_batch import AccountingExportFormat, AccountingExportType
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.models.risk_policy import RiskPolicy
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.services.accounting_export_service import AccountingExportRiskDeclined, AccountingExportService


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_accounting_export_blocked_by_thresholds():
    session = SessionLocal()
    try:
        threshold_set = RiskThresholdSet(
            id="exports_v4",
            subject_type=RiskSubjectType.EXPORT,
            scope=RiskThresholdScope.GLOBAL,
            action=RiskThresholdAction.EXPORT,
            block_threshold=10,
            review_threshold=5,
            allow_threshold=0,
            valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        policy = RiskPolicy(
            id="EXPORT_POLICY",
            subject_type=RiskSubjectType.EXPORT,
            tenant_id=None,
            client_id=None,
            provider=None,
            currency=None,
            country=None,
            threshold_set_id="exports_v4",
            model_selector="risk_v4",
            priority=10,
            active=True,
        )
        period = BillingPeriod(
            period_type=BillingPeriodType.ADHOC,
            start_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            tz="UTC",
            status=BillingPeriodStatus.FINALIZED,
        )
        session.add_all([threshold_set, policy, period])
        session.commit()

        service = AccountingExportService(session)
        token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "tenant_id": 1, "sub": "admin-1"}
        with pytest.raises(AccountingExportRiskDeclined, match="risk_decline"):
            service.create_export(
                period_id=period.id,
                export_type=AccountingExportType.CHARGES,
                export_format=AccountingExportFormat.CSV,
                request_ctx=None,
                token=token,
            )
    finally:
        session.close()
