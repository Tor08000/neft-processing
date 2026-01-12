# OPS 15 — Reconciliation Run

## Goal
Admin runs internal/external reconciliation and reviews discrepancies.

## Actors & Roles
- Ops/Admin

## Prerequisites
- Core API running with `postgres`.

## UI Flow
**Admin portal**
- Reconciliation runs → run reconciliation → review discrepancies.

## API Flow
1. `POST /api/reconciliation/run` — run internal reconciliation.
2. `POST /api/reconciliation/run/external` — run external reconciliation.
3. `GET /api/reconciliation/runs/{id}/discrepancies` — list discrepancies.

## DB Touchpoints
- `reconciliation_runs`, `reconciliation_discrepancies`.

## Events & Audit
- `RECONCILIATION_RUN_COMPLETED`, `EXTERNAL_RECONCILIATION_COMPLETED`.

## Security / Gates
- Admin permissions required (`admin:reconciliation:*`).

## Failure modes
- Missing reconciliation inputs → `400`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_reconciliation_v1.py`.
- smoke cmd: `scripts/smoke_reconciliation_run.cmd` (placeholder).
- PASS: reconciliation run completes and discrepancies returned.
