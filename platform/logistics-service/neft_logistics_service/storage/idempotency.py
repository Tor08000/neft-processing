from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class IdempotencyRecord:
    scope: str
    key: str
    request_hash: str
    status: str
    response_code: int | None
    response_body: dict | None


def hash_payload(payload: dict) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class IdempotencyStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS logistics_idempotency_keys (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    key TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_code INTEGER NULL,
                    response_body TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(scope, key)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS ix_logistics_idempotency_created_at ON logistics_idempotency_keys(created_at)")

    def get(self, scope: str, key: str) -> IdempotencyRecord | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT scope,key,request_hash,status,response_code,response_body FROM logistics_idempotency_keys WHERE scope=? AND key=?",
                (scope, key),
            ).fetchone()
            if not row:
                return None
            return IdempotencyRecord(
                scope=row["scope"],
                key=row["key"],
                request_hash=row["request_hash"],
                status=row["status"],
                response_code=row["response_code"],
                response_body=json.loads(row["response_body"]) if row["response_body"] else None,
            )

    def start_processing(self, scope: str, key: str, request_hash: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            try:
                conn.execute(
                    "INSERT INTO logistics_idempotency_keys(id,scope,key,request_hash,status,created_at,updated_at) VALUES (hex(randomblob(16)),?,?,?,?,?,?)",
                    (scope, key, request_hash, "processing", now, now),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def finalize(self, scope: str, key: str, status: str, code: int, body: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE logistics_idempotency_keys SET status=?, response_code=?, response_body=?, updated_at=? WHERE scope=? AND key=?",
                (status, code, json.dumps(body), now, scope, key),
            )
