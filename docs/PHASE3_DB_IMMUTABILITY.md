# Phase 3 — DB Immutability

DB-level protections added:

- PostgreSQL triggers on `internal_ledger_entries` reject UPDATE/DELETE.
- SQLite trigger emulation on `internal_ledger_entries` rejects UPDATE/DELETE (for tests).
- PostgreSQL immutability triggers for idempotency entities:
  - `invoice_payments`
  - `credit_notes`
  - `payouts`

This makes ledger and idempotency protection independent from ORM hooks.
