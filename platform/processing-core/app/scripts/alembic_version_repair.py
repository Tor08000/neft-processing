from __future__ import annotations

import os

import sqlalchemy as sa
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_prod_env() -> bool:
    app_env = (os.getenv("APP_ENV") or "").strip().lower()
    return app_env in {"prod", "production"}


def _normalize_parent_revisions(down_revision: object) -> tuple[str, ...]:
    if down_revision is None:
        return ()
    if isinstance(down_revision, str):
        return (down_revision,)
    if isinstance(down_revision, (tuple, list, set)):
        return tuple(str(item) for item in down_revision if item)
    return (str(down_revision),)


def _is_ancestor(script: ScriptDirectory, ancestor_revision: str, head_revision: str) -> bool:
    stack = [head_revision]
    visited: set[str] = set()

    while stack:
        current = stack.pop()
        if current == ancestor_revision:
            return True
        if current in visited:
            continue
        visited.add(current)

        revision = script.get_revision(current)
        if revision is None:
            continue

        stack.extend(_normalize_parent_revisions(revision.down_revision))

    return False


def _find_base_revisions(script: ScriptDirectory) -> list[str]:
    revisions: list[str] = []
    seen: set[str] = set()
    for revision in script.walk_revisions(base="base", head="heads"):
        if revision.down_revision is None and revision.revision not in seen:
            revisions.append(revision.revision)
            seen.add(revision.revision)
    return revisions


def _replace_versions(connection: sa.Connection, schema: str, revisions: list[str]) -> None:
    quoted_schema = schema.replace('"', '""')
    connection.execute(sa.text(f'TRUNCATE TABLE "{quoted_schema}".alembic_version_core'))
    for revision in revisions:
        connection.execute(
            sa.text(
                f'INSERT INTO "{quoted_schema}".alembic_version_core(version_num) VALUES (:revision)'
            ),
            {"revision": revision},
        )


def _format_table_preview(schema_tables: list[str], *, limit: int = 20) -> str:
    preview = schema_tables[:limit]
    suffix = "" if len(schema_tables) <= limit else f" ... (+{len(schema_tables) - limit} more)"
    return f"total={len(schema_tables)} preview={preview}{suffix}"


def _read_schema_tables(connection: sa.Connection, schema: str) -> list[str]:
    rows = connection.execute(
        sa.text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        ),
        {"schema": schema},
    ).scalars()
    return [str(row) for row in rows]


