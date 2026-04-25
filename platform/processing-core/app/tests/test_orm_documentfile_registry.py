from sqlalchemy.orm import configure_mappers


from app.db.types import ExistingEnum, GUID


def test_documentfile_mappers_configure_without_registry_conflict() -> None:
    import app.domains.documents.models  # noqa: F401
    import app.models.documents  # noqa: F401

    configure_mappers()


def test_shared_documents_table_keeps_enum_columns_after_overlap_imports() -> None:
    import app.domains.documents.models  # noqa: F401
    import app.models.documents as registry_models

    assert isinstance(registry_models.Document.__table__.c.direction.type, ExistingEnum)
    assert isinstance(registry_models.Document.__table__.c.status.type, ExistingEnum)


def test_shared_documents_table_keeps_uuid_actor_columns_after_overlap_imports() -> None:
    import app.domains.documents.models  # noqa: F401
    import app.models.documents as registry_models

    assert isinstance(registry_models.Document.__table__.c.signed_by_client_user_id.type, GUID)
