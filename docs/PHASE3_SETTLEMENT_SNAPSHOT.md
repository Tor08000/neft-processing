# Phase 3 — Settlement Snapshot

On settlement approval:

- snapshot of period balances is built
- totals (`total_debit`, `total_credit`) captured
- `last_batch_hash` captured
- `period_hash` = SHA256(snapshot payload)

Stored in `settlement_periods` as:

- `snapshot_payload`
- `last_batch_hash`
- `period_hash`
- `genesis_batch_hash`

Validation helper: `verify_period_hash(period)`.
