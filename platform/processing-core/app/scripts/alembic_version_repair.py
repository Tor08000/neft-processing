from __future__ import annotations

import os
from dataclasses import dataclass

import sqlalchemy as sa
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

VERSION_TABLE_NAME = "alembic_version_core"
DOMAIN_TABLE_PROBE = ("clients", "accounts", "operations", "ledger_entries")


@dataclass(frozen=True)
class RepairDecision:
    action: str
    reason: str


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
    connection.execute(sa.text(f'TRUNCATE TABLE "{quoted_schema}".{VERSION_TABLE_NAME}'))
    for revision in revisions:
        connection.execute(
            sa.text(f'INSERT INTO "{quoted_schema}".{VERSION_TABLE_NAME}(version_num) VALUES (:revision)'),
            {"revision": revision},
        )


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


def _schema_has_domain_tables(connection: sa.Connection, schema: str) -> bool:
    rows = connection.execute(
        sa.text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_name = ANY(:table_names)
            """
        ),
        {"schema": schema, "table_names": list(DOMAIN_TABLE_PROBE)},
    ).scalars().all()
    return bool(rows)


def _write_decision_artifacts(decision: RepairDecision) -> None:
    decision_file = (os.getenv("ALEMBIC_DECISION_FILE") or "").strip()
    if decision_file:
        with open(decision_file, "w", encoding="utf-8") as handle:
            handle.write(f"ALEMBIC_DECISION={decision.action}\n")
            handle.write(f"ALEMBIC_DECISION_REASON={decision.reason}\n")

    print(f"[entrypoint] mode selected = {decision.action}", flush=True)
    print(f"[entrypoint] mode reason = {decision.reason}", flush=True)


def ensure_alembic_version_consistency() -> RepairDecision:
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
    print(f"[entrypoint] alembic script heads: {heads}", flush=True)
    print(f"[entrypoint] alembic script base revisions: {sorted(_find_base_revisions(script))}", flush=True)

    engine = sa.create_engine(database_url)
    quoted_schema = schema.replace('"', '""')

    def _read_version_rows(connection: sa.Connection) -> list[str]:
        return connection.execute(
            sa.text(f'SELECT version_num FROM "{quoted_schema}".{VERSION_TABLE_NAME} ORDER BY version_num')
        ).scalars().all()

    def _read_alembic_ctx_heads(connection: sa.Connection) -> list[str]:
        context = MigrationContext.configure(
            connection,
            opts={"version_table": VERSION_TABLE_NAME, "version_table_schema": schema},
        )
        return sorted(context.get_current_heads())

    try:
        with engine.begin() as connection:
            connection.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{quoted_schema}"'))
            connection.execute(
                sa.text(
                    f'CREATE TABLE IF NOT EXISTS "{quoted_schema}".{VERSION_TABLE_NAME} '
                    '(version_num VARCHAR(128) NOT NULL PRIMARY KEY)'
                )
            )

        with engine.connect() as connection:
            db_revisions = _read_version_rows(connection)
            alembic_ctx_heads = _read_alembic_ctx_heads(connection)
            schema_tables = _read_schema_tables(connection, schema)
            has_domain_tables = _schema_has_domain_tables(connection, schema)

        print(f"[entrypoint] version_table_rows = {len(db_revisions)}", flush=True)
        print(f"[entrypoint] alembic current = {alembic_ctx_heads}", flush=True)
        print(f"[entrypoint] alembic heads = {heads}", flush=True)
        print(f"[entrypoint] schema tables = {schema_tables}", flush=True)

        if len(db_revisions) == 0:
            if has_domain_tables:
                decision = RepairDecision("STAMP", "version table empty but domain tables already exist")
            else:
                decision = RepairDecision("UPGRADE", "fresh schema and empty version table")
            _write_decision_artifacts(decision)
            return decision

        if len(db_revisions) > 1:
            if not auto_repair:
                decision = RepairDecision("FAIL", "multiple rows in version table")
                _write_decision_artifacts(decision)
                raise RuntimeError(f"expected one row in {schema}.{VERSION_TABLE_NAME}, got {len(db_revisions)}")
            with engine.begin() as connection:
                _replace_versions(connection, schema, heads)
            decision = RepairDecision("REPAIR", "multiple rows repaired to script head")
            _write_decision_artifacts(decision)
            return decision

        current_revision = db_revisions[0]
        if script.get_revision(current_revision) is None:
            if not auto_repair:
                decision = RepairDecision("FAIL", f"unknown revision in version table: {current_revision}")
                _write_decision_artifacts(decision)
                raise RuntimeError(decision.reason)
            with engine.begin() as connection:
                _replace_versions(connection, schema, heads)
            decision = RepairDecision("REPAIR", "unknown revision replaced with script head")
            _write_decision_artifacts(decision)
            return decision

        lineage_ok = any(_is_ancestor(script, current_revision, head_revision) for head_revision in heads)
        if not lineage_ok:
            if not auto_repair:
                decision = RepairDecision("FAIL", "lineage mismatch: current revision is not ancestor of head")
                _write_decision_artifacts(decision)
                raise RuntimeError(decision.reason)
            with engine.begin() as connection:
                _replace_versions(connection, schema, heads)
            decision = RepairDecision("REPAIR", "lineage mismatch repaired by stamping script head")
            _write_decision_artifacts(decision)
            return decision

        if db_revisions != alembic_ctx_heads and not auto_repair:
            decision = RepairDecision("FAIL", "alembic context differs from version table")
            _write_decision_artifacts(decision)
            raise RuntimeError(
                "alembic context mismatch. "
                f"db_rows={db_revisions}, alembic_current={alembic_ctx_heads}; possible wrong schema/version table"
            )

        if db_revisions != alembic_ctx_heads and auto_repair:
            with engine.begin() as connection:
                _replace_versions(connection, schema, alembic_ctx_heads or heads)
            decision = RepairDecision("REPAIR", "alembic context mismatch repaired")
            _write_decision_artifacts(decision)
            return decision

        decision = RepairDecision("SKIP", "version table is already consistent")
        _write_decision_artifacts(decision)
        return decision
    except Exception:
        if strict_mode:
            raise
        decision = RepairDecision("UPGRADE", "fallback to upgrade because repair step failed in non-strict mode")
        _write_decision_artifacts(decision)
        return decision
    finally:
        engine.dispose()


if __name__ == "__main__":
    ensure_alembic_version_consistency()
