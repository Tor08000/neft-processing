from sqlalchemy import String

from app.models.client_actions import DocumentAcknowledgement


def test_document_acknowledgement_model_matches_varchar_storage_truth():
    assert isinstance(DocumentAcknowledgement.__table__.c.id.type, String)
    assert isinstance(DocumentAcknowledgement.__table__.c.document_id.type, String)
