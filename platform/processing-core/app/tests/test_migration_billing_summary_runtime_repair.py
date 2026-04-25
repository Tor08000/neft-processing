import importlib
from types import SimpleNamespace


migration = importlib.import_module(
    "app.alembic.versions.20300280_0221_billing_summary_audit_columns_runtime_repair"
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


def test_upgrade_restores_runtime_columns_idempotently(monkeypatch) -> None:
    dummy_op = DummyOp()
    monkeypatch.setattr(migration, "op", dummy_op)

    migration.upgrade()

    statements = "\n".join(dummy_op.connection.executed)
    assert "ADD COLUMN IF NOT EXISTS generated_at TIMESTAMPTZ NULL DEFAULT now()" in statements
    assert "ADD COLUMN IF NOT EXISTS hash VARCHAR(128) NULL" in statements
    assert "CREATE INDEX IF NOT EXISTS ix_billing_summary_generated_at" in statements
