# PARTNER 11 — Payouts: Batch → Export → Mark Sent/Settled

## Goal
Partner or ops builds payout batches, exports files, and marks payouts sent/settled.

## Actors & Roles
- Partner Admin
- Ops/Admin

## Prerequisites
- Settlement data available.

## UI Flow
**Partner portal**
- Payout batches → export → mark sent/settled.

**NOT IMPLEMENTED**
- Partner portal payout batch UI not present.

## API Flow
**NOT IMPLEMENTED**
- No payout batch/export endpoints exist.
- Existing admin payout endpoints are per-payout, not batch-based:
  - `POST /api/settlements/payouts/{payout_id}/send`
  - `POST /api/settlements/payouts/{payout_id}/confirm`

## DB Touchpoints
- `settlement_payouts` — payout records.
- `settlement_periods`, `settlement_items` — settlement sources.

## Events & Audit
- `PAYOUT_INITIATED`, `PAYOUT_CONFIRMED` — case events for payout lifecycle.
- **NOT IMPLEMENTED**: `PAYOUT_BATCH_BUILT`, `PAYOUT_EXPORTED`, `PAYOUT_MARKED_SENT`, `PAYOUT_SETTLED`.

## Security / Gates
- Admin payouts require `admin` permissions.

## Failure modes
- Missing payout record → `404 payout_not_found`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_payout_exports_e2e.py` (export logic only).
- smoke cmd: `scripts/smoke_payouts_batch_export.cmd` (fails with NOT IMPLEMENTED).
- PASS: **NOT IMPLEMENTED**.
