# CLIENT 08 — Support Request

## Goal
Client creates and tracks support tickets.

## Actors & Roles
- Client Owner / Client User
- Support/Ops

## Prerequisites
- Core API running with `postgres`.

## UI Flow
**Client portal**
- Support page → create ticket → add comments → close ticket.

## API Flow
1. `POST /api/cases` — create ticket.
2. `GET /api/cases` — list tickets.
3. `GET /api/cases/{id}` — ticket details.
4. `POST /api/cases/{id}/comments` — add comment.
5. `POST /api/cases/{id}/close` — close case.

## DB Touchpoints
- `cases`, `case_events`, `case_comments`.

## Events & Audit
- `CASE_CREATED`, `STATUS_CHANGED`, `CASE_CLOSED`.

## Security / Gates
- Client auth required.

## Failure modes
- Case not found or forbidden → `404` / `403`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_cases_list.py`, `platform/processing-core/app/tests/test_cases_create_applies_queue_and_sla.py`.
- smoke cmd: `scripts/smoke_support_ticket.cmd` (placeholder).
- PASS: case created, updated, and closed.
