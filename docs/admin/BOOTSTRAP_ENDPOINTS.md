# Bootstrap endpoints

## Auth host (all portals)

| Action | Method | Endpoint |
| --- | --- | --- |
| Login | POST | `/api/v1/auth/login` |
| Me | GET | `/api/v1/auth/me` |
| Register | POST | `/api/v1/auth/register` |

## Core API

| Portal | Method | Endpoint |
| --- | --- | --- |
| Client/Partner portal bootstrap | GET | `/api/core/portal/me` |
| Admin bootstrap | GET | `/api/core/v1/admin/me` |

## Error handling expectations

- `401` → Unauthorized page.
- `403` → Forbidden page.
- `404` or invalid JSON → Tech error page with `request_id`.
