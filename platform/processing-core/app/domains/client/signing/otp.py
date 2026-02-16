from __future__ import annotations

import hashlib
import random


def generate_otp_code() -> str:
    return f"{random.SystemRandom().randint(0, 999999):06d}"


def hash_otp_code(otp_code: str) -> str:
    return hashlib.sha256(otp_code.encode("utf-8")).hexdigest()


def verify_otp_code(otp_code: str, otp_hash: str) -> bool:
    return hash_otp_code(otp_code) == otp_hash
