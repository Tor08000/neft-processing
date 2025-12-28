from app.services.legal_integrations.providers.docusign import DocuSignAdapter
from app.services.legal_integrations.providers.kontur_sign import KonturSignAdapter
from app.services.legal_integrations.providers.noop import NoopLegalAdapter

__all__ = ["DocuSignAdapter", "KonturSignAdapter", "NoopLegalAdapter"]
