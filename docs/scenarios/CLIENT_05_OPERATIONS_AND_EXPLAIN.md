# CLIENT 05 - Operations & Explain

## Goal
Client reviews operations and receives explainability for decline-related KPI signals.

## Actors & Roles
- Client Owner / Accountant

## Prerequisites
- Core API running with `postgres`.

## UI Flow
**Client portal**
- Operations list -> operation details -> explain breakdown (reasons, evidence, recommendations).

## API Flow
1. `GET /api/v1/client/operations` - list operations.
2. `GET /api/v1/client/operations/{id}` - operation details.
3. `GET /api/core/explain?kpi_key=declines_total&window_days=7` - explain current declines KPI signal.

## DB Touchpoints
- `operations` - operation records used by list/details.
- `bi_daily_metrics` - KPI read model used by explain.

## Events & Audit
- `TRANSACTION_INGESTED`.

## Security / Gates
- Client permissions required (`client:operations:*`).

## Failure modes
- Unauthorized access -> `403`.
- Missing operation -> `404`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_client_portal_api.py`, `platform/processing-core/app/tests/test_explain_v2_endpoint.py`.
- smoke cmd: `scripts/smoke_operations_explain.cmd`.
- PASS: seeded declined operation appears in list/details; explain response contains reason tree, evidence, and recommendations sections.
