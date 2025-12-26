class LegalIntegrationError(RuntimeError):
    pass


class ProviderNotConfigured(LegalIntegrationError):
    pass


class EnvelopeNotFound(LegalIntegrationError):
    pass


class SignatureVerificationError(LegalIntegrationError):
    pass


__all__ = [
    "EnvelopeNotFound",
    "LegalIntegrationError",
    "ProviderNotConfigured",
    "SignatureVerificationError",
]
