from __future__ import annotations

from dataclasses import dataclass

from app.models.integrations import IntegrationType


@dataclass(frozen=True)
class IntegrationConnector:
    integration_type: IntegrationType
    name: str
    enabled: bool


ACTIVE_CONNECTORS = (
    IntegrationConnector(integration_type=IntegrationType.ONEC, name="1C", enabled=True),
    IntegrationConnector(integration_type=IntegrationType.BANK, name="Bank", enabled=True),
)


def list_connectors() -> list[IntegrationConnector]:
    return list(ACTIVE_CONNECTORS)


__all__ = ["IntegrationConnector", "list_connectors"]
