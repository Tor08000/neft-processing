from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from neft_shared.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class IntakeMetrics:
    intake_requests: Counter = field(default_factory=Counter)
    partner_errors: int = 0
    posting_errors: int = 0
    responses: Counter = field(default_factory=Counter)
    normalization_latencies: list[float] = field(default_factory=list)
    request_latencies: list[float] = field(default_factory=list)

    def mark_request(self, name: str) -> None:
        self.intake_requests[name] += 1

    def mark_partner_error(self) -> None:
        self.partner_errors += 1

    def mark_posting_error(self) -> None:
        self.posting_errors += 1

    def mark_response(self, status: str) -> None:
        self.responses[status] += 1

    def observe_normalization(self, seconds: float) -> None:
        self.normalization_latencies.append(seconds * 1000)
        logger.debug("intake_normalization_ms", extra={"latency_ms": self.normalization_latencies[-1]})

    def observe_request_latency(self, partner_id: str, latency_ms: float) -> None:
        self.request_latencies.append(latency_ms)
        logger.debug(
            "integration_request_latency",
            extra={"partner_id": partner_id, "latency_ms": latency_ms},
        )


metrics = IntakeMetrics()
