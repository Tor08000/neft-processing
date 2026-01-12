from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg import sql

# Настройки БД берем из .env (docker-compose -> env_file: .env)
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "neft")
POSTGRES_USER = os.getenv("POSTGRES_USER", "neft")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "neft")
AUTH_DB_SCHEMA = os.getenv("AUTH_DB_SCHEMA", "public")

logger = logging.getLogger(__name__)

DSN_ASYNC = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)


@asynccontextmanager
async def get_conn():
    """
    Даём (conn, cur) так, как ожидают роуты:
    `async with get_conn() as (conn, cur): ...`
    """
    conn = await psycopg.AsyncConnection.connect(DSN_ASYNC)
    try:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                sql.SQL("SET search_path TO {}, public").format(sql.Identifier(AUTH_DB_SCHEMA))
            )
            yield conn, cur
    finally:
        if not conn.closed:
            await conn.close()


async def ensure_users_table() -> None:
    conn = await psycopg.AsyncConnection.connect(DSN_ASYNC)
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s AND table_schema=%s",
                ("users", AUTH_DB_SCHEMA),
            )
            exists = await cur.fetchone()
            if not exists:
                logger.critical(
                    "auth-host: users table missing in schema %s", AUTH_DB_SCHEMA
                )
                raise SystemExit(1)
    finally:
        if not conn.closed:
            await conn.close()
