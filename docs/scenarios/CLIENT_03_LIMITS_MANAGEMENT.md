# CLIENT 03 - Limits Management

## Goal
Client reviews and updates card limits through the mounted client-portal surface. Runtime enforcement remains covered by the fleet limit engine tests.

## Actors & Roles
- Client Owner
- Client Admin

## Prerequisites
- Core API running with `postgres`.

## UI Flow
**Client portal**
- Card detail -> update limit -> confirm visible limit state.

## API Flow
1. `GET /api/v1/client/cards/{card_id}` - inspect current card limits.
2. `POST /api/v1/client/cards/{card_id}/limits` - create or update a contractual limit for the card.
3. `GET /api/v1/client/cards` - confirm the card summary reflects the new limit.

## DB Touchpoints
- `cards` - card ownership surface.
- `limit_configs` - persisted contractual card limit.

## Events & Audit
- No dedicated fleet event is emitted by this client-portal surface.
- Runtime enforcement remains covered by `test_fuel_limits_engine.py`.

## Security / Gates
- Client auth required.

## Failure modes
- Card not found -> `404`.
- Invalid limit payload -> `400` / `422`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_client_portal_api.py`, `platform/processing-core/app/tests/test_fuel_limits_engine.py`.
- smoke cmd: `scripts/smoke_limits_apply_and_enforce.cmd`.
- PASS: seeded card accepts a DAILY_AMOUNT limit update and persisted `limit_configs` state reflects the new value/window.
