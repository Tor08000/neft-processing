import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.event_outbox import EventOutbox
from app.services.event_outbox import publish_event

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _reset_db():
    table = Base.metadata.tables["event_outbox"]
    table.drop(bind=engine, checkfirst=True)
    table.create(bind=engine, checkfirst=True)
    yield
    table.drop(bind=engine, checkfirst=True)


def test_outbox_idempotency_key_is_exactly_once_guard():
    db = SessionLocal()
    try:
        publish_event(
            db,
            aggregate_type="refund",
            aggregate_id="r-1",
            event_type="refund.created",
            payload={"amount": 100},
            idempotency_key="outbox:refund:r-1",
        )
        db.commit()

        publish_event(
            db,
            aggregate_type="refund",
            aggregate_id="r-1",
            event_type="refund.created",
            payload={"amount": 100},
            idempotency_key="outbox:refund:r-1",
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        assert db.query(EventOutbox).count() == 1
    finally:
        db.close()
