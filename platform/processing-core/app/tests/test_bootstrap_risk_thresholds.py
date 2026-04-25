from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.risk_threshold_set import RiskThresholdSet
from app.models.risk_types import RiskSubjectType, RiskThresholdAction, RiskThresholdScope
from app.services.bootstrap import ensure_default_risk_threshold_sets


def test_bootstrap_creates_document_finalize_threshold_set() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[RiskThresholdSet.__table__])
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    try:
        session = session_factory()
        try:
            ensure_default_risk_threshold_sets(session)
            session.commit()
            ensure_default_risk_threshold_sets(session)
            session.commit()

            document_threshold = (
                session.query(RiskThresholdSet)
                .filter(RiskThresholdSet.subject_type == RiskSubjectType.DOCUMENT)
                .filter(RiskThresholdSet.action == RiskThresholdAction.DOCUMENT_FINALIZE)
                .filter(RiskThresholdSet.scope == RiskThresholdScope.GLOBAL)
                .filter(RiskThresholdSet.active.is_(True))
                .one()
            )
            assert document_threshold.id == "global-document-finalize-v1"
            assert document_threshold.block_threshold == 90
            assert document_threshold.review_threshold == 70
            assert document_threshold.allow_threshold == 0
            assert session.query(RiskThresholdSet).count() == 5
        finally:
            session.close()
    finally:
        engine.dispose()
