# CLIENT 07 — Reconciliation Act: Request → Generate → Sign

## Goal
Client requests a reconciliation act, receives generated document, and acknowledges/signs it.

## Actors & Roles
- Client Owner / Client Accountant
- Admin (Ops)

## Prerequisites
- Client portal enabled.
- Ops/admin to attach reconciliation result.

## UI Flow
**Client portal**
- Request reconciliation → track status → download → acknowledge.

**Admin**
- Mark request in progress → attach result → mark sent.

## API Flow
**Client portal**
1. `POST /api/v1/client/reconciliation-requests` — create request.
2. `GET /api/v1/client/reconciliation-requests` — list requests.
3. `GET /api/v1/client/reconciliation-requests/{request_id}/download` — download result PDF.
4. `POST /api/v1/client/reconciliation-requests/{request_id}/ack` — acknowledge.

**Admin**
1. `POST /api/reconciliation-requests/{request_id}/mark-in-progress`.
2. `POST /api/reconciliation-requests/{request_id}/attach-result`.
3. `POST /api/reconciliation-requests/{request_id}/mark-sent`.

**NOT IMPLEMENTED**
- Explicit sign endpoint (`/reconciliation/requests/{id}/sign`). Acknowledgement is the only client action.

## DB Touchpoints
- `reconciliation_requests` — request lifecycle and result object key.
- `document_acknowledgements` — client acknowledgements.
- `invoices` — linked to reconciliation request (for inclusion).
- `bank_statements`, `bank_transactions` — imported statements used for reconciliation runs.
- `bank_reconciliation_runs`, `bank_reconciliation_diffs` — reconciliation outcomes after bank import.

## Events & Audit
- `RECONCILIATION_REQUEST_CREATED` — client request creation audit event.
- `RECONCILIATION_ACKNOWLEDGED` — client acknowledgement audit event.
- `RECONCILIATION_GENERATED`, `RECONCILIATION_SENT` — admin-side status changes.
- `BANK_STATEMENT_IMPORTED` — audit event on statement upload.
- `RECONCILIATION_RUN_COMPLETED` — audit event on bank reconciliation run.
- **NOT IMPLEMENTED**: `RECON_SIGNED` event code (signing not separate from ack).

## Security / Gates
- Client portal auth required; access to request scoped to client.
- Admin endpoints require support/admin context.

## Failure modes
- Duplicate active request for same period → returns existing request.
- Missing result object key/hash → download/ack blocked.

## VERIFIED
- pytest: **NOT IMPLEMENTED** (no end-to-end reconciliation doc tests).
- smoke cmd: `scripts/smoke_reconciliation_request_sign.cmd` (fails with NOT IMPLEMENTED).
- PASS: request created → result attached → client can download and acknowledge.
