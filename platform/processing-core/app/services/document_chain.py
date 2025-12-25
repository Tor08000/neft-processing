from __future__ import annotations

import hashlib
from datetime import datetime


def compute_ack_hash(document_hash: str, ack_at: datetime, ack_by: str) -> str:
    payload = f"{document_hash}:{ack_at.isoformat()}:{ack_by}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
