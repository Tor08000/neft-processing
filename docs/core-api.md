# Core API reference additions

## New reference endpoints
- `GET /api/v1/merchants` – list merchants with pagination.
- `POST /api/v1/merchants`, `GET /api/v1/merchants/{merchant_id}`, `PATCH /api/v1/merchants/{merchant_id}`, `DELETE /api/v1/merchants/{merchant_id}`.
- `GET /api/v1/terminals` – list terminals with pagination.
- `POST /api/v1/terminals`, `GET /api/v1/terminals/{terminal_id}`, `PATCH /api/v1/terminals/{terminal_id}`, `DELETE /api/v1/terminals/{terminal_id}`.
- `GET /api/v1/cards` – list cards with pagination.
- `POST /api/v1/cards`, `GET /api/v1/cards/{card_id}`, `PATCH /api/v1/cards/{card_id}`.

All list endpoints accept `limit` and `offset` query parameters. Payloads and responses use the Pydantic schemas from `app.schemas.merchants`, `app.schemas.terminals`, and `app.schemas.cards`.

## Terminal auth validation
`POST /api/v1/processing/terminal-auth` now validates the reference data before running limits:
- Merchant must exist and be `ACTIVE`.
- Terminal must exist, belong to the merchant, and be `ACTIVE`.
- Card must exist, be `ACTIVE`, and its `client_id` must match the request.

Requests failing these checks return HTTP 400 with an explanatory `detail`.

## Default reference data
On application startup the service ensures the presence of default records used by automated tests:
- Merchant `M-001` (`ACTIVE`)
- Terminal `T-001` bound to merchant `M-001` (`ACTIVE`)
- Card `CARD-001` for `client_id` `CLIENT-123` (`ACTIVE`)

The bootstrap step recreates these entries if they are missing or inactive, so `run_tests.cmd` can execute without manual setup.
