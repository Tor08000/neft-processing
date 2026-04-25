from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "EnvelopeRef",
    "EnvelopeStatus",
    "ExternalLegalAdapter",
    "SignedArtifact",
    "SigningPayload",
    "registry",
]


def __getattr__(name: str) -> Any:
    if name == "registry":
        return import_module("app.services.legal_integrations.registry").registry
    if name in {"EnvelopeRef", "EnvelopeStatus", "ExternalLegalAdapter", "SignedArtifact", "SigningPayload"}:
        return getattr(import_module("app.services.legal_integrations.base"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
