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
1. `POST /api/core/v1/admin/reconciliation/internal` — run internal reconciliation.
2. `POST /api/core/v1/admin/reconciliation/external/statements` — upload external statement.
3. `POST /api/core/v1/admin/reconciliation/external/run` — run canonical external reconciliation.
4. `GET /api/core/v1/admin/reconciliation/runs/{id}` — review run detail.
5. `GET /api/core/v1/admin/reconciliation/runs/{id}/discrepancies` — list discrepancies.
6. `GET /api/core/v1/admin/reconciliation/runs/{id}/export?format=csv` — export reconciliation result.

## DB Touchpoints
- `reconciliation_runs`, `reconciliation_discrepancies`, `external_statements`, `audit_log`.

## Events & Audit
- `RECONCILIATION_RUN_COMPLETED`, `EXTERNAL_RECONCILIATION_COMPLETED`.

## Security / Gates
- Admin permissions required (`admin:reconciliation:*`).

## Failure modes
- Missing reconciliation inputs → `400`.
- Invalid admin capability / missing permission → `403`.
- WORM / persistence drift must never surface as raw payload on the admin route.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_reconciliation_v1.py`.
- pytest: `platform/processing-core/app/tests/test_admin_reconciliation_details.py`.
- smoke cmd: `scripts/smoke_reconciliation_run.cmd`.
- PASS: admin login/verify succeeds, canonical external statement upload succeeds, canonical external reconciliation completes with 3 discrepancies (`2 balance_mismatch`, `1 unmatched_external`), run detail/discrepancy export respond, and persisted reconciliation + audit rows are verified.
