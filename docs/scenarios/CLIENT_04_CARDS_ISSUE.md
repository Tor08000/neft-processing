# CLIENT 04 — Cards Issue

## Goal
Client issues fleet cards, manages status, and sees updates reflected in operations.

## Actors & Roles
- Client Owner / Fleet Manager
- Ops/Admin (optional)

## Prerequisites
- Core API running with `postgres`.

## UI Flow
**Client portal**
- Cards list → issue card → block/unblock card.

## API Flow
1. `GET /api/client/fleet/cards` — list cards.
2. `POST /api/client/fleet/cards` — issue card.
3. `POST /api/client/fleet/cards/{card_id}/block` — block card.
4. `POST /api/client/fleet/cards/{card_id}/unblock` — unblock card.

## DB Touchpoints
- `fuel_cards` — card registry.
- `fuel_card_status_events` — status transitions.

## Events & Audit
- `CARD_CREATED`, `CARD_STATUS_CHANGED` in `case_events`.

## Security / Gates
- Client permissions required (`client:fleet:*`).

## Failure modes
- Card not found or not owned by client → `404` / `403`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_fleet_v1.py`.
- smoke cmd: `scripts/smoke_cards_issue.cmd` (placeholder).
- PASS: card issued and status updates recorded.
