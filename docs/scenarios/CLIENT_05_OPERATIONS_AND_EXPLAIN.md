# CLIENT 05 — Operations & Explain

## Goal
Client reviews operations and receives explainability for declined/flagged transactions.

## Actors & Roles
- Client Owner / Accountant

## Prerequisites
- Core API running with `postgres`.

## UI Flow
**Client portal**
- Operations list → operation details → explain breakdown (reasons, recommendations).

## API Flow
1. `GET /api/v1/client/operations` — list operations.
2. `GET /api/v1/client/operations/{id}` — operation details.
3. `POST /api/v1/core/explain` — explain decision for operation.

## DB Touchpoints
- `operations`, `transactions` — operation records.
- `decision_memory` — explain snapshots.

## Events & Audit
- `TRANSACTION_INGESTED` in `case_events`.

## Security / Gates
- Client permissions required (`client:operations:*`).

## Failure modes
- Unauthorized access → `403`.
- Explain request for missing operation → `404`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_unified_explain_fuel.py`.
- smoke cmd: `scripts/smoke_operations_explain.cmd` (placeholder).
- PASS: explain response contains reasons/recommendations sections.
