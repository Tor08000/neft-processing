# Audit Phase 2 — Idempotency Spec

## Key semantics

All money-producing commands must have an idempotency key.

- Refund: `refund_requests.idempotency_key` (unique)
- Reversal: `reversals.idempotency_key` (unique)
- Posting batches: `posting_batches.idempotency_key` (unique)
- Internal ledger transaction: `internal_ledger_transactions.idempotency_key` (unique, normalized with `ledger:` prefix)
- Outbox event: `event_outbox.idempotency_key` (unique)

## Scope

Current scope is **global per table**. Recommended next step is composite scope `(tenant_id, command_family, key)` to prevent cross-domain key collisions.

## Replay behavior

- Same key must return same created object.
- No additional postings.
- No additional outbox rows.

## Concurrency behavior

- DB uniqueness is the primary lock.
- Transaction code catches `IntegrityError`, re-reads existing record, and returns replay.
- User should not receive raw DB uniqueness error in successful replay race.

## TTL / retention

- Financial idempotency records are durable and should not be short-lived TTL cache.
- Archive policy can move old keys to cold storage, but semantic replay window should cover chargeback/refund SLA.

## Exactly-once for outbox

- Outbox row written in same DB transaction as business state.
- Dedup on `event_outbox.idempotency_key`.
- Consumers should dedupe by `event id`/key.
