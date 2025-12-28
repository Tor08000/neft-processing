from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.billing_period import BillingPeriod, BillingPeriodStatus, BillingPeriodType
from app.services.billing_periods import BillingPeriodConflict, BillingPeriodService


@pytest.fixture()
def sqlite_session():
    engine = sa.create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine, tables=[BillingPeriod.__table__])
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    try:
        session = SessionLocal()
        yield session
    finally:
        session.close()
        engine.dispose()


def test_billing_period_insert_default_status_and_uuid(sqlite_session):
    start_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)

    period = BillingPeriod(
        period_type=BillingPeriodType.DAILY,
        start_at=start_at,
        end_at=end_at,
        tz="UTC",
    )

    sqlite_session.add(period)
    sqlite_session.commit()
    sqlite_session.refresh(period)

    assert period.id is not None
    assert period.id == str(uuid.UUID(period.id))
    assert period.status == BillingPeriodStatus.OPEN
    assert period.created_at is not None


def test_billing_period_unique_scope(sqlite_session):
    start_at = datetime(2024, 2, 1, tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)

    first = BillingPeriod(
        period_type=BillingPeriodType.DAILY,
        start_at=start_at,
        end_at=end_at,
        tz="UTC",
    )
    sqlite_session.add(first)
    sqlite_session.commit()

    duplicate = BillingPeriod(
        period_type=BillingPeriodType.DAILY,
        start_at=start_at,
        end_at=end_at,
        tz="UTC",
    )
    sqlite_session.add(duplicate)

    with pytest.raises(sa.exc.IntegrityError):
        sqlite_session.commit()
    sqlite_session.rollback()


def test_billing_period_indexes_exist(sqlite_session):
    inspector = sa.inspect(sqlite_session.get_bind())
    index_names = {index["name"] for index in inspector.get_indexes("billing_periods")}

    assert {
        "ix_billing_periods_type_start",
        "ix_billing_periods_status",
        "ix_billing_periods_start_at",
    }.issubset(index_names)


def test_lock_and_finalize_flow(sqlite_session):
    service = BillingPeriodService(sqlite_session)
    start_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)
    token = {"roles": ["ADMIN", "ADMIN_FINANCE"], "sub": "tester"}

    finalized = service.finalize(
        period_type=BillingPeriodType.DAILY,
        start_at=start_at,
        end_at=end_at,
        tz="UTC",
        token=token,
    )
    sqlite_session.commit()
    assert finalized.status == BillingPeriodStatus.FINALIZED
    assert finalized.finalized_at is not None

    locked = service.lock(
        period_type=BillingPeriodType.DAILY,
        start_at=start_at,
        end_at=end_at,
        tz="UTC",
        token=token,
    )
    sqlite_session.commit()
    assert locked.status == BillingPeriodStatus.LOCKED
    assert locked.locked_at is not None

    with pytest.raises(BillingPeriodConflict):
        service.finalize(
            period_type=BillingPeriodType.DAILY,
            start_at=start_at,
            end_at=end_at,
            tz="UTC",
            token=token,
        )
