# CLIENT PORTAL CONTRACT (dev)

## Base URLs
- Auth API base: `/api/v1/auth`
- Core API base: `/api/core`
- Client portal UI: `/client/*`

## Endpoints (client flow)
1. `POST /api/v1/auth/login` → returns access/refresh tokens.
2. `GET /api/v1/auth/me` → must be called exactly once after login success before setting authenticated UI state.
3. `GET /api/core/portal/me` → canonical profile/access-state endpoint for client routing.
4. `POST /api/core/client/onboarding/profile` → onboarding step 1 payload (strict, `extra=forbid`).
5. Optional legal gate (outside onboarding route):
   - `GET /api/core/legal/required`
   - `GET /api/core/legal/documents/{code}`
   - `POST /api/core/legal/accept`

## Onboarding profile payload (`POST /api/core/client/onboarding/profile`)
```json
{
  "org_type": "LEGAL",
  "name": "ООО Нефть",
  "inn": "1234567890",
  "kpp": "123456789",
  "ogrn": "1234567890123",
  "address": "Москва"
}
```

Validation notes:
- Unknown fields are rejected with 422 (FastAPI/Pydantic validation detail).
- Frontend maps `detail[].loc` to form fields (`name`, `inn`, `kpp`, `ogrn`, `address`).

## JWT alignment (auth-host ↔ core-api ↔ frontend)
- Issuer for client tokens: `neft-auth`
- Audience for client portal tokens: `neft-client`
- Portal claim for client flow: `portal=client`

Core API validates client endpoints with client issuer/audience and portal-kind checks.
Admin tokens (`aud=neft-admin`) must be rejected on client endpoints.

## Reauth rules
- Any `401` on `GET /api/v1/auth/me`:
  1. clear tokens (`access`, `refresh`, `expiresAt`)
  2. set `reauth_required`
  3. single redirect to `/client/login?reauth=1`
- No automatic login retry loops.
- Retry is disabled for:
  - `/api/v1/auth/*`
  - `/api/core/client/onboarding/*`

## Dev auth debug logs
Before Authorization attach:
- `attach_bearer token_length=<N> token_prefix=<first_12>`
- or `skip_bearer reason=missing|invalid_format|expired`

Auth flow logs:
- `[AUTH] login success, calling /me`
- `[AUTH] auth_me_401 -> reauth`
