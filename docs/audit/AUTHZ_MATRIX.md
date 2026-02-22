# NEFT AuthZ Matrix (Gateway × API × UI)

## Roles/claims baseline

| Token type | Expected audience | Typical roles |
|---|---|---|
| admin token | `neft-admin` | `ADMIN`, `PLATFORM_ADMIN`, `SUPERADMIN` |
| client token | `neft-client` | `CLIENT_OWNER` (+ client roles) |
| partner token | `neft-partner` | `PARTNER_OWNER` (+ partner roles) |

## Access matrix (core contract)

| Namespace | Gateway auth_request | No token | Wrong token type | Valid token |
|---|---|---:|---:|---:|
| `/api/core/v1/admin/*` | `/_internal/admin_auth_verify` | 401 | 403/401 | 200 |
| `/api/core/client/*` | `/_internal/client_auth_verify` | 401 | 403/401 | 200 |
| `/api/core/partner/*` | `/_internal/partner_auth_verify` | 401 | 403/401 | 200 |
| `/api/core/v1/client/*` (deprecated) | `/_internal/client_auth_verify` | 401 | 403/401 | 200 + `X-API-Deprecated: true` |
| `/api/core/v1/partner/*` (deprecated) | `/_internal/partner_auth_verify` | 401 | 403/401 | 200 + `X-API-Deprecated: true` |

## UI gating expectations

| Frontend module | API namespace | UI hide reason (allowed) | UI hide reason (not allowed) |
|---|---|---|---|
| admin-web | `/api/core/v1/admin/*` | 403 (role/entitlement) | 404 due to wrong prefix |
| client-web | `/api/core/client/*` | 403 (role/entitlement) | 404 due to legacy `/v1/client` path |
| partner-web | `/api/core/partner/*` | 403 (role/entitlement) | 404 due to legacy `/v1/partner` path |

## Verify endpoints integrity checklist

- `/api/core/admin/auth/verify` exists and returns 401 without token.
- `/api/core/client/auth/verify` exists and returns 401 without token.
- `/api/core/partner/auth/verify` exists and returns 401 without token.
- Authorization header is forwarded from gateway to upstream during verify/protected calls.

## Operational invariants

1. Auth-host continues serving canonical auth under `/api/v1/auth/*`.
2. Gateway rewrites `/api/auth/*` to `/api/v1/auth/*` only as compatibility path.
3. Request correlation key (`X-Request-ID`) propagates gateway → upstream and back in logs.
