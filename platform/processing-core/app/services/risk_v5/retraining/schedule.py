from __future__ import annotations

from dataclasses import dataclass

from app.services.risk_v5.retraining.dataset import build_dataset
from app.services.risk_v5.retraining.publisher import PublishResult, publish_model
from app.services.risk_v5.retraining.trainer import train_model
from app.services.risk_v5.retraining.validator import validate_model


@dataclass(frozen=True)
class RetrainingRunResult:
    publish: PublishResult


def run_retraining(*, shadow_rows: list[dict], schema_version: str) -> RetrainingRunResult:
    dataset = build_dataset(shadow_rows=shadow_rows, schema_version=schema_version)
    training = train_model(dataset)
    validation = validate_model(training)
    publish = publish_model(training, validation)
    return RetrainingRunResult(publish=publish)


__all__ = ["RetrainingRunResult", "run_retraining"]
