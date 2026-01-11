from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.models.edo import EdoDocumentStatus


class TransitionError(RuntimeError):
    pass


@dataclass(frozen=True)
class EdoTransitionRule:
    from_status: EdoDocumentStatus | None
    to_status: EdoDocumentStatus


class EdoStateMachine:
    _allowed = {
        EdoDocumentStatus.DRAFT: {
            EdoDocumentStatus.QUEUED,
        },
        EdoDocumentStatus.QUEUED: {
            EdoDocumentStatus.SENDING,
        },
        EdoDocumentStatus.SENDING: {
            EdoDocumentStatus.SENT,
            EdoDocumentStatus.FAILED,
        },
        EdoDocumentStatus.SENT: {
            EdoDocumentStatus.DELIVERED,
            EdoDocumentStatus.REJECTED,
            EdoDocumentStatus.REVOKED,
            EdoDocumentStatus.FAILED,
        },
        EdoDocumentStatus.DELIVERED: {
            EdoDocumentStatus.SIGNED,
            EdoDocumentStatus.REJECTED,
            EdoDocumentStatus.REVOKED,
            EdoDocumentStatus.FAILED,
        },
        EdoDocumentStatus.FAILED: {
            EdoDocumentStatus.QUEUED,
        },
    }

    @classmethod
    def can_transition(cls, from_status: EdoDocumentStatus, to_status: EdoDocumentStatus) -> bool:
        allowed = cls._allowed.get(from_status, set())
        return to_status in allowed

    @classmethod
    def assert_transition(cls, from_status: EdoDocumentStatus, to_status: EdoDocumentStatus) -> None:
        if not cls.can_transition(from_status, to_status):
            raise TransitionError(f"invalid_transition:{from_status.value}->{to_status.value}")


__all__ = ["EdoStateMachine", "EdoTransitionRule", "TransitionError"]
