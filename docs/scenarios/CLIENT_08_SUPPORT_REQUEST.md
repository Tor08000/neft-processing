# CLIENT 08 — Support Request (Create → Status → Close)

## Goal
Client creates a support ticket and tracks status until closure.

## Actors & Roles
- Client user (creates ticket)
- Support admin (updates status, closes case)

## Prerequisites
- Processing-core API.
- Support user token context (client or admin) for `/cases` endpoints.

## UI Flow
**Client portal**
- Create ticket → view status.

**Admin**
- Update status → close case → add comments.

## API Flow
1. `POST /api/cases` — create case.
2. `GET /api/cases` — list client cases (scoped by creator).
3. `GET /api/cases/{case_id}` — view details.
4. `PATCH /api/cases/{case_id}` — admin update status/assignment.
5. `POST /api/cases/{case_id}/comments` — admin adds comment.

**NOT IMPLEMENTED**
- Client-side close endpoint (closure is admin-only).

## DB Touchpoints
- `cases` — ticket records.
- `case_events` — immutable event log.
- `case_comments` — discussion history.

## Events & Audit
- `CASE_CREATED` — emitted on case creation.
- `STATUS_CHANGED` — emitted when status changes.
- `CASE_CLOSED` — emitted on close.

## Security / Gates
- Client can only view own cases; admin required for update/close.

## Failure modes
- Missing client context → `403 missing_client_context`.
- Non-admin update attempt → `403 forbidden`.

## VERIFIED
- pytest: **NOT IMPLEMENTED** (support case e2e tests not present).
- smoke cmd: `scripts/smoke_support_ticket.cmd` (fails with NOT IMPLEMENTED).
- PASS: case created by client, admin updates to CLOSED, event log shows status changes.
