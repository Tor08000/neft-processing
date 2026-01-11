# OPS 15 — Reconciliation Run

## Goal
Ops runs reconciliation and reviews discrepancies and reports.

## Actors & Roles
- Admin / Ops

## Prerequisites
- Reconciliation providers configured.

## UI Flow
**Admin UI**
- Reconciliation runs list → differences → export report.

## API Flow
1. `POST /api/reconciliation/run` — run reconciliation (internal/external).
2. `GET /api/reconciliation/runs` — list runs.
3. `GET /api/reconciliation/runs/{run_id}/discrepancies` — discrepancies.

**NOT IMPLEMENTED**
- `GET /api/reconciliation/runs/{run_id}/export` (export report).

**Offline reconciliation (fleet)**
1. `POST /internal/fuel/offline-reconcile` — run offline batch reconciliation for period.
2. `GET /internal/fuel/offline-reconcile/{run_id}` — run status.
3. `GET /internal/fuel/offline-reconcile/{run_id}/discrepancies` — offline discrepancies.

## DB Touchpoints
- `reconciliation_runs` — run metadata.
- `reconciliation_discrepancies` — diff records.
- `external_statements` — provider statements.
- `fleet_offline_reconciliation_runs` — offline reconciliation runs for fuel batches.
- `fleet_offline_discrepancies` — offline mismatch records (limits/products/cards).

## Events & Audit
- **NOT IMPLEMENTED**: `RECON_RUN_STARTED`, `RECON_DIFF_DETECTED`, `RECON_RUN_FINISHED` event codes.

## Security / Gates
- Requires `admin:reconciliation:*` permission.

## Failure modes
- Missing provider config → `422` or `409` depending on service validation.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_reconciliation_v1.py`.
- smoke cmd: `scripts/smoke_reconciliation_run.cmd` (fails with NOT IMPLEMENTED).
- PASS: run completes and discrepancies can be queried.
