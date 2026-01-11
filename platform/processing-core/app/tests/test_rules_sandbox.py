from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.api.routes.rules import router as rules_router
from app.db import Base, get_db
from app.models.operation import Operation, OperationStatus, OperationType
from app.models.unified_rule import (
    RuleSetActive,
    RuleSetStatus,
    RuleSetVersion,
    UnifiedRule,
    UnifiedRuleMetric,
    UnifiedRulePolicy,
    UnifiedRuleScope,
)


@pytest.fixture()
def sandbox_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(rules_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, TestingSessionLocal

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _seed_rule_set(db: Session, *, scope: UnifiedRuleScope) -> RuleSetVersion:
    version = RuleSetVersion(name="sandbox-v1", scope=scope, status=RuleSetStatus.ACTIVE)
    db.add(version)
    db.flush()
    db.add(RuleSetActive(scope=scope, version_id=version.id))
    db.commit()
    db.refresh(version)
    return version


def test_synthetic_sandbox_returns_decision(sandbox_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = sandbox_client
    with SessionLocal() as db:
        version = _seed_rule_set(db, scope=UnifiedRuleScope.FLEET)
        rule = UnifiedRule(
            code="FLEET_DAILY_SPEND_LIMIT",
            version_id=version.id,
            scope=UnifiedRuleScope.FLEET,
            metric=UnifiedRuleMetric.AMOUNT,
            window={"type": "rolling", "unit": "day", "size": 1},
            value={"op": "<=", "threshold": 100},
            policy=UnifiedRulePolicy.HARD_DECLINE,
            priority=100,
            reason_code="LIMIT_DAILY_SPEND_EXCEEDED",
            explain_template="Daily spend {current} > {threshold}",
        )
        db.add(rule)
        db.commit()

    response = client.post(
        "/rules/sandbox:evaluate",
        json={
            "mode": "synthetic",
            "at": "2026-01-11T12:00:00Z",
            "scope": "FLEET",
            "context": {"client_id": "c1", "card_id": "card1", "amount": 150},
            "synthetic_metrics": {"AMOUNT": 0},
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["decision"] == "HARD_DECLINE"
    assert payload["matched_rules"]


def test_conflict_resolution_is_deterministic(sandbox_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = sandbox_client
    with SessionLocal() as db:
        version = _seed_rule_set(db, scope=UnifiedRuleScope.API)
        db.add(
            UnifiedRule(
                code="API_RATE_SOFT",
                version_id=version.id,
                scope=UnifiedRuleScope.API,
                metric=UnifiedRuleMetric.COUNT,
                window={"type": "rolling", "unit": "minute", "size": 1},
                value={"op": ">=", "threshold": 1},
                policy=UnifiedRulePolicy.SOFT_DECLINE,
                priority=10,
            )
        )
        db.add(
            UnifiedRule(
                code="API_RATE_SOFT_STRICT",
                version_id=version.id,
                scope=UnifiedRuleScope.API,
                metric=UnifiedRuleMetric.COUNT,
                window={"type": "rolling", "unit": "minute", "size": 1},
                value={"op": ">=", "threshold": 1},
                policy=UnifiedRulePolicy.SOFT_DECLINE,
                priority=50,
            )
        )
        db.commit()

    response = client.post(
        "/rules/sandbox:evaluate",
        json={
            "mode": "synthetic",
            "at": "2026-01-11T12:00:00Z",
            "scope": "API",
            "context": {"endpoint": "/v1/test"},
            "synthetic_metrics": {"COUNT": 1},
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["decision"] == "SOFT_DECLINE"
    assert payload["matched_rules"][0]["code"] == "API_RATE_SOFT_STRICT"


def test_historical_sandbox_loads_transaction(sandbox_client: tuple[TestClient, sessionmaker]) -> None:
    client, SessionLocal = sandbox_client
    with SessionLocal() as db:
        version = _seed_rule_set(db, scope=UnifiedRuleScope.FLEET)
        db.add(
            UnifiedRule(
                code="FLEET_SINGLE_LIMIT",
                version_id=version.id,
                scope=UnifiedRuleScope.FLEET,
                metric=UnifiedRuleMetric.AMOUNT,
                window={"type": "rolling", "unit": "day", "size": 1},
                value={"op": "<=", "threshold": 50},
                policy=UnifiedRulePolicy.HARD_DECLINE,
                priority=100,
            )
        )
        db.add(
            Operation(
                operation_id="tx_123",
                created_at=datetime.now(timezone.utc),
                operation_type=OperationType.AUTH,
                status=OperationStatus.AUTHORIZED,
                merchant_id="m1",
                terminal_id="t1",
                client_id="client-1",
                card_id="card-1",
                amount=120,
                currency="RUB",
                response_code="00",
                response_message="OK",
            )
        )
        db.commit()

    response = client.post(
        "/rules/sandbox:evaluate",
        json={"mode": "historical", "scope": "FLEET", "transaction_id": "tx_123"},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["decision"] == "HARD_DECLINE"
