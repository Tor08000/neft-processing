# Auth + Portal Bootstrap Runbook

## Canonical login path

* Login endpoint: `POST /api/v1/auth/login` (gateway `/api/auth/v1/auth/login`).
* **Portal is required**. It can be provided in one of the following ways (in this order):
  1. Request body: `{"portal": "client|partner|admin"}`
  2. Header: `X-Portal: client|partner|admin`
  3. Query param: `?portal=client|partner|admin`

If no portal is resolved, auth-host returns `400` with:

```
{"detail":{"error":"portal_required","reason_code":"PORTAL_REQUIRED"}}
```

## JWT claims & environment rules

* `iss`/`aud` are selected by portal (`client` uses client issuer/audience; `admin/partner` use admin issuer/audience).
* `user_id` is always included when available.
* `client_id` and `org_id` are **only auto-injected in dev/local** (`NEFT_ENV=local|dev|development|test`).

## Dev seed (core)

Idempotent demo seed for portal bootstrap:

```
docker compose exec -T core-api python scripts/dev_seed_core.py
docker compose exec -T core-api python scripts/dev_seed_core.py  # repeat run
```

Controlled via env (defaults shown):

```
NEFT_DEMO_ORG_ID=1
NEFT_DEMO_CLIENT_UUID=00000000-0000-0000-0000-000000000001
NEFT_DEMO_CLIENT_EMAIL=client@neft.local
NEFT_DEMO_ORG_NAME=demo-client
NEFT_DEMO_PLAN_CODE=DEMO
NEFT_DEMO_PLAN_TITLE=Demo
```

## Smoke commands

### Tokens

```
curl -s -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"client@neft.local","password":"client","portal":"client"}'

curl -s -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"partner@neft.local","password":"partner","portal":"partner"}'

curl -s -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@neft.local","password":"admin","portal":"admin"}'
```

### Portal bootstrap

```
curl -i http://localhost/api/core/portal/me -H "Authorization: Bearer <CLIENT_TOKEN>"
curl -i http://localhost/api/core/portal/me -H "Authorization: Bearer <PARTNER_TOKEN>"
curl -i http://localhost/api/core/portal/me -H "Authorization: Bearer <ADMIN_TOKEN>"
```

### Notifications unread count

```
curl -i http://localhost/api/core/client/notifications/unread-count -H "Authorization: Bearer <CLIENT_TOKEN>"
```
