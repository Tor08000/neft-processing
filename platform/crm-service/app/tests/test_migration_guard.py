from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_migration_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20260216_01_crm_v1_core_tables.py"
    )
    spec = spec_from_file_location("crm_migration_20260216_01", module_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_skips_when_crm_core_tables_already_exist(monkeypatch) -> None:
    module = _load_migration_module()
    created_tables: list[str] = []
    created_indexes: list[str] = []
    executed_sql: list[str] = []

    class _Inspector:
        def has_table(self, _table_name: str) -> bool:
            return True

    monkeypatch.setattr(module.op, "get_bind", lambda: object())
    monkeypatch.setattr(module, "inspect", lambda _bind: _Inspector())
    monkeypatch.setattr(module.op, "create_table", lambda name, *args, **kwargs: created_tables.append(name))
    monkeypatch.setattr(module.op, "create_index", lambda name, *args, **kwargs: created_indexes.append(name))
    monkeypatch.setattr(module.op, "execute", lambda sql: executed_sql.append(str(sql)))

    module.upgrade()

    assert created_tables == []
    assert created_indexes == []
    assert executed_sql == []
