from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict

from .schemas.risk_score import ModelType


@dataclass
class ModelInfo:
    model_type: ModelType
    version: str
    trained_at: datetime
    metrics: dict
    simulated: bool = True
    provider_mode: str = "registry_only"


class ModelRegistry:
    def __init__(self) -> None:
        self._models: Dict[ModelType, ModelInfo] = {}
        self._counters: Dict[ModelType, int] = {}

    def train(self, model_type: ModelType, metrics: dict | None = None) -> ModelInfo:
        counter = self._counters.get(model_type, 0) + 1
        self._counters[model_type] = counter
        version = f"{model_type.value}-v{counter}"
        info = ModelInfo(
            model_type=model_type,
            version=version,
            trained_at=datetime.now(timezone.utc),
            metrics=metrics or {},
            simulated=True,
            provider_mode="registry_only",
        )
        self._models[model_type] = info
        return info

    def update(self, model_type: ModelType, metrics: dict | None = None) -> ModelInfo:
        return self.train(model_type, metrics=metrics)

    def get(self, model_type: ModelType) -> ModelInfo | None:
        return self._models.get(model_type)


model_registry = ModelRegistry()
