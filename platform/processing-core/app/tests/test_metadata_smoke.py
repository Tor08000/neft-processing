from app.db import Base
from app.integrations.fuel.providers import virtual_network  # noqa: F401
import app.models  # noqa: F401


def test_metadata_table_names_unique() -> None:
    assert len(Base.metadata.tables) == len(set(Base.metadata.tables))
