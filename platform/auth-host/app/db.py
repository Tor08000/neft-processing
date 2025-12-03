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
