from __future__ import annotations

from typing import Iterable, Sequence

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.risk_rule import RiskRule, RiskRuleAction, RiskRuleScope, RiskRuleVersion
from app.services.risk_rules import RuleConfig, RuleDefinition, RuleScope


class RiskRulesRepository:
    """Repository for persisting and loading risk rules with DSL conversion."""

    def __init__(self, db: Session):
        self.db = db

    def _to_definition(self, rule: RiskRule) -> RuleDefinition:
        config = RuleConfig.model_validate(rule.dsl_payload)
        return config.to_definition()

    def _prepare_payload(self, config: RuleConfig) -> dict:
        return config.model_dump(mode="json")

    def create_rule(self, config: RuleConfig, description: str | None = None) -> RiskRule:
        payload = self._prepare_payload(config)
        rule = RiskRule(
            name=config.name,
            description=description,
            scope=RiskRuleScope(config.scope.value),
            subject_ref=config.subject_id,
            action=RiskRuleAction(config.action.value),
            enabled=config.enabled,
            priority=config.priority,
            dsl_payload=payload,
        )
        self.db.add(rule)
        self.db.flush()
        self._store_version(rule, payload, version=1)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def update_rule(self, rule_id: int, config: RuleConfig, description: str | None = None) -> RiskRule:
        rule = self.db.query(RiskRule).filter(RiskRule.id == rule_id).one()
        payload = self._prepare_payload(config)
        rule.name = config.name
        rule.description = description
        rule.scope = RiskRuleScope(config.scope.value)
        rule.subject_ref = config.subject_id
        rule.action = RiskRuleAction(config.action.value)
        rule.enabled = config.enabled
        rule.priority = config.priority
        rule.dsl_payload = payload

        next_version = 1 + len(rule.versions)
        self._store_version(rule, payload, version=next_version)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def _store_version(self, rule: RiskRule, payload: dict, version: int) -> RiskRuleVersion:
        version_obj = RiskRuleVersion(rule=rule, version=version, dsl_payload=payload)
        self.db.add(version_obj)
        return version_obj

    def disable_rules(self, rule_ids: Sequence[int]) -> int:
        if not rule_ids:
            return 0
        updated = (
            self.db.query(RiskRule)
            .filter(RiskRule.id.in_(rule_ids))
            .update({RiskRule.enabled: False}, synchronize_session="fetch")
        )
        self.db.commit()
        return updated

    def clone_rule(self, rule_id: int, *, new_name: str) -> RiskRule:
        source = self.db.query(RiskRule).filter(RiskRule.id == rule_id).one()
        payload = dict(source.dsl_payload)
        payload["name"] = new_name
        config = RuleConfig.model_validate(payload)
        return self.create_rule(config, description=source.description)

    def get_active_rules_by_scope(
        self, scope: RuleScope, subject_ref: str | None = None
    ) -> list[RuleDefinition]:
        query = self.db.query(RiskRule).filter(RiskRule.enabled.is_(True))
        query = query.filter(RiskRule.scope == RiskRuleScope(scope.value))
        if scope != RuleScope.GLOBAL:
            query = query.filter(RiskRule.subject_ref == subject_ref)
        rules = query.order_by(RiskRule.priority.asc(), RiskRule.id.asc()).all()
        return [self._to_definition(rule) for rule in rules]

    def get_applicable_rules(
        self, scope: RuleScope, subject_ref: str | None = None
    ) -> list[RuleDefinition]:
        query = self.db.query(RiskRule).filter(RiskRule.enabled.is_(True))
        query = query.filter(
            or_(
                RiskRule.scope == RiskRuleScope.GLOBAL,
                and_(
                    RiskRule.scope == RiskRuleScope(scope.value),
                    RiskRule.subject_ref == subject_ref,
                ),
            )
        )
        rules = query.order_by(RiskRule.priority.asc(), RiskRule.id.asc()).all()
        return [self._to_definition(rule) for rule in rules]

    def list_raw_rules(self) -> list[RiskRule]:
        return (
            self.db.query(RiskRule)
            .order_by(RiskRule.priority.asc(), RiskRule.id.asc())
            .all()
        )

    def save_many(self, configs: Iterable[RuleConfig]) -> list[RiskRule]:
        saved: list[RiskRule] = []
        for config in configs:
            saved.append(self.create_rule(config))
        return saved
