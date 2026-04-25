import importlib
from types import SimpleNamespace


migration = importlib.import_module(
    "app.alembic.versions.20300300_0223_card_access_runtime_repair"
)


class DummyConnection:
    def __init__(self) -> None:
        self.dialect = SimpleNamespace(name="postgresql")
        self.executed: list[str] = []

    def exec_driver_sql(self, statement: str) -> None:
        self.executed.append(str(statement))


class DummyOp:
    def __init__(self) -> None:
        self.connection = DummyConnection()

    def get_bind(self) -> DummyConnection:
        return self.connection


def test_upgrade_restores_card_access_runtime_table(monkeypatch) -> None:
    dummy_op = DummyOp()
    monkeypatch.setattr(migration, "op", dummy_op)

    migration.upgrade()

    statements = "\n".join(dummy_op.connection.executed)
    assert "CREATE TYPE" in statements
    assert "card_access_scope" in statements
    assert "CREATE TABLE IF NOT EXISTS" in statements
    assert "card_access" in statements
    assert "client_id UUID NOT NULL REFERENCES" in statements
    assert "CONSTRAINT uq_card_access_user_card UNIQUE (card_id, user_id)" in statements
    assert "CREATE INDEX IF NOT EXISTS ix_card_access_client_id" in statements
    assert "CREATE INDEX IF NOT EXISTS ix_card_access_user_id" in statements
    assert "CREATE INDEX IF NOT EXISTS ix_card_access_card_id" in statements
