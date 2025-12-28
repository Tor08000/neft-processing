from __future__ import annotations

from dataclasses import dataclass

from app.services.risk_v5.retraining.trainer import TrainingResult
from app.services.risk_v5.retraining.validator import ValidationResult


@dataclass(frozen=True)
class PublishResult:
    published: bool
    model_version: str | None


def publish_model(training: TrainingResult, validation: ValidationResult) -> PublishResult:
    """Register the model version in the registry as a candidate."""

    if not validation.passed:
        return PublishResult(published=False, model_version=None)
    return PublishResult(published=True, model_version=training.model_version)


__all__ = ["PublishResult", "publish_model"]
