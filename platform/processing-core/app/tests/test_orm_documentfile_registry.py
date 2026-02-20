from sqlalchemy.orm import configure_mappers


def test_documentfile_mappers_configure_without_registry_conflict() -> None:
    import app.domains.documents.models  # noqa: F401
    import app.models.documents  # noqa: F401

    configure_mappers()
