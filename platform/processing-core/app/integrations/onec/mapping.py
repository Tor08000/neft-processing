from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.integrations import IntegrationMapping, IntegrationType


@dataclass(frozen=True)
class MappingResult:
    values: dict[str, Any]
    missing_required: list[str]


class IntegrationMappingService:
    def __init__(self, db: Session, *, integration_type: IntegrationType) -> None:
        self.db = db
        self.integration_type = integration_type

    def load(self, entity_type: str, *, version: str) -> list[IntegrationMapping]:
        return (
            self.db.query(IntegrationMapping)
            .filter(IntegrationMapping.integration_type == self.integration_type)
            .filter(IntegrationMapping.entity_type == entity_type)
            .filter(IntegrationMapping.version == version)
            .order_by(IntegrationMapping.created_at.asc())
            .all()
        )

    def apply(self, entity_type: str, context: dict[str, Any], *, version: str) -> MappingResult:
        mappings = self.load(entity_type, version=version)
        values: dict[str, Any] = {}
        missing_required: list[str] = []
        for mapping in mappings:
            value = self._resolve_value(context, mapping.source_field)
            if value is None:
                if mapping.is_required:
                    missing_required.append(mapping.source_field)
                continue
            value = self._apply_transform(value, mapping.transform)
            values[mapping.target_field] = value
        return MappingResult(values=values, missing_required=missing_required)

    @staticmethod
    def _resolve_value(context: dict[str, Any], key: str) -> Any:
        current: Any = context
        for part in key.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None
        return current

    @staticmethod
    def _apply_transform(value: Any, transform: str | None) -> Any:
        if transform is None:
            return value
        if transform == "upper":
            return str(value).upper()
        if transform == "lower":
            return str(value).lower()
        if transform == "strip":
            return str(value).strip()
        if transform.startswith("const:"):
            return transform.split(":", 1)[1]
        return value


__all__ = ["IntegrationMappingService", "MappingResult"]
