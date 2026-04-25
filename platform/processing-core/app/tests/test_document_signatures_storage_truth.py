from app.domains.documents.models import DocumentSignature as ClientDocumentSignature
from app.models.legal_integrations import DocumentSignature as LegalDocumentSignature


def test_document_signatures_shared_storage_truth() -> None:
    client_table = ClientDocumentSignature.__table__
    legal_table = LegalDocumentSignature.__table__

    assert client_table is legal_table
    assert client_table.name == "document_signatures"

    columns = set(client_table.c.keys())
    assert {"document_id", "client_id", "signer_user_id", "signature_method", "consent_text_version"} <= columns
    assert {"provider", "version", "status", "signature_type", "signature_hash_sha256", "verified"} <= columns
