# CLIENT 04 - Cards Status Cycle

## Goal
Client reviews issued cards and manages their status through the mounted client-portal surface.

## Actors & Roles
- Client Owner
- Client Admin

## Prerequisites
- Core API running with `postgres`.

## UI Flow
**Client portal**
- Cards list -> card detail -> block card -> unblock card.

## API Flow
1. `GET /api/v1/client/cards` - list cards.
2. `GET /api/v1/client/cards/{card_id}` - card detail.
3. `POST /api/v1/client/cards/{card_id}/block` - block card.
4. `POST /api/v1/client/cards/{card_id}/unblock` - unblock card.

## DB Touchpoints
- `cards` - client-owned card registry and status.

## Events & Audit
- This client-portal surface updates card status directly on `cards`.

## Security / Gates
- Client auth required.

## Failure modes
- Card not found or not owned by client -> `404`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/test_client_portal_api.py`.
- smoke cmd: `scripts/smoke_cards_issue.cmd`.
- PASS: seeded issued card appears in list/detail, block/unblock succeed, and final status persists as `ACTIVE`.
