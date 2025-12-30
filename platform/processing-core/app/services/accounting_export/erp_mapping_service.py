from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.erp_exports import ErpMapping, ErpMappingMatchKind, ErpMappingRule
from app.services.accounting_export.canonical import AccountingEntry, build_entry_id


class ErpMappingNotFound(RuntimeError):
    """Raised when ERP mapping configuration is missing."""


class ErpMappingService:
    def __init__(self, db: Session):
        self.db = db

    def load_mapping(self, mapping_id: str) -> ErpMapping:
        mapping = self.db.query(ErpMapping).filter(ErpMapping.id == mapping_id).one_or_none()
        if not mapping:
            raise ErpMappingNotFound("erp_mapping_not_found")
        return mapping

    def load_rules(self, mapping_id: str) -> list[ErpMappingRule]:
        return (
            self.db.query(ErpMappingRule)
            .filter(ErpMappingRule.mapping_id == mapping_id, ErpMappingRule.enabled.is_(True))
            .order_by(ErpMappingRule.priority.asc(), ErpMappingRule.id.asc())
            .all()
        )

    def resolve_rule(
        self, entry: AccountingEntry, rules: Iterable[ErpMappingRule]
    ) -> ErpMappingRule | None:
        for rule in rules:
            if self._rule_matches(entry, rule):
                return rule
        return None

    def apply_mapping(
        self, entries: Iterable[AccountingEntry], rules: Iterable[ErpMappingRule]
    ) -> list[AccountingEntry]:
        resolved: list[AccountingEntry] = []
        for entry in entries:
            rule = self.resolve_rule(entry, rules)
            if not rule:
                resolved.append(entry)
                continue
            mapping_payload = {
                "gl_account": rule.gl_account,
                "subaccount_1": rule.subaccount_1,
                "subaccount_2": rule.subaccount_2,
                "subaccount_3": rule.subaccount_3,
                "cost_item": rule.cost_item,
                "vat_code": rule.vat_code,
                "counterparty_ref_mode": rule.counterparty_ref_mode.value if rule.counterparty_ref_mode else None,
                "nomenclature_ref": rule.nomenclature_ref,
                "rule_id": str(rule.id),
                "match_kind": rule.match_kind.value,
                "match_value": rule.match_value,
            }
            meta = {**entry.meta, "erp_mapping": mapping_payload}
            updated = replace(entry, meta=meta)
            resolved.append(replace(updated, entry_id=build_entry_id(updated)))
        return resolved

    @staticmethod
    def _match_value(entry: AccountingEntry, key: str) -> str | None:
        raw = entry.meta.get(key)
        if raw is None:
            return None
        return str(raw)

    def _rule_matches(self, entry: AccountingEntry, rule: ErpMappingRule) -> bool:
        match_value = rule.match_value
        if rule.match_kind == ErpMappingMatchKind.DOC_TYPE:
            return entry.document_type == match_value
        if rule.match_kind == ErpMappingMatchKind.SERVICE_CODE:
            return self._match_value(entry, "service_code") == match_value
        if rule.match_kind == ErpMappingMatchKind.PRODUCT_TYPE:
            return self._match_value(entry, "product_type") == match_value
        if rule.match_kind == ErpMappingMatchKind.COMMISSION_KIND:
            return self._match_value(entry, "commission_kind") == match_value
        if rule.match_kind == ErpMappingMatchKind.TAX_RATE:
            return (entry.vat_rate or self._match_value(entry, "tax_rate")) == match_value
        if rule.match_kind == ErpMappingMatchKind.PARTNER:
            return (
                self._match_value(entry, "partner")
                or self._match_value(entry, "partner_id")
            ) == match_value
        if rule.match_kind == ErpMappingMatchKind.CUSTOM:
            if "=" in match_value:
                key, value = match_value.split("=", 1)
                return self._match_value(entry, key.strip()) == value.strip()
            if ":" in match_value:
                key, value = match_value.split(":", 1)
                return self._match_value(entry, key.strip()) == value.strip()
            return self._match_value(entry, "custom") == match_value
        return False


__all__ = ["ErpMappingNotFound", "ErpMappingService"]
