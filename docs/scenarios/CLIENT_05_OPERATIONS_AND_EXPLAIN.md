# CLIENT 05 — Operations List + Explain

## Goal
Client reviews operations and obtains explain/reason details for decisions.

## Actors & Roles
- Client Owner / Client Admin
- Regular User (view-only)

## Prerequisites
- Processing-core API.
- Operation data ingested.

## UI Flow
**Client portal**
- Operations list → operation details → explain (reason codes / rules).

## API Flow
1. `GET /api/v1/client/operations` — list operations.
2. `GET /api/v1/client/operations/{operation_id}` — operation details.
3. `GET /api/v1/core/explain?kind=operation&id={operation_id}` — explain (core API prefix).

## DB Touchpoints
- `operations` — operation records.
- `decision_memory` — decision snapshots used by explain.
- `case_events` — `TRANSACTION_INGESTED` events from ingestion.

## Events & Audit
- `TRANSACTION_INGESTED` — case event emitted during fleet ingestion.
- **NOT IMPLEMENTED**: `EXPLAIN_GENERATED` event is not emitted.

## Security / Gates
- Client portal endpoints require client auth context.
- Explain endpoint requires a bearer token (admin or client) and resolves tenant scope.

## Failure modes
- Operation not found → `404 operation_not_found`.
- Missing explain kind/id → `422 kind_required` or `id_required`.

## VERIFIED
- pytest: **NOT IMPLEMENTED** (explain content assertions not present).
- smoke cmd: `scripts/smoke_operations_explain.cmd` (fails with NOT IMPLEMENTED).
- PASS: explain response contains matched rules/reasons for operation.
