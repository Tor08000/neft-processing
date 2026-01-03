# Trust Gates

Trust Gates are mandatory CI checks that protect the trusted audit layer. They run on every PR and block merges if any trust guarantees regress.

## What is verified

1. **Audit events for critical operations**
   * Finance flows (invoice issuance, payment capture, refunds).
   * Marketplace order creation + transition events.
   * Fleet limits and hard breach auto-block actions.
   * Case creation and export generation.
   * Ledger postings emit audit log entries with hash-chain continuity and redaction.

2. **DB immutability (WORM)**
   * Append-only tables reject `UPDATE`/`DELETE` at the database level.
   * Core tables include `audit_log`, `case_events`, ledger entries, billing flows, marketplace order events, and fuel transactions.

3. **Export signing + verification**
   * Exports are hashed, signed (Local signer in tests), and verified end-to-end.

## CI integration

The workflow `.github/workflows/ci-trust-gates.yml` includes a dedicated job named `trust-gates` that:

1. Boots Postgres and runs Alembic migrations.
2. Validates WORM triggers are present.
3. Runs trust gate integration tests (`platform/processing-core/app/tests/test_trust_gates.py`).
4. Runs export verification smoke checks.

Any failure is blocking: Trust Gates are **required** on every PR.

## Local run (Windows CMD)

From the repo root:

```cmd
scripts\trust_gates.cmd
```

This script:

1. Starts Postgres via Docker Compose.
2. Applies migrations.
3. Verifies WORM triggers.
4. Runs Trust Gate tests.

## Local run (manual)

```bash
docker compose -f docker-compose.test.yml --profile test up -d postgres
docker compose -f docker-compose.test.yml --profile test run --rm core-api alembic upgrade head
docker compose -f docker-compose.test.yml --profile test exec -T postgres psql -U neft -d neft -f scripts/ci/check_worm_triggers.sql
pytest platform/processing-core/app/tests/test_trust_gates.py
```
