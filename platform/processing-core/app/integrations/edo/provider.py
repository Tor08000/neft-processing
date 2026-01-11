from __future__ import annotations

from abc import ABC, abstractmethod

from app.integrations.edo.dtos import (
    EdoInboundRequest,
    EdoReceiveResult,
    EdoRevokeRequest,
    EdoRevokeResult,
    EdoSendRequest,
    EdoSendResult,
    EdoStatusRequest,
    EdoStatusResult,
)


class EdoProvider(ABC):
    @abstractmethod
    def send(self, request: EdoSendRequest) -> EdoSendResult:
        raise NotImplementedError

    @abstractmethod
    def get_status(self, request: EdoStatusRequest) -> EdoStatusResult:
        raise NotImplementedError

    @abstractmethod
    def receive(self, event: EdoInboundRequest) -> EdoReceiveResult:
        raise NotImplementedError

    @abstractmethod
    def revoke(self, request: EdoRevokeRequest) -> EdoRevokeResult:
        raise NotImplementedError


__all__ = ["EdoProvider"]
