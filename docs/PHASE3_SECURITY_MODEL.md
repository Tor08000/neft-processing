# Phase 3 — Security Model

Financial hardening model:

1. **Immutability at DB level**
   - ledger entry UPDATE/DELETE blocked in DB.
2. **Tamper evidence**
   - ledger transaction hash chain per tenant.
3. **Settlement anchoring**
   - period snapshots hashed and persisted.
4. **Double-entry invariants in DB**
   - `total_debit = total_credit` check constraint.
5. **Idempotency hardening**
   - idempotent entities immutable; `response_hash` persisted for replay validation.
6. **External audit readiness**
   - deterministic verification primitives: `verify_ledger_chain`, `verify_period_hash`, reconciliation report hash.
