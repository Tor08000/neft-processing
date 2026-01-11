# OPS 16 — Dispute / Refund Workflow

## Goal
Ops opens disputes, reviews them, and issues refunds when approved.

## Actors & Roles
- Admin / Ops

## Prerequisites
- Operations available to dispute.

## UI Flow
**Admin UI**
- Disputes list → create dispute → approve refund / reject → track status.

## API Flow
1. `POST /api/disputes/open` — open dispute.
2. `POST /api/disputes/{dispute_id}/review` — move to review.
3. `POST /api/disputes/{dispute_id}/accept` — accept and resolve.
4. `POST /api/disputes/{dispute_id}/reject` — reject.
5. `POST /api/disputes/{dispute_id}/close` — close.
6. `POST /api/refunds` — request refund (ops refunds endpoint).

## DB Touchpoints
- `disputes` — dispute records.
- `dispute_events` — dispute lifecycle events.
- `refund_requests` — refund requests.
- `operations`, `ledger_entries` — financial postings.

## Events & Audit
- `DisputeEventType.OPENED`, `MOVED_TO_REVIEW`, `ACCEPTED`, `REJECTED`, `CLOSED` — dispute events.
- `REFUND_POSTED` — dispute event when refund posted.
- **NOT IMPLEMENTED**: `DISPUTE_CREATED`, `DISPUTE_RESOLVED`, `REFUND_ISSUED` as standalone event codes.

## Security / Gates
- Requires admin permissions (disputes/refunds routers are admin-only).

## Failure modes
- Invalid state transition → `409` or service error.
- Refund cap exceeded → `409 refund_cap_exceeded`.

## VERIFIED
- pytest: **NOT IMPLEMENTED** (refund ledger invariants not dedicated).
- smoke cmd: `scripts/smoke_dispute_refund.cmd` (fails with NOT IMPLEMENTED).
- PASS: dispute moves through statuses and refund request is recorded.
