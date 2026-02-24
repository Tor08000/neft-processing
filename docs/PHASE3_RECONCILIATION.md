# Phase 3 — Reconciliation

Added `reconcile_accounts(db, ...)` that verifies:

- debit/credit system net equals zero
- restricted accounts are not negative

Writes immutable-style report row in `reconciliation_reports` with:

- `status` (`OK`/`ERROR`)
- `payload`
- `report_hash` (SHA256 of canonical payload)
