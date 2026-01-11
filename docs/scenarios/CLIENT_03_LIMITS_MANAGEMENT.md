# CLIENT 03 — Limits Management

## Goal
Client admins view and manage spending limits, and verify enforcement on transactions.

## Actors & Roles
- Client Owner / Client Admin
- Regular User (view-only)

## Prerequisites
- Processing-core API.
- Fleet module enabled for the client.

## UI Flow
**Client portal**
- Limits profile view → set/revoke limits.

## API Flow
1. `GET /api/client/fleet/limits?scope_type=...&scope_id=...` — list limits.
2. `POST /api/client/fleet/limits/set` — create/update limit.
3. `POST /api/client/fleet/limits/revoke` — revoke limit.

**NOT IMPLEMENTED**
- Self-service “apply preset profile” is not exposed; CRM limit profiles exist but no client UI uses them.

## DB Touchpoints
- `fuel_limits` — active limits by scope (client/card/group).
- `crm_limit_profiles` — CRM profiles (used by contracts, not self-service).
- `fuel_limit_breaches` — limit breach records (if enforcement is active).

## Events & Audit
- `LIMIT_SET`, `LIMIT_REVOKED` — emitted as `case_events` by fleet service.
- `FUEL_LIMIT_BREACH_DETECTED` — emitted on enforcement when limits are breached.

## Security / Gates
- Requires `client:fleet:limits:manage` permission.

## Failure modes
- Limit set with invalid enum values → `400 invalid_limit_config`.
- Unauthorized user → `403 forbidden`.
- Limit breach → decline with `FUEL_LIMIT_BREACH_DETECTED` case event.

## VERIFIED
- pytest: **NOT IMPLEMENTED** (limit enforcement tests not isolated).
- smoke cmd: `scripts/smoke_limits_apply_and_enforce.cmd` (fails with NOT IMPLEMENTED).
- PASS: limit appears in list and enforcement produces breach record/event.
