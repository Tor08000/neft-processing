import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.unified_rule import (
    RuleSetActive,
    RuleSetStatus,
    RuleSetVersion,
    UnifiedRule,
    UnifiedRuleMetric,
    UnifiedRulePolicy,
    UnifiedRuleScope,
)
from app.schemas.unified_rules import RuleEvaluationContext, RuleEvaluationObject, RuleEvaluationSubject
from app.services.unified_rules_engine import SyntheticMetricsProvider, evaluate_rules, resolve_decision


@pytest.fixture()
def regression_db() -> sessionmaker:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )
    Base.metadata.create_all(bind=engine)
    yield SessionLocal
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_regression_ruleset_fixture(regression_db: sessionmaker) -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "rulesets" / "fleet_ruleset.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    with regression_db() as db:
        version_payload = payload["version"]
        version = RuleSetVersion(
            name=version_payload["name"],
            scope=UnifiedRuleScope(version_payload["scope"]),
            status=RuleSetStatus.ACTIVE,
        )
        db.add(version)
        db.flush()
        db.add(RuleSetActive(scope=version.scope, version_id=version.id))

        for rule_payload in payload["rules"]:
            db.add(
                UnifiedRule(
                    code=rule_payload["code"],
                    version_id=version.id,
                    scope=UnifiedRuleScope(rule_payload["scope"]),
                    metric=UnifiedRuleMetric(rule_payload["metric"]),
                    window=rule_payload.get("window"),
                    value=rule_payload.get("value"),
                    policy=UnifiedRulePolicy(rule_payload["policy"]),
                    priority=rule_payload.get("priority", 100),
                    reason_code=rule_payload.get("reason_code"),
                )
            )
        db.commit()

        rules = db.query(UnifiedRule).filter(UnifiedRule.version_id == version.id).all()
        for case in payload["cases"]:
            context = RuleEvaluationContext(
                timestamp=datetime.now(timezone.utc),
                scope=version.scope,
                subject=RuleEvaluationSubject(client_id=case["context"].get("client_id")),
                object=RuleEvaluationObject(
                    card_id=case["context"].get("card_id"),
                    amount=case["context"].get("amount"),
                    currency=case["context"].get("currency"),
                ),
            )
            provider = SyntheticMetricsProvider(case.get("synthetic_metrics", {}))
            matched = evaluate_rules(rules, context, provider)
            decision, _ = resolve_decision(matched)
            assert decision.value == case["expected_decision"]
