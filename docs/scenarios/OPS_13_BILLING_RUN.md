# OPS 13 — Billing Run (Daily/Monthly)

## Goal
Ops triggers billing runs and verifies invoice generation.

## Actors & Roles
- Admin / Ops

## Prerequisites
- Billing periods configured.
- Admin token with `admin:billing:*` permission.

## UI Flow
**Admin UI**
- Billing runs list → run daily/monthly → review invoices/errors.

## API Flow
1. `POST /api/billing/run` — run billing for a period (manual).
2. `GET /api/billing/periods` — list billing periods.
3. `GET /api/billing/invoices?limit=...` — list invoices.
4. `GET /api/billing/invoices/{invoice_id}` — invoice detail.

**NOT IMPLEMENTED**
- Explicit `/admin/billing/runs/daily` and `/admin/billing/runs/monthly` endpoints (use `/billing/run` instead).

## DB Touchpoints
- `billing_job_runs` — job run metadata.
- `billing_periods` — period lifecycle.
- `invoices`, `invoice_payments`, `credit_notes` — billing outputs.
- `billing_task_links` — task linkage for billing jobs.

## Events & Audit
- `INVOICE_ISSUED` — case event emitted by billing service.
- **NOT IMPLEMENTED**: `BILLING_RUN_STARTED`, `BILLING_RUN_FINISHED`, `BILLING_RUN_FAILED` explicit events.

## Security / Gates
- Requires `admin:billing:*` permission.

## Failure modes
- Billing period closed/locked → `409` or validation error.
- Concurrent run → `409 already running`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_invoice_state_machine.py`.
- smoke cmd: `scripts/smoke_billing_run.cmd`.
- PASS: billing run creates invoices and invoice transitions are valid.
