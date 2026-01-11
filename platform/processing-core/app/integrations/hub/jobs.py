from __future__ import annotations

from dataclasses import dataclass

from app.models.integrations import IntegrationType


@dataclass(frozen=True)
class IntegrationJob:
    integration_type: IntegrationType
    name: str
    schedule: str


JOBS = (
    IntegrationJob(integration_type=IntegrationType.ONEC, name="onec-daily", schedule="0 3 * * *"),
    IntegrationJob(integration_type=IntegrationType.ONEC, name="onec-monthly", schedule="0 4 1 * *"),
)


def list_jobs() -> list[IntegrationJob]:
    return list(JOBS)


__all__ = ["IntegrationJob", "list_jobs"]
