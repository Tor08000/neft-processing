from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
except ModuleNotFoundError:  # pragma: no cover - exercised in shared test env
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    logger.warning(
        "prometheus_client is unavailable; crm-service metrics are running in degraded local mode"
    )

    _REGISTRY: list["_BaseMetric"] = []

    class _MetricHandle:
        def __init__(self, metric: "_BaseMetric", label_values: tuple[str, ...]) -> None:
            self._metric = metric
            self._label_values = label_values

        def inc(self, amount: float = 1.0) -> None:
            self._metric.inc(amount, self._label_values)

        def set(self, value: float) -> None:
            self._metric.set(value, self._label_values)

    class _BaseMetric:
        metric_type = "gauge"

        def __init__(self, name: str, documentation: str, labelnames: list[str] | tuple[str, ...] | None = None) -> None:
            self.name = name
            self.documentation = documentation
            self.labelnames = tuple(labelnames or ())
            self._samples: dict[tuple[str, ...], float] = {}
            _REGISTRY.append(self)

        def labels(self, *args: Any, **kwargs: Any) -> _MetricHandle:
            if kwargs:
                values = tuple(str(kwargs.get(label, "")) for label in self.labelnames)
            else:
                values = tuple(str(value) for value in args)
            return _MetricHandle(self, values)

        def inc(self, amount: float = 1.0, label_values: tuple[str, ...] = ()) -> None:
            self._samples[label_values] = self._samples.get(label_values, 0.0) + float(amount)

        def set(self, value: float, label_values: tuple[str, ...] = ()) -> None:
            self._samples[label_values] = float(value)

        def export(self) -> list[str]:
            lines = [
                f"# HELP {self.name} {self.documentation}",
                f"# TYPE {self.name} {self.metric_type}",
            ]
            if not self._samples:
                lines.append(f"{self.name} 0.0")
                return lines
            for labels, value in self._samples.items():
                if self.labelnames:
                    rendered_labels = ",".join(
                        f'{label}="{label_value}"'
                        for label, label_value in zip(self.labelnames, labels)
                    )
                    lines.append(f"{self.name}{{{rendered_labels}}} {value}")
                else:
                    lines.append(f"{self.name} {value}")
            return lines

    class Counter(_BaseMetric):
        metric_type = "counter"

    class Gauge(_BaseMetric):
        metric_type = "gauge"

    def generate_latest() -> bytes:
        payload = "\n".join(
            line
            for metric in _REGISTRY
            for line in metric.export()
        )
        return f"{payload}\n".encode("utf-8")


__all__ = [
    "CONTENT_TYPE_LATEST",
    "Counter",
    "Gauge",
    "generate_latest",
]
