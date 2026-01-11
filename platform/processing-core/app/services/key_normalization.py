from __future__ import annotations

import hashlib


def normalize_key(value: str, *, max_len: int = 128, prefix: str = "sha256:") -> str:
    if len(value) <= max_len:
        return value

    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    if len(prefix) + len(digest) > max_len:
        return digest[:max_len]
    return f"{prefix}{digest}"


def normalize_key_optional(
    value: str | None, *, max_len: int = 128, prefix: str = "sha256:"
) -> str | None:
    if value is None:
        return None
    return normalize_key(value, max_len=max_len, prefix=prefix)


__all__ = ["normalize_key", "normalize_key_optional"]
