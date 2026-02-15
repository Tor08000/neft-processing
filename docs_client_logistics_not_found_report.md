# P0 report: Client Portal logistics 404 (`fleet` / `trips` / `fuel`)

## 1) Inventory of actual routes

### Core API (`platform/processing-core`)

| Layer | Route prefix / endpoints |
|---|---|
| `app/api/v1/endpoints/logistics.py` | `/api/v1/logistics/*` (orders, routes, fuel endpoints, `trips/{trip_id}/fuel`) |
| `app/routers/client_fleet.py` | `/api/client/fleet/*` (fleet cards/groups/employees/etc, not logistics trips/fuel pages from portal) |
| `app/routers/client_portal_v1.py` | does **not** define `/client/logistics/*` |
| `app/main.py` includes | includes `logistics_router` with no extra prefix and includes `client_portal_v1_router` under `/api/core` |

### Logistics service (`platform/logistics-service`)

| File | Existing routes |
|---|---|
| `neft_logistics_service/main.py` | `/health`, `/metrics`, `/v1/eta`, `/v1/deviation`, `/v1/explain` |
| `routers/*` | no additional routers present |

### Gateway (`gateway/default.conf` is copied in Docker image)

| Incoming path | Upstream behavior |
|---|---|
| `/api/core/client/*` | `proxy_pass http://core_api;` (auth_request enabled) |
| `/api/core/*` | `proxy_pass http://core_api;` |
| `/api/logistics/*` | `proxy_pass http://logistics_service/;` (prefix stripped) |
| `/api/v1/*` | `proxy_pass http://core_api;` |

## 2) Route mismatch that caused 404 in portal

Client portal logistics API used paths under `/api/v1/logistics/...` (via frontend relative `/v1/logistics/...`), while feature pages expect domain entities (`fleet`, `trips`, `fuel`) in portal namespace. Missing portal-facing endpoints led to 404 on key screens.

### Concrete problematic URLs from frontend code

- `/api/v1/logistics/vehicles`
- `/api/v1/logistics/drivers`
- `/api/v1/logistics/trips`
- `/api/v1/logistics/trips/{trip_id}`
- `/api/v1/logistics/trips/{trip_id}/route`
- `/api/v1/logistics/trips/{trip_id}/tracking`
- `/api/v1/logistics/trips/{trip_id}/position`
- `/api/v1/logistics/trips/{trip_id}/eta`
- `/api/v1/logistics/trips/{trip_id}/deviations`
- `/api/v1/logistics/trips/{trip_id}/sla-impact`
- `/api/v1/logistics/trips/{trip_id}/fuel`
- `/api/v1/logistics/fuel/linker:run`
- `/api/v1/logistics/fuel/unlinked`
- `/api/v1/logistics/fuel/alerts`
- `/api/v1/logistics/reports/fuel`

## 3) Canonical flow after fix

`client-portal` now calls only `/api/core/client/logistics/*` through gateway, and core-api exposes matching client endpoints (MVP read-only / empty list behavior for collection endpoints).

| Front expects | Gateway proxies | Backend has |
|---|---|---|
| `/api/core/client/logistics/fleet` | `/api/core/client/* -> core_api` | `GET /client/logistics/fleet` returns `{items:[],...}` |
| `/api/core/client/logistics/trips` | `/api/core/client/* -> core_api` | `GET /client/logistics/trips` returns `{items:[],...}` |
| `/api/core/client/logistics/fuel` | `/api/core/client/* -> core_api` | `GET /client/logistics/fuel` returns `{items:[],...}` |

## 4) Added regression smoke

Script: `scripts/smoke_client_logistics.cmd`

Checks through gateway:

- `GET /api/core/client/logistics/fleet` -> 200
- `GET /api/core/client/logistics/trips` -> 200
- `GET /api/core/client/logistics/fuel` -> 200

