# OPS 14 — Clearing Batch Build

## Goal
Admin builds clearing batches for settlement.

## Actors & Roles
- Ops/Admin

## Prerequisites
- Core API running with `postgres`.

## UI Flow
**Admin portal**
- Clearing batches → build batch → review operations.

## API Flow
1. `POST /api/clearing/run?clearing_date=YYYY-MM-DD` — run clearing for date.
2. `GET /api/clearing/batches/{id}` — fetch batch details.
3. `GET /api/clearing/batches/{id}/operations` — list batch operations.

## DB Touchpoints
- `clearing_batch`, `clearing_batch_operation`.

## Events & Audit
- `SETTLEMENT_CALCULATED` audit events for settlement batches.

## Security / Gates
- Admin permissions required (`admin:clearing:*`).

## Failure modes
- Clearing date without data → empty batch.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_admin_clearing_api.py`.
- smoke cmd: `scripts/smoke_clearing_batch.cmd` (placeholder).
- PASS: batch created and operations listed.
