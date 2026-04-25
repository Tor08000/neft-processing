import importlib
from types import SimpleNamespace


migration = importlib.import_module(
    "app.alembic.versions.20300290_0222_subscription_plan_demo_seed_runtime_repair"
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


def test_upgrade_repairs_only_zero_priced_control_individual(monkeypatch) -> None:
    dummy_op = DummyOp()
    monkeypatch.setattr(migration, "op", dummy_op)

    migration.upgrade()

    statement = "\n".join(dummy_op.connection.executed)
    assert "WHERE code = 'CONTROL_INDIVIDUAL_1M'" in statement
    assert "COALESCE(price_cents, 0) = 0" in statement
    assert "price_cents = 9900" in statement
