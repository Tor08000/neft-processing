# CLIENT 07 — Reconciliation Request & Sign

## Goal
Client requests reconciliation, receives generated act, and acknowledges it.

## Actors & Roles
- Client Owner / Client Accountant
- Ops/Admin (attach result)

## Prerequisites
- Core API running with `postgres` and `minio`.

## UI Flow
**Client portal**
- Reconciliation requests list → request new reconciliation → download PDF → acknowledge.

## API Flow
1. `POST /api/v1/client/reconciliation-requests` — create request.
2. `GET /api/v1/client/reconciliation-requests` — list requests.
3. `GET /api/v1/client/reconciliation-requests/{id}/download` — download PDF.
4. `POST /api/v1/client/reconciliation-requests/{id}/ack` — acknowledge result.
5. `POST /api/v1/admin/reconciliation-requests/{id}/attach-result` — attach generated act (admin).

## DB Touchpoints
- `reconciliation_requests` — requests and status.
- `documents` — reconciliation act.
- `document_acknowledgements` — acknowledgements.

## Events & Audit
- `RECONCILIATION_REQUEST_CREATED`, `RECONCILIATION_GENERATED`, `RECONCILIATION_ACKNOWLEDGED`.

## Security / Gates
- Client portal auth required; admin actions require `admin:reconciliation:*`.

## Failure modes
- Request not found or mismatch client → `404` / `403`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_client_portal_api.py`.
- smoke cmd: `scripts/smoke_reconciliation_request_sign.cmd` (placeholder).
- PASS: request created, result attached, acknowledgement stored.
