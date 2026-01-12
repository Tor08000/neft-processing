# OPS 16 — Dispute / Refund Workflow

## Goal
Admin opens disputes, resolves them, and issues refunds where required.

## Actors & Roles
- Ops/Admin

## Prerequisites
- Core API running with `postgres`.

## UI Flow
**Admin portal**
- Disputes list → open dispute → accept/reject/close → review refund entries.

## API Flow
1. `POST /api/disputes/open` — open dispute.
2. `POST /api/disputes/{id}/review` — move to review.
3. `POST /api/disputes/{id}/accept` / `POST /api/disputes/{id}/reject` — resolve.
4. `POST /api/refunds` — create refund request.

## DB Touchpoints
- `disputes`, `dispute_events`.
- `billing_refunds` / `credit_notes` for refunds.

## Events & Audit
- Audit log entries for dispute transitions and refunds.

## Security / Gates
- Admin permissions required (`admin:disputes:*`, `admin:refunds:*`).

## Failure modes
- Invalid dispute state transition → `409`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_disputes.py`, `platform/processing-core/app/tests/test_refunds.py`.
- smoke cmd: `scripts/smoke_dispute_refund.cmd` (placeholder).
- PASS: dispute transitions apply and refund entries recorded.
