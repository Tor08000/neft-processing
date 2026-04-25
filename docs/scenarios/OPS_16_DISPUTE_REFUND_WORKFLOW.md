# OPS 16 - Dispute / Refund Workflow

## Goal
Admin opens a dispute on a captured operation, moves it through review, accepts it with hold release plus refund/fee postings, and can also post a standalone refund.

## Actors & Roles
- Ops/Admin

## Prerequisites
- `auth-host`, `core-api`, and `postgres` are running.
- Admin login uses the canonical seeded credentials.

## UI Flow
**Admin portal**
- Disputes queue -> open dispute -> move to review -> accept/reject/close -> inspect refund outcome.
- Refunds page -> create refund -> verify posted status and posting reference.

## API Flow
1. `POST /api/v1/admin/disputes/open` - open dispute and place hold.
2. `POST /api/v1/admin/disputes/{id}/review` - move dispute to `UNDER_REVIEW`.
3. `POST /api/v1/admin/disputes/{id}/accept` - accept dispute, release hold, post refund and fee adjustment.
4. `POST /api/v1/admin/refunds` - create standalone refund request.

## DB Touchpoints
- `disputes`, `dispute_events`
- `posting_batches`, `ledger_entries`, `account_balances`
- `refund_requests`
- `operations.refunded_amount`

## Events & Audit
- Dispute events persisted for:
  - `OPENED`
  - `HOLD_PLACED`
  - `MOVED_TO_REVIEW`
  - `ACCEPTED`
  - `REFUND_POSTED`
  - `FEE_POSTED`
- Posting batches persisted for dispute hold, dispute refund, dispute fee adjustment, and standalone refund.

## Security / Gates
- Admin permissions required:
  - `admin:disputes:*`
  - `admin:refunds:*`

## Failure Modes
- Invalid dispute state transition -> `409`
- Missing account/ledger schema parity -> runtime 500 until additive repair migrations are applied

## VERIFIED
- pytest:
  - `platform/processing-core/app/tests/test_disputes.py`
  - `platform/processing-core/app/tests/test_refunds.py`
  - `platform/processing-core/app/tests/test_accounts_and_ledger.py`
  - `platform/processing-core/app/tests/test_admin_accounts_api.py`
  - `platform/processing-core/app/tests/test_posting_engine.py`
  - `platform/processing-core/app/tests/test_ledger_posting_engine.py`
- smoke cmd:
  - `scripts/smoke_dispute_refund.cmd`
- PASS:
  - admin login/verify succeeds
  - dispute open -> review -> accept succeeds through canonical admin routes
  - dispute hold is released after acceptance
  - refund request posts in `SAME_PERIOD`
  - persisted dispute events, posting batches, refund row, and `operations.refunded_amount` are verified
