import sys
import traceback

from app.api.dependencies.schema_guard import REQUIRED_CORE_TABLES
from app.diagnostics.db_state import collect_inventory


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

    missing_tables = inventory.missing_tables(REQUIRED_CORE_TABLES)
    print(f"[entrypoint] missing_required_tables={missing_tables}", flush=True)

    if missing_version or missing_tables:
        return 2

    print("[entrypoint] core tables present after migrations", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
