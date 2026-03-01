from __future__ import annotations


class LedgerError(Exception):
    pass


class InvariantViolation(LedgerError):
    pass


class IdempotencyMismatch(LedgerError):
    pass


class NotFound(LedgerError):
    pass
