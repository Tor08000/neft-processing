# Phase 3 — Ledger Hash Chain

Implemented hash chain for `internal_ledger_transactions`:

- `batch_sequence` (strictly increasing per tenant)
- `previous_batch_hash`
- `batch_hash`
- `total_debit` / `total_credit` with DB check `total_debit = total_credit`

`batch_hash` is calculated via SHA256 over canonical payload:
`previous_batch_hash + serialized_postings + total_debit + total_credit + timestamp`.

Verification entrypoint: `verify_ledger_chain(db, tenant_id=...)` in `app/services/internal_ledger.py`.
