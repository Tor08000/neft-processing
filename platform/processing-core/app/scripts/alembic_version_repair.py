from __future__ import annotations

import os

import sqlalchemy as sa
from alembic.config import Config
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
    try:
        with engine.begin() as connection:
            connection.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{quoted_schema}"'))
            connection.execute(
                sa.text(
                    f'''
                    CREATE TABLE IF NOT EXISTS "{quoted_schema}".alembic_version_core (
                        version_num VARCHAR(256) NOT NULL PRIMARY KEY
                    )
                    '''
                )
            )

            db_revisions = connection.execute(
                sa.text(
                    f'SELECT version_num FROM "{quoted_schema}".alembic_version_core ORDER BY version_num'
                )
            ).scalars().all()

            print(f"[entrypoint] alembic_version_core rows: {db_revisions}", flush=True)

            if not db_revisions:
                revisions_to_insert = bases or heads[:1]
                if not bases:
                    print(
                        "[entrypoint] warning: no base revisions detected; using first head as fallback",
                        flush=True,
                    )
                if revisions_to_insert:
                    _replace_versions(connection, schema, revisions_to_insert)
                print(
                    f"[entrypoint] auto-repair action: INSERT_BASE revisions={revisions_to_insert}",
                    flush=True,
                )
                return

            invalid_revisions = [
                revision for revision in db_revisions if script.get_revision(revision) is None
            ]
            if invalid_revisions:
                if not auto_repair:
                    raise RuntimeError(
                        "[entrypoint] auto-repair action: FAIL_INVALID_REV "
                        f"invalid revisions in {schema}.alembic_version_core: {invalid_revisions}. "
                        "Set ALEMBIC_AUTO_REPAIR=1 to repair automatically in non-prod environments."
                    )
                _replace_versions(connection, schema, heads)
                print(
                    "[entrypoint] auto-repair action: STAMP_HEAD "
                    f"reason=invalid_revision revisions={heads}",
                    flush=True,
                )
                return

            lineage_mismatch = [
                revision
                for revision in db_revisions
                if not any(_is_ancestor(script, revision, head_revision) for head_revision in heads)
            ]
            if lineage_mismatch:
                if not auto_repair:
                    raise RuntimeError(
                        "[entrypoint] auto-repair action: FAIL_LINEAGE "
                        f"lineage mismatch in {schema}.alembic_version_core for revisions {lineage_mismatch}. "
                        "Set ALEMBIC_AUTO_REPAIR=1 to repair automatically in non-prod environments."
                    )
                _replace_versions(connection, schema, heads)
                print(
                    "[entrypoint] auto-repair action: STAMP_HEAD "
                    f"reason=lineage_mismatch revisions={heads}",
                    flush=True,
                )
                print("[entrypoint] warning: alembic lineage mismatch repaired", flush=True)
                return

            print("[entrypoint] auto-repair action: NONE", flush=True)
    finally:
        engine.dispose()


if __name__ == "__main__":
    ensure_alembic_version_consistency()
