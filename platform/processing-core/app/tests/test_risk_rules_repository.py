from datetime import timedelta

import pytest
from sqlalchemy import inspect

from app.db import Base, SessionLocal, engine
from app.repositories.risk_rules_repository import RiskRulesRepository
from app.services.risk_rules import (
    MetricType,
    RuleAction,
    RuleConfig,
    RuleScope,
    SelectorConfig,
    WindowConfig,
)


@pytest.fixture(autouse=True)
def _prepare_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def repo():
    session = SessionLocal()
    repository = RiskRulesRepository(session)
    try:
        yield repository
    finally:
        session.close()


def _make_basic_rule(name: str, scope: RuleScope, subject: str | None = None) -> RuleConfig:
    return RuleConfig(
        name=name,
        scope=scope,
        subject_id=subject,
        selector=SelectorConfig(),
        metric=MetricType.ALWAYS,
        value=1,
        action=RuleAction.MEDIUM,
        priority=10,
        enabled=True,
    )


def test_migration_tables_created():
    inspector = inspect(engine)
    assert "risk_rules" in inspector.get_table_names()
    assert "risk_rule_versions" in inspector.get_table_names()

    indexes = inspector.get_indexes("risk_rules")
    index_names = {idx["name"] for idx in indexes}
    assert {"ix_risk_rules_scope", "ix_risk_rules_subject_ref", "ix_risk_rules_enabled"}.issubset(
        index_names
    )

    version_constraints = inspector.get_unique_constraints("risk_rule_versions")
    assert any(constraint["name"] == "uq_risk_rule_version" for constraint in version_constraints)


def test_create_and_load_rules(repo: RiskRulesRepository):
    repo.create_rule(_make_basic_rule("global", RuleScope.GLOBAL))

    definitions = repo.get_active_rules_by_scope(RuleScope.GLOBAL)
    assert len(definitions) == 1
    assert definitions[0].name == "global"
    assert definitions[0].scope == RuleScope.GLOBAL


def test_applicable_rules_merge_global_and_scoped(repo: RiskRulesRepository):
    repo.create_rule(_make_basic_rule("global", RuleScope.GLOBAL))
    repo.create_rule(_make_basic_rule("client_rule", RuleScope.CLIENT, subject="client-1"))

    combined = repo.get_applicable_rules(RuleScope.CLIENT, subject_ref="client-1")
    assert {rule.name for rule in combined} == {"global", "client_rule"}

    other_client = repo.get_applicable_rules(RuleScope.CLIENT, subject_ref="client-2")
    assert [rule.name for rule in other_client] == ["global"]


def test_disable_rules(repo: RiskRulesRepository):
    global_rule = repo.create_rule(_make_basic_rule("global", RuleScope.GLOBAL))
    client_rule = repo.create_rule(_make_basic_rule("client_rule", RuleScope.CLIENT, subject="client-1"))

    updated = repo.disable_rules([client_rule.id])
    assert updated == 1

    rules = repo.get_applicable_rules(RuleScope.CLIENT, subject_ref="client-1")
    assert [rule.name for rule in rules] == ["global"]
    assert all(rule.name != "client_rule" for rule in rules)

    repo.disable_rules([global_rule.id])
    assert repo.get_applicable_rules(RuleScope.CLIENT, subject_ref="client-1") == []


def test_clone_and_versions(repo: RiskRulesRepository):
    base_rule = repo.create_rule(_make_basic_rule("global", RuleScope.GLOBAL))
    cloned = repo.clone_rule(base_rule.id, new_name="global_clone")

    assert cloned.name == "global_clone"
    assert len(base_rule.versions) == 1
    assert len(cloned.versions) == 1

    updated = repo.update_rule(
        base_rule.id,
        RuleConfig(
            name="global_updated",
            scope=RuleScope.GLOBAL,
            subject_id=None,
            selector=SelectorConfig(),
            window=WindowConfig(hours=2),
            metric=MetricType.COUNT,
            value=5,
            action=RuleAction.HIGH,
            priority=5,
            enabled=True,
        ),
    )

    assert updated.name == "global_updated"
    assert len(updated.versions) == 2
    definition = repo.get_active_rules_by_scope(RuleScope.GLOBAL)[0]
    assert definition.window
    assert definition.window.duration == timedelta(hours=2)


def test_save_many(repo: RiskRulesRepository):
    configs = [
        _make_basic_rule("r1", RuleScope.GLOBAL),
        _make_basic_rule("r2", RuleScope.CLIENT, subject="client-42"),
    ]
    saved = repo.save_many(configs)
    assert len(saved) == 2
    assert {rule.name for rule in repo.get_applicable_rules(RuleScope.CLIENT, "client-42")} == {
        "r1",
        "r2",
    }
