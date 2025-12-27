from __future__ import annotations

from dataclasses import dataclass

from app.models.audit_log import AuditVisibility
from app.services.audit_service import AuditService, RequestContext


class LegalGraphError(RuntimeError):
    """Base class for legal graph failures."""


@dataclass(frozen=True)
class LegalGraphWriteFailure:
    entity_type: str
    entity_id: str | None
    error: str


def audit_graph_write_failure(
    db,
    *,
    failure: LegalGraphWriteFailure,
    request_ctx: RequestContext | None,
) -> None:
    AuditService(db).audit(
        event_type="LEGAL_GRAPH_WRITE_FAILED",
        entity_type=failure.entity_type,
        entity_id=failure.entity_id or "",
        action="WRITE_FAILED",
        visibility=AuditVisibility.INTERNAL,
        after={"error": failure.error},
        request_ctx=request_ctx,
    )


__all__ = ["LegalGraphError", "LegalGraphWriteFailure", "audit_graph_write_failure"]
