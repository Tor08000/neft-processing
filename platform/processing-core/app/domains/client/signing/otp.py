from __future__ import annotations

import hashlib
import random
import secrets


def generate_otp_code() -> str:
    return f"{random.SystemRandom().randint(0, 999999):06d}"


def generate_otp_salt() -> str:
    return secrets.token_hex(16)


def hash_otp_code(otp_code: str, *, salt: str, pepper: str) -> str:
    return hashlib.sha256(f"{salt}{otp_code}{pepper}".encode("utf-8")).hexdigest()


def verify_otp_code(otp_code: str, otp_hash: str, *, salt: str, pepper: str) -> bool:
    return hash_otp_code(otp_code, salt=salt, pepper=pepper) == otp_hash
