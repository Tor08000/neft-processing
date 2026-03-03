# Client portal cross-service contract (client-portal ↔ gateway ↔ auth-host ↔ core-api ↔ document-service)

## Base paths

- `client-portal` auth base: `VITE_AUTH_API_BASE=/api/v1/auth`.
- `client-portal` core base: `VITE_CORE_API_BASE=/api/core`.
- Canonical onboarding profile endpoint: `POST /api/core/client/onboarding/profile`.

## Gateway routing contract

- `/api/v1/auth/*` proxies to `auth-host` **without** prefix rewrite.
- `/api/auth/*` is legacy alias rewritten to `/api/v1/auth/*`.
- `/api/core/*` proxies to `core-api`.
- Gateway forwards `Authorization` header via `proxy_set_header Authorization $http_authorization;`.

## Auth/JWT contract

- Client portal expects client token issuer `iss=neft-auth` (configurable by `VITE_CLIENT_TOKEN_ISSUER`).
- Client portal tokens must be client audience (`aud=neft-client`) to pass core onboarding auth guard.
- On any onboarding `401`, UI must show reauth message and redirect to `/client/login?reauth=1` once.

## Required headers

- `Authorization: Bearer <JWT>` for protected `client-portal -> core-api` routes.
- `X-Request-ID` is propagated by gateway and used for diagnostics/correlation.

## Document-service/health

- `document-service` healthcheck uses Python stdlib (`urllib.request`) against `http://127.0.0.1:8000/health`.
- Healthcheck does not require `curl` or `wget`, preventing false unhealthy status due to missing binaries.

## Stability notes

- `/api/v1/auth/me` and session status endpoints should be polled by frontend logic with stop conditions (no infinite retries after auth failures).
- Avoid mixed base paths like `/api/auth` + `/api/v1/auth` in the same frontend flow to prevent redirect/rewrite surprises.
