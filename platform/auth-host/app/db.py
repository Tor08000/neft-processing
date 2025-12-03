from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

# Настройки БД берем из .env (docker-compose -> env_file: .env)
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "neft")
POSTGRES_USER = os.getenv("POSTGRES_USER", "neft")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "neft")

DSN_ASYNC = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)


async def init_db() -> None:
    """
    Инициализация БД auth-host:
    - создаем таблицу users, если её нет.
    Без EXTENSION'ов и uuid-ossp, максимально просто и надежно.
    """
    logger.info("auth-host: init_db start")

    conn: psycopg.AsyncConnection | None = None
    try:
        conn = await psycopg.AsyncConnection.connect(DSN_ASYNC)

        async with conn.cursor() as cur:
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS clients (
                    id UUID PRIMARY KEY,
                    tenant_id BIGINT NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT,
                    full_name TEXT,
                    status TEXT DEFAULT 'ACTIVE'
                )
                """
            )

            await cur.execute(
                "ALTER TABLE clients ADD COLUMN IF NOT EXISTS email TEXT"
            )

            await cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS clients_email_lower_idx
                ON clients (lower(email))
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    full_name TEXT,
                    password_hash TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )

            await cur.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'users'
                          AND column_name = 'id'
                          AND table_schema = 'public'
                          AND data_type <> 'uuid'
                    ) THEN
                        ALTER TABLE users ALTER COLUMN id DROP DEFAULT;
                        ALTER TABLE users ALTER COLUMN id TYPE uuid USING (
                            CASE
                                WHEN pg_typeof(id)::text = 'uuid' THEN id
                                ELSE md5(id::text || clock_timestamp()::text)::uuid
                            END
                        );
                    END IF;
                END$$;
                """
            )

            await cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT")
            await cur.execute(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT"
            )
            await cur.execute(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN"
            )
            await cur.execute(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ"
            )
            await cur.execute(
                "UPDATE users SET is_active = TRUE WHERE is_active IS NULL"
            )
            await cur.execute(
                "UPDATE users SET created_at = now() WHERE created_at IS NULL"
            )
            await cur.execute(
                "UPDATE users SET password_hash = '' WHERE password_hash IS NULL"
            )
            await cur.execute(
                "ALTER TABLE users ALTER COLUMN id SET NOT NULL"
            )
            await cur.execute(
                "ALTER TABLE users ALTER COLUMN email SET NOT NULL"
            )
            await cur.execute(
                "ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL"
            )
            await cur.execute(
                "ALTER TABLE users ALTER COLUMN is_active SET NOT NULL"
            )
            await cur.execute(
                "ALTER TABLE users ALTER COLUMN is_active SET DEFAULT TRUE"
            )
            await cur.execute(
                "ALTER TABLE users ALTER COLUMN created_at SET NOT NULL"
            )
            await cur.execute(
                "ALTER TABLE users ALTER COLUMN created_at SET DEFAULT now()"
            )

            await cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_idx
                ON users (lower(email))
                """
            )

        await conn.commit()
        logger.info("auth-host: DB init OK")

    except Exception:
        logger.exception("auth-host: DB init FAILED")
        if conn is not None:
            try:
                await conn.rollback()
            except Exception:
                logger.exception("auth-host: rollback failed")
        raise
    finally:
        if conn is not None:
            try:
                await conn.close()
            except Exception:
                logger.exception("auth-host: close connection failed")


@asynccontextmanager
async def get_conn():
    """
    Даём (conn, cur) так, как ожидают роуты:
    `async with get_conn() as (conn, cur): ...`
    """
    conn = await psycopg.AsyncConnection.connect(DSN_ASYNC)
    try:
        async with conn.cursor(row_factory=dict_row) as cur:
            yield conn, cur
    finally:
        if not conn.closed:
            await conn.close()
