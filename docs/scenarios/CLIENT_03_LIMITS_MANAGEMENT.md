# CLIENT 03 — Limits Management

## Goal
Client reviews and updates fleet fuel limits, and limits enforcement is reflected in operations.

## Actors & Roles
- Client Owner / Fleet Manager
- Ops/Admin (limit profiles)

## Prerequisites
- Core API running with `postgres`.
- Limit profiles seeded via CRM or admin limits rules.

## UI Flow
**Client portal**
- Limits list → create/update limit → review breaches in operations.

## API Flow
1. `GET /api/client/fleet/limits` — list current limits.
2. `POST /api/client/fleet/limits/set` — create or update limit.
3. `POST /api/client/fleet/limits/revoke` — revoke limit.

## DB Touchpoints
- `fuel_limits` — client/card/vehicle limits.
- `limit_configs`, `crm_limit_profiles` — limit rules and profiles.

## Events & Audit
- `LIMIT_SET`, `LIMIT_REVOKED` events recorded in `case_events`.
- Limit breaches recorded as `FUEL_LIMIT_BREACH_DETECTED`.

## Security / Gates
- Client permissions required (`client:fleet:*`).

## Failure modes
- Limit scope mismatch or unauthorized access → `403`.
- Invalid limit payload → `422`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_fleet_v1.py`, `platform/processing-core/app/tests/test_fuel_limits_engine.py`.
- smoke cmd: `scripts/smoke_limits_apply_and_enforce.cmd` (placeholder).
- PASS: limits list/set/revoke succeed and breach event is recorded.
