# PARTNER 12 — Partner Documents (EDO)

## Goal
Partner lists EDO documents, downloads artifacts, and acknowledges receipt.

## Actors & Roles
- Partner Admin

## Prerequisites
- Core API running with `postgres`.

## UI Flow
**Partner portal**
- EDO documents list → document details → download artifacts → acknowledge.

## API Flow
1. `GET /partner/api/v1/edo/documents` — list partner EDO documents.
2. `GET /partner/api/v1/edo/documents/{id}` — document details.
3. `GET /partner/api/v1/edo/documents/{id}/artifacts` — download artifacts.
4. `POST /partner/api/v1/edo/documents/{id}/ack` — acknowledge.

## DB Touchpoints
- `edo_documents`, `edo_artifacts`, `edo_transitions`.

## Events & Audit
- EDO transitions stored in `edo_transitions` and audit log.

## Security / Gates
- Partner auth required; partner ownership enforced by token context.

## Failure modes
- Document not found or not owned by partner → `404` / `403`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_edo_events.py`.
- smoke cmd: `scripts/smoke_partner_documents.cmd`.
- PASS: partner login + `portal/me` resolve partner context; seeded partner EDO document is visible through list/details/artifacts/transitions and acknowledgement responds successfully.
