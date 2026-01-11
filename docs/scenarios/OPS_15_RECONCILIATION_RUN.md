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
4. `POST /api/v1/admin/integrations/bank/statements/import` — upload bank statement and auto-run reconciliation.
5. `GET /api/v1/admin/integrations/bank/statements` — list imported statements.

**NOT IMPLEMENTED**
- `GET /api/reconciliation/runs/{run_id}/export` (export report).

## DB Touchpoints
- `reconciliation_runs` — run metadata.
- `reconciliation_discrepancies` — diff records.
- `external_statements` — provider statements.
- `bank_statements`, `bank_transactions` — imported statements and transactions.
- `bank_reconciliation_runs`, `bank_reconciliation_diffs`, `bank_reconciliation_matches` — bank reconciliation outcomes.

## Events & Audit
- `BANK_STATEMENT_IMPORTED` — statement upload audit event.
- `RECONCILIATION_RUN_COMPLETED` — bank reconciliation completion audit event.
- **NOT IMPLEMENTED**: `RECON_RUN_STARTED`, `RECON_DIFF_DETECTED`, `RECON_RUN_FINISHED` event codes.

## Security / Gates
- Requires `admin:reconciliation:*` permission.

## Failure modes
- Missing provider config → `422` or `409` depending on service validation.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_reconciliation_v1.py`.
- smoke cmd: `scripts/smoke_reconciliation_run.cmd` (fails with NOT IMPLEMENTED).
- PASS: run completes and discrepancies can be queried.
