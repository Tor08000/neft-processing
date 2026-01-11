# OPS 14 — Clearing Batch Build

## Goal
Ops builds clearing batches for a period and reviews batch details.

## Actors & Roles
- Admin / Ops

## Prerequisites
- Clearing data available.

## UI Flow
**Admin UI**
- Clearing batches list → build batch → view batch operations.

## API Flow
1. `POST /api/clearing/batches/build` — build batch for period.
2. `GET /api/clearing/batches` — list batches.
3. `GET /api/clearing/batches/{batch_id}` — batch details.
4. `GET /api/clearing/batches/{batch_id}/operations` — batch operations.

## DB Touchpoints
- `clearing_batch` — batch records.
- `clearing_batch_operation` — operations linked to batch.
- `clearing` — legacy clearing entries.

## Events & Audit
- **NOT IMPLEMENTED**: `CLEARING_BATCH_BUILT` explicit event code.

## Security / Gates
- Requires `admin:clearing:*` permission.

## Failure modes
- Batch already exists for period → `409` or service error.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_admin_clearing_api.py`.
- smoke cmd: `scripts/smoke_clearing_batch.cmd` (fails with NOT IMPLEMENTED).
- PASS: batch created and operations list returned.
