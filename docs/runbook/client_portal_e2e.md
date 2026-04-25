# Client Portal E2E Runbook (Windows CMD)

This runbook validates Client Portal bootstrap, access states, and onboarding scenarios using the SSoT endpoint `GET /api/core/portal/me`. Portal UI must only derive access state from SSoT fields: org, subscription, entitlements_snapshot, capabilities, and gating flags (features).【F:platform/processing-core/app/schemas/portal_me.py†L7-L78】

## Environment variables (CMD)
```cmd
set GATEWAY_BASE=http://localhost
set AUTH_BASE=http://localhost/api/auth
set CORE_BASE=%GATEWAY_BASE%/api/core
```

## AccessState mapping (SSoT → UI)
Use this table to confirm UI state and avoid generic error screens.

| Condition | SSoT signal | UI AccessState |
| --- | --- | --- |
| Missing/invalid token | 401/403 from `/portal/me` | AUTH_REQUIRED |
| Org missing or org.status != ACTIVE | `portal/me.org == null` or `org_status != ACTIVE` | NEEDS_ONBOARDING (reason `org_not_active`)【F:frontends/client-portal/src/access/accessState.ts†L61-L78】 |
| Subscription missing | `subscription.plan_code == null` | NEEDS_PLAN【F:frontends/client-portal/src/access/accessState.ts†L79-L84】 |
| Subscription overdue | `subscription.status` in `OVERDUE/PAST_DUE/DELINQUENT` | OVERDUE【F:frontends/client-portal/src/access/accessState.ts†L86-L92】 |
| Subscription suspended | `subscription.status` in `SUSPENDED/BLOCKED/PAUSED` | SUSPENDED【F:frontends/client-portal/src/access/accessState.ts†L86-L96】 |
| Role gate fails | Missing required role | FORBIDDEN_ROLE【F:frontends/client-portal/src/access/accessState.ts†L72-L96】 |
| Module disabled | `entitlements_snapshot.modules.<code>.enabled=false` | MODULE_DISABLED【F:frontends/client-portal/src/access/accessState.ts†L98-L116】 |
| Capability missing | `capabilities` missing | MISSING_CAPABILITY【F:frontends/client-portal/src/access/accessState.ts†L83-L117】 |
| Service unavailable | 502/503/network | SERVICE_UNAVAILABLE【F:frontends/client-portal/src/access/accessState.ts†L52-L54】 |
| Misconfig | dev-only (missing config) | MISCONFIG |
| Tech error | 5xx/parse crash | TECH_ERROR |

## Scenario A — New client (P1)
Goal: signup/login → `/portal/me` NEEDS_ONBOARDING → create org → select plan → generate contract → contract sign → verify `/portal/me` ACTIVE → cards/docs/users.

1) **Login** (obtain client token)
```cmd
curl -i %AUTH_BASE%/login -H "Content-Type: application/json" -d @client_login.json
```

2) **Bootstrap**
```cmd
curl -i %CORE_BASE%/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"
```
Expected: `NEEDS_ONBOARDING` when `org` null or status not ACTIVE.【F:frontends/client-portal/src/access/accessState.ts†L61-L78】

3) **Create org draft**
```cmd
curl -i -X POST %CORE_BASE%/client/org -H "Authorization: Bearer %CLIENT_TOKEN%" -d "{}"
```

4) **Select plan/modules**
```cmd
curl -i -X POST %CORE_BASE%/client/subscription/select -H "Authorization: Bearer %CLIENT_TOKEN%" -d "{\"plan_code\":\"BASIC\",\"modules\":[\"FLEET\"]}"
```

5) **Generate contract**
```cmd
curl -i -X POST %CORE_BASE%/client/contracts/generate -H "Authorization: Bearer %CLIENT_TOKEN%"
```

6) **Sign contract (OTP/ПЭП)**
```cmd
curl -i -X POST %CORE_BASE%/client/contracts/sign -H "Authorization: Bearer %CLIENT_TOKEN%" -d "{\"otp\":\"0000\"}"
```

7) **Verify activation via bootstrap**
```cmd
curl -i %CORE_BASE%/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"
```
Expected: `org.status=ACTIVE`, `subscription.status=ACTIVE`, and final client access in `/portal/me` response.【F:platform/processing-core/app/schemas/portal_me.py†L14-L43】

8) **Validate core features**
```cmd
curl -i %CORE_BASE%/v1/client/cards -H "Authorization: Bearer %CLIENT_TOKEN%"
curl -i %CORE_BASE%/client/documents -H "Authorization: Bearer %CLIENT_TOKEN%"
curl -i %CORE_BASE%/v1/client/users -H "Authorization: Bearer %CLIENT_TOKEN%"
```

Compatibility/internal note:
- `POST /client/onboarding/activate` still exists, but it is not the normal happy-path activation step for new consumers.
- Current authenticated onboarding activation is contract-sign driven; `onboarding/activate` is a guarded compatibility/internal route after the same minimum subscription + contract prerequisites already hold.

## Scenario B — Overdue (P2)
Goal: subscription OVERDUE → `/portal/me` OVERDUE → pay → ACTIVE.

1) Force overdue status in DB (admin action or seed).
2) Bootstrap:
```cmd
curl -i %CORE_BASE%/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"
```
Expected: `OVERDUE` based on subscription status mapping.【F:frontends/client-portal/src/access/accessState.ts†L86-L92】

3) Pay invoice (billing flow) and re-check:
```cmd
curl -i %CORE_BASE%/portal/me -H "Authorization: Bearer %CLIENT_TOKEN%"
```
Expected: `ACTIVE` state.

## Scenario C — Driver access (P2)
Goal: OWNER assigns DRIVER and grants access → driver sees only own cards/ops.

1) OWNER assigns role and grants CardAccess:
```cmd
curl -i -X PATCH %CORE_BASE%/v1/client/users/%DRIVER_ID%/roles -H "Authorization: Bearer %CLIENT_TOKEN%" -d "{\"roles\":[\"CLIENT_DRIVER\"]}"
curl -i -X POST %CORE_BASE%/v1/client/cards/%CARD_ID%/access -H "Authorization: Bearer %CLIENT_TOKEN%" -d "{\"user_id\":\"%DRIVER_ID%\",\"scope\":\"VIEW\"}"
```

2) DRIVER lists cards/operations:
```cmd
curl -i %CORE_BASE%/v1/client/cards -H "Authorization: Bearer %DRIVER_TOKEN%"
curl -i %CORE_BASE%/v1/client/operations -H "Authorization: Bearer %DRIVER_TOKEN%"
```
Expected: only cards/operations assigned by `assigned_driver_user_id` or CardAccess scope.

## Error payload expectations
- All errors should include `request_id` and `reason_code` for UI mapping.
- `SERVICE_UNAVAILABLE` is only for 502/503/network errors; business states use AccessState mappings above.
