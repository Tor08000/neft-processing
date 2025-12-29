from __future__ import annotations

import os
from contextlib import asynccontextmanager

import psycopg
from psycopg.rows import dict_row

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
