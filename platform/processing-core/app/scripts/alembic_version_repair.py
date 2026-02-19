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
            _log_state(db_revisions, alembic_ctx_heads, None, "STAMP_HEAD")
            print(f"[entrypoint] after repair alembic context current_heads = {after_repair_heads}", flush=True)
            return

        if not db_revisions:
            if not auto_repair:
                _log_state(db_revisions, alembic_ctx_heads, None, "FAIL")
                raise RuntimeError(f"empty {schema}.alembic_version_core while ALEMBIC_AUTO_REPAIR=0")
            revisions_to_insert = bases or heads[:1]
            with engine.begin() as connection:
                if revisions_to_insert:
                    _replace_versions(connection, schema, revisions_to_insert)
            with engine.connect() as connection:
                after_repair_heads = _read_alembic_ctx_heads(connection)
            _log_state(db_revisions, alembic_ctx_heads, None, "INSERT_BASE")
            print(f"[entrypoint] after repair alembic context current_heads = {after_repair_heads}", flush=True)
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
            _log_state(db_revisions, alembic_ctx_heads, False, "STAMP_HEAD")
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
            _log_state(db_revisions, alembic_ctx_heads, False, "STAMP_HEAD")
            print(f"[entrypoint] after repair alembic context current_heads = {after_repair_heads}", flush=True)
            return

        _log_state(db_revisions, alembic_ctx_heads, True, "NONE")
    finally:
        engine.dispose()


if __name__ == "__main__":
    ensure_alembic_version_consistency()
