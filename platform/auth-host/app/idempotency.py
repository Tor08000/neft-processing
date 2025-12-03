import hashlib
from fastapi import Header

def make_idempotency_key(
    method: str,
    path: str,
    payload: bytes,
    idem_header: str | None
) -> str:
    # приоритет — заголовок; иначе соберём детерминированный ключ
    if idem_header:
        return idem_header.strip()
    h = hashlib.sha256()
    h.update(method.encode())
    h.update(b":")
    h.update(path.encode())
    h.update(b":")
    h.update(payload or b"")
    return h.hexdigest()

async def get_idempotency_key(
    x_idempotency_key: str | None = Header(default=None)
) -> str | None:
    return x_idempotency_key
