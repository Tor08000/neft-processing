# PARTNER 11 — Payouts Batch Export

## Goal
Partner exports payout batches and downloads export files.

## Actors & Roles
- Partner Admin
- Ops/Admin

## Prerequisites
- Core API running with `postgres` and `minio`.

## UI Flow
**Partner portal**
- Payouts list → open batch → download export.

## API Flow
1. `GET /api/v1/payouts/batches` — list payout batches.
2. `GET /api/v1/payouts/batches/{id}` — batch details.
3. `POST /api/v1/payouts/exports` — create export.
4. `GET /api/v1/payouts/exports` — list exports.
5. `GET /api/v1/payouts/exports/{id}/download` — download export.

## DB Touchpoints
- `payout_batches`, `payout_exports`, `settlement_payouts`.

## Events & Audit
- `PAYOUT_INITIATED`, `PAYOUT_CONFIRMED` recorded in audit log.

## Security / Gates
- ABAC enforced for payout exports (`payouts:export`).

## Failure modes
- Export for missing batch → `404`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_payout_exports_e2e.py`, `platform/processing-core/app/tests/test_payout_exports_xlsx_e2e.py`.
- smoke cmd: `scripts/smoke_payouts_batch_export.cmd` (placeholder).
- PASS: export created and download returns file.
