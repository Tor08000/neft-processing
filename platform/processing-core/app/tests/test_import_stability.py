from __future__ import annotations

import sys

from app.db import Base
from app.models import legal_document
from app.models import legal_gate


def test_legal_document_table_singleton() -> None:
    assert legal_document.LegalDocument.__table__ is Base.metadata.tables["legal_documents"]
    assert legal_gate.LegalDocument.__table__ is Base.metadata.tables["legal_documents"]
    assert [name for name in Base.metadata.tables if name == "legal_documents"] == [
        "legal_documents"
    ]


def test_no_alternate_processing_core_imports() -> None:
    alt_prefixes = ("processing_core.", "platform.processing_core.")
    offenders = [name for name in sys.modules if name.startswith(alt_prefixes)]
    assert not offenders, f"unexpected processing_core imports: {offenders}"
