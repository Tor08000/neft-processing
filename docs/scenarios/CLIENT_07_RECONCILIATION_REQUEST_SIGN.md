# CLIENT 07 - Reconciliation Request & Result Acknowledgement

## Goal
Client requests reconciliation, receives a generated result artifact, downloads it, and acknowledges both the artifact and the request.

## Actors & Roles
- Client Owner / Client Accountant
- Ops/Admin

## Prerequisites
- Core API running with `postgres` and `minio`.

## UI Flow
**Client portal**
- Reconciliation requests list -> request new reconciliation -> download result PDF -> acknowledge result -> acknowledge request.

## API Flow
1. `POST /api/v1/client/reconciliation-requests` - create request.
2. `GET /api/v1/client/reconciliation-requests` - list requests.
3. `GET /api/v1/client/reconciliation-requests/{id}` - request details.
4. `POST /api/v1/admin/reconciliation-requests/{id}/mark-in-progress` - move request into ops handling.
5. `POST /api/v1/admin/reconciliation-requests/{id}/attach-result` - attach generated result.
6. `POST /api/v1/admin/reconciliation-requests/{id}/mark-sent` - mark result as sent.
7. `GET /api/v1/client/reconciliation-requests/{id}/download` - download result PDF.
8. `POST /api/v1/client/documents/ACT_RECONCILIATION/{id}/ack` - acknowledge result artifact.
9. `POST /api/v1/client/reconciliation-requests/{id}/ack` - acknowledge request lifecycle.

## DB Touchpoints
- `reconciliation_requests` - request state and result metadata.
- `document_acknowledgements` - immutable client acknowledgement of the reconciliation artifact.

## Events & Audit
- `RECONCILIATION_REQUEST_CREATED`
- `RECONCILIATION_GENERATED`
- `RECONCILIATION_SENT`
- `RECONCILIATION_ACKNOWLEDGED`
- `DOCUMENT_ACKNOWLEDGED`

## Security / Gates
- Client portal auth required.
- Admin actions require admin auth under `/api/v1/admin/*`.

## Failure modes
- Request not found or foreign client -> `404` / `403`.
- Missing attached result -> `404`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_client_portal_api.py`.
- smoke cmd: `scripts/smoke_reconciliation_request_sign.cmd`.
- PASS: request created, MinIO-backed result attached and marked sent, client download succeeds, artifact acknowledgement persists, and request reaches `ACKNOWLEDGED`.
