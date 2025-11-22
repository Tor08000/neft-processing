from __future__ import annotations

from contextlib import asynccontextmanager

import psycopg

from neft_shared.settings import get_settings

settings = get_settings()
DSN = settings.database_url
DSN_ASYNC = DSN.replace("+psycopg", "") if "+psycopg" in DSN else DSN


async def init_db() -> None:
    """Создаёт минимальные таблицы для auth-host, если их ещё нет."""

    async with psycopg.AsyncConnection.connect(DSN_ASYNC) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    full_name TEXT,
                    password_hash TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT now()
                )
                """
            )
            await conn.commit()


@asynccontextmanager
async def get_conn():
    async with psycopg.AsyncConnection.connect(DSN_ASYNC) as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            yield conn, cur
