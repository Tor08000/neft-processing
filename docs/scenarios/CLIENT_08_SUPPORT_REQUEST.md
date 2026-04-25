# CLIENT 08 - Support Request

## Goal
Client creates and tracks support requests while the canonical owner remains the `cases` domain.

## Actors & Roles
- Client Owner / Client User
- Support / Ops

## Prerequisites
- Core API running with `postgres`.

## UI Flow
**Client portal**
- Support page -> create request -> review status -> canonical case link (`/cases/:id`) stays available from helpdesk detail -> ops resolves request.

## API Flow
1. `POST /api/v1/support/requests` - create compatibility support request.
2. `GET /api/v1/support/requests` - list support requests.
3. `GET /api/v1/support/requests/{id}` - request details.
4. `POST /api/v1/support/requests/{id}/status` - admin status transition.
5. Canonical owner row materializes in `cases`.

## DB Touchpoints
- `support_requests` - compatibility tail.
- `cases`, `case_events`, `case_comments` - canonical owner state.

## Events & Audit
- `SUPPORT_REQUEST_CREATED`
- `SUPPORT_REQUEST_STATUS_CHANGED`
- canonical case events in `case_events`

## Security / Gates
- Client auth required for create/list/detail.
- Admin auth required for status changes.

## Failure modes
- Request not found or forbidden -> `404` / `403`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_support_requests.py`, `platform/processing-core/app/tests/test_cases_permissions.py`, `platform/processing-core/app/tests/test_support_request_storage_truth.py`.
- smoke cmd: `scripts/smoke_support_ticket.cmd`.
- PASS: support request is created via compatibility route, list/detail succeed, admin resolves it, and the canonical `cases` row persists the synced state.
