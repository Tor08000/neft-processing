from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

REDACTION_DISPLAY = "REDACTED"
HASH_LENGTH = 10

EMAIL_REGEX = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
PHONE_REGEX = re.compile(r"\+?\d[\d\s().-]{7,}\d")
BEARER_REGEX = re.compile(r"bearer\s+[A-Z0-9._-]+", re.IGNORECASE)
JWT_REGEX = re.compile(r"[A-Z0-9_-]+\.[A-Z0-9_-]+\.[A-Z0-9_-]+", re.IGNORECASE)
PAN_REGEX = re.compile(r"(?:\d[ -]?){13,19}")
IBAN_REGEX = re.compile(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", re.IGNORECASE)


@dataclass(frozen=True)
class FieldRule:
    id: str
    kind: str
    message: str
    mask: str
    pattern: re.Pattern[str]


def _build_field_regex(terms: list[str]) -> re.Pattern[str]:
    joined = "|".join(re.escape(term) for term in terms)
    return re.compile(rf"(^|[._\-\s])({joined})($|[._\-\s])", re.IGNORECASE)


FIELD_RULES = [
    FieldRule(
        id="field_contains_secret",
        kind="secret",
        message="Field contains a secret token/password",
        mask="full",
        pattern=_build_field_regex(
            [
                "password",
                "pass",
                "secret",
                "token",
                "api_key",
                "apikey",
                "authorization",
                "cookie",
                "session",
                "private_key",
            ]
        ),
    ),
    FieldRule(
        id="field_contains_email",
        kind="email",
        message="Field contains email",
        mask="email",
        pattern=_build_field_regex(["email"]),
    ),
    FieldRule(
        id="field_contains_phone",
        kind="phone",
        message="Field contains phone number",
        mask="phone",
        pattern=_build_field_regex(["phone", "tel"]),
    ),
    FieldRule(
        id="field_contains_card",
        kind="card",
        message="Field contains card PAN",
        mask="card",
        pattern=_build_field_regex(["card", "pan"]),
    ),
    FieldRule(
        id="field_contains_bank",
        kind="bank",
        message="Field contains bank account",
        mask="bank",
        pattern=_build_field_regex(["iban", "account", "bank"]),
    ),
    FieldRule(
        id="field_contains_address",
        kind="pii",
        message="Field contains address",
        mask="full",
        pattern=_build_field_regex(["address"]),
    ),
    FieldRule(
        id="field_contains_identity",
        kind="identifier",
        message="Field contains document identifier",
        mask="full",
        pattern=_build_field_regex(["passport", "inn", "snils", "driver"]),
    ),
    FieldRule(
        id="field_contains_name",
        kind="pii",
        message="Field contains full name",
        mask="full",
        pattern=re.compile(r"(^|[._\-\s])(full_name|name)($|[._\-\s])", re.IGNORECASE),
    ),
]


def _normalize_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _find_email(value: str) -> str | None:
    match = EMAIL_REGEX.search(value)
    return match.group(0) if match else None


def _find_phone(value: str) -> str | None:
    match = PHONE_REGEX.search(value)
    return match.group(0) if match else None


def _find_pan(value: str) -> tuple[str, str] | None:
    match = PAN_REGEX.search(value)
    if not match:
        return None
    raw = match.group(0)
    digits = _normalize_digits(raw)
    if len(digits) < 13 or len(digits) > 19:
        return None
    return raw, digits


def _find_iban(value: str) -> str | None:
    match = IBAN_REGEX.search(value)
    return match.group(0) if match else None


def _has_bearer_token(value: str) -> bool:
    return BEARER_REGEX.search(value) is not None


def _has_jwt(value: str) -> bool:
    return JWT_REGEX.search(value) is not None


def _simple_hash(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return digest[:HASH_LENGTH]


def _build_reason(kind: str, rule: str, message: str) -> dict[str, str]:
    return {"kind": kind, "rule": rule, "message": message}


def _mask_email(value: str) -> str:
    match = _find_email(value)
    if not match:
        return REDACTION_DISPLAY
    local, _, domain = match.partition("@")
    if not domain:
        return REDACTION_DISPLAY
    prefix = local[: min(2, len(local))]
    return f"{prefix}***@{domain}"


def _mask_phone(value: str) -> str:
    digits = _normalize_digits(value)
    if len(digits) < 7:
        return REDACTION_DISPLAY
    return f"***-**-{digits[-2:]}"


def _mask_pan(digits: str) -> str:
    prefix = digits[:6]
    suffix = digits[-4:]
    masked = "*" * max(0, len(digits) - 10)
    return f"{prefix}{masked}{suffix}"


def _mask_bank(value: str) -> str:
    trimmed = re.sub(r"\s", "", value)
    if len(trimmed) <= 8:
        return REDACTION_DISPLAY
    return f"{trimmed[:4]}****{trimmed[-4:]}"


def _match_field_rule(field_path: str) -> FieldRule | None:
    if not field_path:
        return None
    for rule in FIELD_RULES:
        if rule.pattern.search(field_path):
            return rule
    return None


def redact_value(field_path: str, value: Any, *, include_hash: bool = True) -> Any:
    field_rule = _match_field_rule(field_path)
    if field_rule:
        display = REDACTION_DISPLAY
        if field_rule.mask == "email" and isinstance(value, str):
            display = _mask_email(value)
        elif field_rule.mask == "phone" and isinstance(value, str):
            display = _mask_phone(value)
        elif field_rule.mask == "card" and isinstance(value, str):
            display = _mask_pan(_normalize_digits(value))
        elif field_rule.mask == "bank" and isinstance(value, str):
            display = _mask_bank(value)
        payload: dict[str, Any] = {
            "redacted": True,
            "display": display,
            "reason": _build_reason(field_rule.kind, field_rule.id, field_rule.message),
        }
        if include_hash and value is not None:
            payload["hash"] = _simple_hash(str(value))
        return payload

    if not isinstance(value, str):
        return value

    if _has_bearer_token(value) or _has_jwt(value):
        payload = {
            "redacted": True,
            "display": REDACTION_DISPLAY,
            "reason": _build_reason("secret", "value_contains_token", "Value looks like a secret token"),
        }
        if include_hash:
            payload["hash"] = _simple_hash(value)
        return payload

    email = _find_email(value)
    if email:
        if email == value:
            payload = {
                "redacted": True,
                "display": _mask_email(value),
                "reason": _build_reason("email", "value_is_email", "Value is an email"),
            }
            if include_hash:
                payload["hash"] = _simple_hash(value)
            return payload
        payload = {
            "redacted": True,
            "display": value.replace(email, _mask_email(email)),
            "reason": _build_reason("free_text", "value_contains_email", "Free text contains an email"),
        }
        if include_hash:
            payload["hash"] = _simple_hash(value)
        return payload

    phone = _find_phone(value)
    if phone:
        if phone == value:
            payload = {
                "redacted": True,
                "display": _mask_phone(value),
                "reason": _build_reason("phone", "value_is_phone", "Value is a phone number"),
            }
            if include_hash:
                payload["hash"] = _simple_hash(value)
            return payload
        payload = {
            "redacted": True,
            "display": value.replace(phone, _mask_phone(phone)),
            "reason": _build_reason("free_text", "value_contains_phone", "Free text contains a phone number"),
        }
        if include_hash:
            payload["hash"] = _simple_hash(value)
        return payload

    pan_match = _find_pan(value)
    if pan_match:
        raw, digits = pan_match
        if _normalize_digits(value) == digits:
            payload = {
                "redacted": True,
                "display": _mask_pan(digits),
                "reason": _build_reason("card", "value_is_card", "Value looks like card PAN"),
            }
            if include_hash:
                payload["hash"] = _simple_hash(value)
            return payload
        payload = {
            "redacted": True,
            "display": value.replace(raw, _mask_pan(digits)),
            "reason": _build_reason("free_text", "value_contains_card", "Free text contains card PAN"),
        }
        if include_hash:
            payload["hash"] = _simple_hash(value)
        return payload

    iban = _find_iban(value)
    if iban:
        if iban == value:
            payload = {
                "redacted": True,
                "display": _mask_bank(value),
                "reason": _build_reason("bank", "value_is_iban", "Value looks like IBAN or bank account"),
            }
            if include_hash:
                payload["hash"] = _simple_hash(value)
            return payload
        payload = {
            "redacted": True,
            "display": value.replace(iban, _mask_bank(iban)),
            "reason": _build_reason("free_text", "value_contains_iban", "Free text contains bank account"),
        }
        if include_hash:
            payload["hash"] = _simple_hash(value)
        return payload

    return value


def redact_deep(value: Any, field_path: str, *, include_hash: bool = True) -> Any:
    maybe_redacted = redact_value(field_path, value, include_hash=include_hash)
    if maybe_redacted is None or isinstance(maybe_redacted, (str, int, float, bool)):
        return maybe_redacted
    if isinstance(maybe_redacted, dict):
        if maybe_redacted.get("redacted") is True:
            return maybe_redacted
        return {
            key: redact_deep(item, f"{field_path}.{key}" if field_path else key, include_hash=include_hash)
            for key, item in maybe_redacted.items()
        }
    if isinstance(maybe_redacted, list):
        return [
            redact_deep(item, f"{field_path}[{index}]", include_hash=include_hash)
            for index, item in enumerate(maybe_redacted)
        ]
    return maybe_redacted


def redact_for_audit(field_path: str, value: Any) -> Any:
    return redact_deep(value, field_path, include_hash=True)

