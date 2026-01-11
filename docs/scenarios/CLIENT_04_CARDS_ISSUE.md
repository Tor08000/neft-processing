# CLIENT 04 — Cards Issue

## Goal
Client admins issue cards, manage card status, and update card limits.

## Actors & Roles
- Client Owner / Client Admin
- Regular User (view-only)

## Prerequisites
- Processing-core API.
- Fleet module enabled for the client.

## UI Flow
**Client portal**
- Cards list → issue card → block/unblock card.

## API Flow
1. `GET /api/client/fleet/cards` — list cards.
2. `POST /api/client/fleet/cards` — issue card.
3. `POST /api/client/fleet/cards/{card_id}/block` — freeze card.
4. `POST /api/client/fleet/cards/{card_id}/unblock` — unfreeze card.

**NOT IMPLEMENTED**
- Per-card limit update endpoint (limits are managed via `/limits/set` for scopes).

## DB Touchpoints
- `fuel_cards` — card records.
- `fuel_card_status_events` — card status history (immutable).
- `case_events` — fleet event stream for card actions.

## Events & Audit
- `CARD_CREATED` — emitted when card is issued.
- `CARD_STATUS_CHANGED` — emitted on block.
- `FUEL_CARD_UNBLOCKED` — emitted on unblock.

## Security / Gates
- Requires `client:fleet:cards:manage` permission for create/block/unblock.

## Failure modes
- Unauthorized user → `403 forbidden`.
- Invalid card id → `404 card_not_found`.

## VERIFIED
- pytest: **NOT IMPLEMENTED** (card issuance tests not isolated).
- smoke cmd: `scripts/smoke_cards_issue.cmd` (fails with NOT IMPLEMENTED).
- PASS: card issued, status changes visible in list and events.
