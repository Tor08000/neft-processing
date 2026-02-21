from __future__ import annotations

import os

import psycopg
from alembic import command

from app.alembic_runtime import (
    AUTH_TABLE_RESET_ALLOWLIST,
    fetch_db_revision,
    get_script_directory,
    is_db_revision_known,
    make_alembic_config,
    should_reset_for_broken_revision,
)


def _drop_auth_objects(dsn: str) -> None:
    with psycopg.connect(dsn) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            for table_name in AUTH_TABLE_RESET_ALLOWLIST:
                cur.execute(f'DROP TABLE IF EXISTS public."{table_name}" CASCADE')
            cur.execute("DROP TABLE IF EXISTS public.alembic_version")
            cur.execute("DROP TABLE IF EXISTS processing_auth.alembic_version_auth")
            cur.execute("DROP SCHEMA IF EXISTS processing_auth")


def _is_dev_mode() -> bool:
    return (os.getenv("APP_ENV", "dev") or "dev").strip().lower() == "dev"


def run() -> None:
    dsn = os.environ["DATABASE_URL"]
    cfg = make_alembic_config()
    script = get_script_directory(cfg)
    heads = tuple(script.get_heads())

    if len(heads) != 1:
        raise RuntimeError(f"multiple alembic heads detected: {heads}")

    expected_head = heads[0]
    initial_db_revision = fetch_db_revision(dsn)
    print(f"[entrypoint] detected DB revision: {initial_db_revision}", flush=True)
    print(f"[entrypoint] script heads: {heads}", flush=True)

    revision_known = is_db_revision_known(script, initial_db_revision)
    if initial_db_revision and not revision_known:
        print(f"[entrypoint] unknown DB revision detected: {initial_db_revision}", flush=True)
        if not should_reset_for_broken_revision(db_revision=initial_db_revision, revision_known=False):
            raise RuntimeError(
                f"DB revision {initial_db_revision} is unknown to this build; "
                "run with DEV_DB_RECOVERY=reset or AUTH_DB_RECOVERY=reset, "
                "or manually fix public.alembic_version"
            )
        if not _is_dev_mode():
            raise RuntimeError(
                "Refusing destructive auth DB recovery outside dev mode "
                f"(APP_ENV={os.getenv('APP_ENV', 'dev')})"
            )

        print("[entrypoint] running auth DB reset recovery", flush=True)
        _drop_auth_objects(dsn)
        command.stamp(cfg, "base")
        print("[entrypoint] alembic stamp base executed", flush=True)

    try:
        command.upgrade(cfg, "head")
    except Exception as exc:
        print(f"[entrypoint] alembic upgrade failed: {exc}", flush=True)
        raise

    final_db_revision = fetch_db_revision(dsn)
    print(f"[entrypoint] upgrade executed; final DB revision: {final_db_revision}", flush=True)
    if final_db_revision not in heads:
        raise RuntimeError(
            "final alembic revision mismatch: "
            f"expected one of {heads}, got {final_db_revision}"
        )

    print("[entrypoint] final revision matches head", flush=True)


if __name__ == "__main__":
    run()