def _read_clients_columns(connection: sa.Connection, schema: str) -> list[str]:
    rows = connection.execute(
        sa.text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = 'clients'
            ORDER BY ordinal_position
            """
        ),
        {"schema": schema},
    ).scalars()
    return [str(row) for row in rows]


def ensure_alembic_version_consistency() -> None:
    schema = (
        os.getenv("ALEMBIC_VERSION_TABLE_SCHEMA")
        or os.getenv("NEFT_DB_SCHEMA")
        or "processing_core"
    ).strip() or "processing_core"
    alembic_config_path = os.getenv("ALEMBIC_CONFIG", "/app/app/alembic.ini")
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    auto_repair_default = not _is_prod_env()
    auto_repair = _env_flag("ALEMBIC_AUTO_REPAIR", auto_repair_default)
    strict_mode = _is_prod_env() and not _env_flag("ALEMBIC_REPAIR_ALLOW_RISKY_FALLBACK", False)

    config = Config(alembic_config_path)
    config.set_main_option("sqlalchemy.url", database_url)
    script = ScriptDirectory.from_config(config)

    heads = sorted(script.get_heads())
    bases = sorted(_find_base_revisions(script))

    print(f"[entrypoint] alembic script heads: {heads}", flush=True)
    print(f"[entrypoint] alembic script base revisions: {bases}", flush=True)
    print(
        "[entrypoint] alembic auto-repair "
        f"{'enabled' if auto_repair else 'disabled'} (ALEMBIC_AUTO_REPAIR={int(auto_repair)})",
        flush=True,
    )
    print(f"[entrypoint] alembic repair strict mode = {int(strict_mode)}", flush=True)

    engine = sa.create_engine(database_url)
    quoted_schema = schema.replace('"', '""')

    def _read_sql_rows(connection: sa.Connection) -> list[str]:
        return connection.execute(
            sa.text(
                f'SELECT version_num FROM "{quoted_schema}".alembic_version_core ORDER BY version_num'
            )
        ).scalars().all()

    def _read_alembic_ctx_heads(connection: sa.Connection) -> list[str]:
        context = MigrationContext.configure(
            connection,
            opts={"version_table": "alembic_version_core", "version_table_schema": schema},
        )
        return sorted(context.get_current_heads())

    def _log_state(
        db_rows: list[str],
        alembic_ctx_heads: list[str],
        lineage_ok: bool | None,
        decision: str,
    ) -> None:
        print(f"[entrypoint] db version rows (sql) = {db_rows}", flush=True)
        print(f"[entrypoint] alembic context current_heads = {alembic_ctx_heads}", flush=True)
        print(f"[entrypoint] script heads = {heads}", flush=True)
        print(
            f"[entrypoint] lineage check = {'OK' if lineage_ok else 'FAIL' if lineage_ok is False else 'N/A'}",
            flush=True,
        )
        print(f"[entrypoint] decision = {decision}", flush=True)

    def _log_mode(mode: str, reason: str) -> None:
        print(f"[entrypoint] migration mode selected: {mode} ({reason})", flush=True)

    try:
        with engine.begin() as connection:
            connection.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{quoted_schema}"'))
            connection.execute(
                sa.text(
                    f'''
                    CREATE TABLE IF NOT EXISTS "{quoted_schema}".alembic_version_core (
                        version_num VARCHAR(128) NOT NULL PRIMARY KEY
                    )
                    '''
                )
            )

        with engine.connect() as connection:
            db_revisions = _read_sql_rows(connection)
            alembic_ctx_heads = _read_alembic_ctx_heads(connection)

        print(f"[entrypoint] alembic_version_core rows: {db_revisions}", flush=True)

        if db_revisions != alembic_ctx_heads:
            if not auto_repair:
                _log_state(db_revisions, alembic_ctx_heads, None, "FAIL")
                raise RuntimeError(
                    "alembic_version_table_mismatch: "
                    f"db_rows={db_revisions} alembic_ctx_heads={alembic_ctx_heads} "
                    f"version_table_schema={schema}"
                )
            repair_revisions = alembic_ctx_heads or heads
            with engine.begin() as connection:
                _replace_versions(connection, schema, repair_revisions)
            with engine.connect() as connection:
                after_repair_heads = _read_alembic_ctx_heads(connection)
            _log_state(db_revisions, alembic_ctx_heads, None, "REPAIR_CTX_MISMATCH")
            _log_mode("repair", "version table differs from alembic context")
            print(f"[entrypoint] after repair alembic context current_heads = {after_repair_heads}", flush=True)
            return

        if not db_revisions:
            with engine.connect() as connection:
                schema_tables = _read_schema_tables(connection, schema)
                non_version_tables = [
                    table_name for table_name in schema_tables if table_name != "alembic_version_core"
                ]
                schema_not_empty = len(non_version_tables) > 0
                clients_columns = _read_clients_columns(connection, schema)

            print(
                f"[entrypoint] schema tables in {schema}: {_format_table_preview(non_version_tables)}",
                flush=True,
            )
            print(f"[entrypoint] clients columns in {schema}: {clients_columns}", flush=True)

            if schema_not_empty:
                with engine.begin() as connection:
                    revisions_to_insert = heads
                    if revisions_to_insert:
                        _replace_versions(connection, schema, revisions_to_insert)

                with engine.connect() as connection:
                    after_repair_heads = _read_alembic_ctx_heads(connection)
                _log_state(db_revisions, alembic_ctx_heads, None, "STAMP_HEAD_ON_NON_EMPTY_SCHEMA")
                _log_mode("stamp", "version table empty but schema already has domain tables")
                print(
                    f"[entrypoint] after reset/repair alembic context current_heads = {after_repair_heads}",
                    flush=True,
                )
                return

            _log_state(db_revisions, alembic_ctx_heads, None, "UPGRADE_EMPTY_SCHEMA")
            _log_mode("upgrade", "fresh schema with empty version table")
            return

        invalid_revisions = [
            revision for revision in db_revisions if script.get_revision(revision) is None
        ]
        if invalid_revisions:
            if not auto_repair:
                _log_state(db_revisions, alembic_ctx_heads, False, "FAIL")
                raise RuntimeError(
                    "[entrypoint] auto-repair action: FAIL_INVALID_REV "
                    f"invalid revisions in {schema}.alembic_version_core: {invalid_revisions}. "
                    "Set ALEMBIC_AUTO_REPAIR=1 to repair automatically in non-prod environments."
                )
            with engine.begin() as connection:
                _replace_versions(connection, schema, heads)
            with engine.connect() as connection:
                after_repair_heads = _read_alembic_ctx_heads(connection)
            _log_state(db_revisions, alembic_ctx_heads, False, "REPAIR_INVALID_REVISIONS")
            _log_mode("repair", "invalid revision row detected")
            print(f"[entrypoint] after repair alembic context current_heads = {after_repair_heads}", flush=True)
            return

        lineage_mismatch = [
            revision
            for revision in db_revisions
            if not any(_is_ancestor(script, revision, head_revision) for head_revision in heads)
        ]
        if lineage_mismatch:
            if not auto_repair:
                _log_state(db_revisions, alembic_ctx_heads, False, "FAIL")
                raise RuntimeError(
                    f"lineage mismatch: db_heads={db_revisions} script_heads={heads}. "
                    "Set ALEMBIC_AUTO_REPAIR=1 to repair automatically in non-prod environments."
                )
            with engine.begin() as connection:
                _replace_versions(connection, schema, heads)
            with engine.connect() as connection:
                after_repair_heads = _read_alembic_ctx_heads(connection)
            _log_state(db_revisions, alembic_ctx_heads, False, "REPAIR_LINEAGE_MISMATCH")
            _log_mode("repair", "db revision is not ancestor of script head")
            print(f"[entrypoint] after repair alembic context current_heads = {after_repair_heads}", flush=True)
            return

        _log_state(db_revisions, alembic_ctx_heads, True, "NONE")
        _log_mode("skip", "version table is already consistent")
    except Exception as exc:
        print(f"[entrypoint] critical: alembic consistency repair failed: {exc!r}", flush=True)
        if strict_mode:
            raise
        print("[entrypoint] safe fallback mode: continue with alembic upgrade head", flush=True)
        _log_mode("upgrade", "fallback after repair exception")
    finally:
        engine.dispose()


if __name__ == "__main__":
    ensure_alembic_version_consistency()
