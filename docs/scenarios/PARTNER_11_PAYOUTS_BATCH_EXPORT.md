# PARTNER 11 - Payouts Batch Export

## Goal
Ops/admin closes a partner payout period, generates an export file for the payout batch, and downloads the uploaded artifact.

Partner portal finance remains a separate read-side contour. The canonical export owner in this scenario is still the admin-authenticated compatibility route family under `/api/v1/payouts/*`, not partner self-service UI.

## Actors & Roles
- Ops/Admin
- Partner Finance user as a read-side consumer only

## Prerequisites
- `auth-host`, `core-api`, `postgres`, and `minio` running
- Canonical admin seed account available: `admin@neft.local / Neft123!`
- Active ABAC version available; the smoke script bootstraps the payout-export allow policy when it is missing

## UI Flow
**Export owner**
- No dedicated mounted admin portal page is used in the verified export flow yet; runtime verification happens through the live admin-authenticated API/smoke path.

**Partner portal**
- `/payouts` remains a finance read/history shell.
- Partner portal does not create payout export files in this contour.

## API Flow
1. `POST /api/v1/payouts/close-period` - create or replay a READY payout batch for the target partner/date range.
2. `GET /api/v1/payouts/batches` - list payout batches.
3. `GET /api/v1/payouts/batches/{batch_id}` - read batch detail.
4. `POST /api/v1/payouts/batches/{batch_id}/export` - create payout export file.
5. `GET /api/v1/payouts/batches/{batch_id}/exports` - list exports for the batch.
6. `GET /api/v1/payouts/exports/{export_id}/download` - download the generated file.

## DB Touchpoints
- `billing_periods`
- `operations`
- `payout_batches`
- `payout_items`
- `payout_export_files`
- `audit_logs`

## Events & Audit
- `PAYOUT_BATCH_CREATED`
- `PAYOUT_RECONCILE_OK`
- `PAYOUT_EXPORT_CREATED`
- `PAYOUT_EXPORT_UPLOADED`
- `PAYOUT_EXPORTED`
- `PAYOUT_EXPORT_DOWNLOADED`
- Idempotent replay and external-ref conflict rows are also written when applicable.

## Security / Gates
- Admin auth required for the verified runtime flow.
- Export creation requires the `marketplace:settlement` scope.
- ABAC enforces `payouts:export` on the target batch.
- The live smoke bootstraps `payout_export_admin_allow` into the active ABAC version when that policy is absent.
- Partner finance pages remain read-side only in the mounted portal topology.

## Failure modes
- Export for missing batch -> `404 batch_not_found`
- Download for missing export -> `404 export_not_found`
- Non-finalized billing period on close-period -> `409 billing_period_not_finalized`
- Duplicate external ref -> `409 external_ref_conflict`
- Unsupported export/bank format -> `400 format_not_supported` / `400 bank_format_*`

## VERIFIED
- pytest:
  - `platform/processing-core/app/tests/test_payouts_e2e.py`
  - `platform/processing-core/app/tests/test_payout_exports_e2e.py`
  - `platform/processing-core/app/tests/test_payout_exports_xlsx_e2e.py`
- smoke cmd: `scripts/smoke_payouts_batch_export.cmd`
- UI smoke: `frontends/e2e/tests/partner_payouts.spec.ts` covers the partner finance read shell only, not export creation.
- PASS:
  - seeded partner slice closes into a READY payout batch
  - batch list/detail return the same batch and aggregate
  - CSV export is created in `UPLOADED` state and downloadable
  - XLSX export coverage is verified by targeted pytest
  - persisted `payout_batches` and `payout_export_files` rows are verified in Postgres
