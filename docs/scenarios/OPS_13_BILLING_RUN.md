# OPS 13 — Billing Run

## Goal
Admin runs billing for a period and issues invoices.

## Actors & Roles
- Ops/Admin

## Prerequisites
- Core API running with `postgres` and `minio`.
- Billing seed data present.

## UI Flow
**Admin portal**
- Billing run page → run period → review invoices.

## API Flow
1. `POST /api/billing/run` — run billing.
2. `GET /api/billing/periods` — list billing periods.
3. `GET /api/billing/invoices` — list invoices.

## DB Touchpoints
- `billing_job_runs`, `billing_periods`, `invoices`.

## Events & Audit
- `INVOICE_ISSUED` for created invoices.

## Security / Gates
- Admin permissions required (`admin:billing:*`).

## Failure modes
- Missing seed data → billing run returns `400`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_invoice_state_machine.py`.
- smoke cmd: `scripts/smoke_billing_run.cmd`.
- PASS: billing run creates invoices and period records.
