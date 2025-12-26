from __future__ import annotations

from app.celery_client import celery_client
from app.db import get_sessionmaker
from app.services.legal_integrations.service import LegalIntegrationsService


@celery_client.task(name="legal.poll_provider")
def poll_legal_provider(provider: str, *, use_edo: bool = False) -> list[str]:
    session_factory = get_sessionmaker()
    with session_factory() as db:
        service = LegalIntegrationsService(db)
        envelopes = service.poll_provider(provider=provider, use_edo=use_edo)
        return [envelope.envelope_id for envelope in envelopes]


__all__ = ["poll_legal_provider"]
