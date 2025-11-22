import os
import psycopg
from contextlib import asynccontextmanager

DSN = os.getenv("DATABASE_URL", "postgresql+psycopg://neft:neftpass@postgres:5432/neft")
# psycopg3 async DSN должен быть postgresql://
DSN_ASYNC = DSN.replace("+psycopg", "") if "+psycopg" in DSN else DSN

@asynccontextmanager
async def get_conn():
    async with psycopg.AsyncConnection.connect(DSN_ASYNC) as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            yield conn, cur
