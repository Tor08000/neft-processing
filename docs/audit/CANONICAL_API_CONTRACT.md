# NEFT Canonical API Contract (Final)

## 1) Canonical namespaces

| Domain | Canonical prefix | Enforcement point |
|---|---|---|
| Core Admin API | `/api/core/v1/admin/*` | Gateway `auth_request /_internal/admin_auth_verify` |
| Core Client API | `/api/core/client/*` | Gateway `auth_request /_internal/client_auth_verify` |
| Core Partner API | `/api/core/partner/*` | Gateway `auth_request /_internal/partner_auth_verify` |
| Auth API | `/api/v1/auth/*` | Gateway direct proxy to `auth-host` |

## 2) Legacy/deprecated aliases

| Legacy prefix | Current behavior | Security notes |
|---|---|---|
| `/api/core/v1/client/*` | Rewritten to `/api/core/client/*`, header `X-API-Deprecated: true` | Still protected with `client_auth_verify` |
| `/api/core/v1/partner/*` | Rewritten to `/api/core/partner/*`, header `X-API-Deprecated: true` | Still protected with `partner_auth_verify` |
| `/api/auth/*` | Rewritten to `/api/v1/auth/*` | No auth bypass in gateway, routed to auth-host |

## 2.1) Non-supported legacy patterns (must not appear)

The following patterns are NOT part of the supported compatibility surface and must not appear in code or docs:

- `/api/core/{client|partner}/v1/*` (non-supported form)

If such prefixes appear, they should be treated as bugs and removed/normalized to canonical namespaces.

## 3) Auth verify contract (gateway internal)

Gateway internal checks:
- `/_internal/admin_auth_verify -> /api/core/admin/auth/verify`
- `/_internal/client_auth_verify -> /api/core/client/auth/verify`
- `/_internal/partner_auth_verify -> /api/core/partner/auth/verify`

External observable verify paths (must exist):
- `/api/core/admin/auth/verify`
- `/api/core/client/auth/verify`
- `/api/core/partner/auth/verify`

Expected statuses:
- no token: `401`
- valid token with matching audience/role: `200`
- invalid token or wrong audience: `401/403`

## 4) Versioning policy

1. `admin` stays on explicit `v1` namespace (`/api/core/v1/admin/*`).
2. `client` and `partner` are canonical without `/v1/` in path (`/api/core/client/*`, `/api/core/partner/*`).
3. Deprecated aliases are kept only as compatibility bridge and must return `X-API-Deprecated: true`.
4. New functional versions should be introduced via additive prefixes (`/api/core/v2/...`) and routed explicitly in gateway.

## 5) Frontend API contract constraints

1. `client-web` and `partner-web` must not call `/api/core/v1/client` or `/api/core/v1/partner` directly.
2. Shared frontend base builders must normalize auth route to `/api/v1/auth`.
3. Admin frontend may keep `/api/core/v1/admin` as canonical admin namespace.

## 6) Service-level routed prefixes (through gateway)

- `/api/ai/* -> ai-service`
- `/api/v1/crm/*` and `/api/crm/* -> crm-service`
- `/api/logistics/* -> logistics-service`
- `/api/docs/* -> document-service`
- `/api/int/*` and `/api/integrations/* -> integration-hub`

## 7) Contract invariants (must-pass)

1. Protected business namespaces are never reachable without auth (no accidental `404` replacing `401/403`).
2. Deprecated aliases never bypass `auth_request` and always emit deprecation header.
3. Verify endpoints exist and are callable by gateway internals.
4. Gateway config twins `gateway/nginx.conf` and `gateway/default.conf` remain aligned on routing rules.
