# OPS 14 - Clearing Batch Build

## Goal
Admin runs clearing for a billing date and verifies persisted merchant clearing rows.

## Actors & Roles
- Ops/Admin

## Prerequisites
- `core-api`, `auth-host`, and `postgres` are running.
- Finalized `billing_summary` rows exist for the target `clearing_date`.

## UI Flow
**Admin portal**
- Clearing compatibility batch review remains a separate surface under `/api/v1/admin/clearing/batches*`.
- This scenario verifies the admin clearing run action itself, not the older batch-review compatibility contour.

## API Flow
1. `POST /api/v1/admin/clearing/run?clearing_date=YYYY-MM-DD` - build clearing rows for the date from finalized `billing_summary`.
2. Repeating the same call returns `created=0` with `reason=already_exists` and does not duplicate persisted clearing rows.

## Compatibility note
- `/api/v1/admin/clearing/batches*` is a live compatibility batch-review surface backed by `clearing_batch` / `clearing_batch_operation`.
- It is verified by `test_admin_clearing_api.py`, but it is not the storage/read surface produced by `POST /api/v1/admin/clearing/run`.

## DB Touchpoints
- `billing_summary`
- `clearing`
- `billing_job_runs`

## Storage truth note
- Live `processing_core.billing_summary` storage for this contour is keyed by `billing_date`, `merchant_id`, `client_id`, `product_type`, and `currency`.
- The real smoke seeds against that live table shape and does not assume `billing_period_id` is present in the mounted database.

## Events & Audit
- No dedicated settlement audit event is asserted in this scenario.
- Verification relies on persisted `billing_job_runs` rows with `job_type = CLEARING` and success metrics for the initial run plus the already-exists replay.

## Security / Gates
- Admin auth required (`/api/core/admin/auth/verify`).

## Failure modes
- No finalized billing summaries for the date -> `200` with `{"clearing_date": "...", "created": 0, "reason": "no_data"}` and a successful `CLEARING` job row.
- Repeated run for the same date -> `200` with `{"clearing_date": "...", "created": 0, "reason": "already_exists"}` and no duplicate `clearing` rows.

## VERIFIED
- pytest:
  - `platform/processing-core/app/tests/test_admin_clearing_storage_truth.py`
  - `platform/processing-core/app/tests/test_admin_clearing_api.py`
  - `platform/processing-core/app/tests/test_admin_clearing_run.py`
- smoke cmd: `scripts/smoke_clearing_batch.cmd`
- PASS: seeded finalized summaries produce two persisted clearing rows, repeated run returns `already_exists`, and two successful `CLEARING` job rows capture the first run plus the replay.
