# Audit Phase 2 — Audit Trail

## What is logged

For each material money-state transition:

- Ledger postings (`ledger_entries`, `posting_batches`, `internal_ledger_entries`)
- Audit log event via `AuditService.audit`
- Optional outbox event (`event_outbox`)

## Required fields

Audit envelope should contain:

- actor (`admin/client/partner/system`)
- request/correlation IDs
- input hash / idempotency key
- resulting object IDs (operation, posting batch, refund/reversal/dispute id)

Current implementation already stores core references for internal ledger transaction audits and invariant violations.

## Immutability model

- Ledger entries are append-only (update/delete denied by model-level guard).
- Corrections are represented by reversing/adjustment postings.
- Outbox entries deduplicated by unique idempotency key.

## Reproducibility

- Internal ledger entries include deterministic `entry_hash` derived from canonical payload.
- Posting batches can be replay-detected by idempotency keys.
- Invariant checker can rebuild violation context snapshots for invoices/settlements.

## Snapshot strategy

For critical objects, store before/after snapshots in audit records:

- settlement period state transitions
- refund/reversal/dispute resolution
- adjustment creation (reason, effective date, linked entity)

## Gap list / hardening backlog

1. Promote append-only enforcement to DB trigger level for all environments.
2. Add explicit `correlation_id` and input hash to all admin monetary endpoints.
3. Add immutable signed snapshots for period close artifacts.
