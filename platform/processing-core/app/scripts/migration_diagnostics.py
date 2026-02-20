import sys
import traceback

from sqlalchemy import text

from app.api.dependencies.schema_guard import REQUIRED_CORE_TABLES
from app.db import DATABASE_URL, make_engine
from app.diagnostics.db_state import collect_inventory


def _read_parallel_versions(parallel_tables: list[tuple[str, str]]) -> dict[str, list[str]]:
    if not parallel_tables:
        return {}

    versions_by_table: dict[str, list[str]] = {}
    engine = make_engine(DATABASE_URL)
    try:
        with engine.connect() as connection:
            for table_schema, table_name in parallel_tables:
                quoted_schema = table_schema.replace('"', '""')
                quoted_table = table_name.replace('"', '""')
                key = f"{table_schema}.{table_name}"
                rows = connection.execute(
                    text(
                        f'SELECT version_num FROM "{quoted_schema}"."{quoted_table}" '
                        'ORDER BY version_num'
                    )
                ).scalars().all()
                versions_by_table[key] = [str(version) for version in rows]
    finally:
        engine.dispose()

    return versions_by_table


def main() -> int:
    try:
        inventory = collect_inventory()
    except Exception as exc:  # noqa: BLE001 - startup diagnostics
        traceback.print_exc()
        print(f"[entrypoint] diagnostics failed: {exc}", flush=True)
        return 1

    print(
        "[entrypoint] post-migration target: "
        f"db={inventory.current_database} user={inventory.current_user} "
        f"server={inventory.server_addr}:{inventory.server_port} search_path={inventory.search_path}",
        flush=True,
    )
    print(f"[entrypoint] post-migration schemas: {inventory.schemas}", flush=True)
    print(
        f"[entrypoint] post-migration tables sample: {[f'{s}.{t}' for s, t in inventory.tables[:30]]}",
        flush=True,
    )

    missing_version = not inventory.alembic_versions
    if inventory.alembic_versions:
        print(f"[entrypoint] alembic_version_core present: {inventory.alembic_versions}", flush=True)
    else:
        print("[entrypoint] alembic_version_core missing", flush=True)

    if missing_version and inventory.parallel_alembic_version_tables:
        versions_by_table = _read_parallel_versions(inventory.parallel_alembic_version_tables)
        for table_schema, table_name in inventory.parallel_alembic_version_tables:
            key = f"{table_schema}.{table_name}"
            versions = versions_by_table.get(key, [])
            print(
                f"[entrypoint] parallel version table detected: {table_schema}.{table_name}; "
                f"contents={versions}",
                flush=True,
            )

    missing_tables = inventory.missing_tables(REQUIRED_CORE_TABLES)
    print(f"[entrypoint] missing_required_tables={missing_tables}", flush=True)

    if missing_version or missing_tables:
        return 2

    print("[entrypoint] core tables present after migrations", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
