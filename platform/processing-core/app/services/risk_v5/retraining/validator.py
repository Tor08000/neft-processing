from __future__ import annotations

from dataclasses import dataclass

from app.services.risk_v5.retraining.trainer import TrainingResult


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    reasons: list[str]


def validate_model(training: TrainingResult) -> ValidationResult:
    """Apply quality gates to a trained model."""

    reasons: list[str] = []
    if training.metrics.get("auc", 0) < 0.7:
        reasons.append("auc_below_threshold")
    if training.metrics.get("precision", 0) < 0.5:
        reasons.append("precision_below_threshold")
    return ValidationResult(passed=not reasons, reasons=reasons)


__all__ = ["ValidationResult", "validate_model"]
