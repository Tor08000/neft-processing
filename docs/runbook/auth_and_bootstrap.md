# Auth + Portal Bootstrap Runbook (Windows CMD)

Цель: подтвердить в docker compose, что auth выдаёт токены для client/partner/admin, core-api принимает токены, seed idempotent, а portal bootstrap отвечает корректно.

## Canonical login path

**Canonical gateway URLs (use these in smoke):**

* Login: `POST http://localhost/api/v1/auth/login`
* JWKS: `GET http://localhost/api/v1/auth/.well-known/jwks.json`
* Portal bootstrap: `GET http://localhost/api/core/portal/me`

**Portal is required. Official option:** send it in the JSON body.

Fallbacks (if body omitted) are supported in this order:

1. Header: `X-Portal: client|partner|admin`
2. Query param: `?portal=client|partner|admin`

If no portal is resolved, auth-host returns `400` with:

```
{"detail":{"error":"portal_required","reason_code":"PORTAL_REQUIRED"}}
```

## JWT claims & environment rules

* `iss`/`aud` are selected by portal (`client` uses client issuer/audience; `admin/partner` use admin issuer/audience).
* `user_id` is always included when available.
* `client_id` and `org_id` are **only auto-injected in dev/local** (`NEFT_ENV=local|dev|development|test`).
* `org_id` is an integer (matches `orgs.id` in core) for dev seed flows.

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

## Runbook order (mandatory)

1) docker compose up
2) login (get tokens)
3) seed core (twice)
4) portal bootstrap checks
5) logs review

## Smoke commands (Windows CMD)

> Все команды ниже — для **Windows CMD** (не PowerShell). Используйте `^` для переноса строк.

### 1) Поднять систему

```
cd C:\neft-processing
docker compose down -v
docker compose up -d --build
docker compose ps
```

### 2) Проверить auth живой

```
curl -i http://localhost/api/v1/auth/health
curl -i http://localhost/api/v1/auth/.well-known/jwks.json
```

### 3) Tokens (client/partner/admin)

```
curl -s -X POST http://localhost/api/v1/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"client@neft.local\",\"password\":\"client\",\"portal\":\"client\"}"

curl -s -X POST http://localhost/api/v1/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"partner@neft.local\",\"password\":\"partner\",\"portal\":\"partner\"}"

curl -s -X POST http://localhost/api/v1/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"admin@neft.local\",\"password\":\"admin\",\"portal\":\"admin\"}"
```

DoD: ответы не `404`, и в JSON есть `access_token`. Если используются другие demo креды — зафиксировать их в этом runbook.

### 4) Seed core (idempotent)

```
docker compose exec -T core-api python scripts/dev_seed_core.py
docker compose exec -T core-api python scripts/dev_seed_core.py
```

DoD: второй запуск не падает, вывод показывает idempotent поведение.

### 5) Portal bootstrap

Подставьте `<CLIENT_TOKEN>` из шага 3.

```
curl -i http://localhost/api/core/portal/me -H "Authorization: Bearer <CLIENT_TOKEN>"
curl -i http://localhost/api/core/portal/me -H "Authorization: Bearer <PARTNER_TOKEN>"
curl -i http://localhost/api/core/portal/me -H "Authorization: Bearer <ADMIN_TOKEN>"
```

### 6) Notifications unread count (client)

```
curl -i http://localhost/api/core/client/notifications/unread-count -H "Authorization: Bearer <CLIENT_TOKEN>"
```

DoD:

* client `portal/me` → `200`.
* client `unread-count` → `200`.
* partner/admin `portal/me` → `200` **или** ожидаемый бизнес-статус (например, `MODULE_DISABLED` / `SUBSCRIPTION_REQUIRED`), но не `500` и не `token_rejected`.

### 7) Проверка логов

```
docker compose logs --tail=200 auth-host
docker compose logs --tail=200 core-api
docker compose logs --tail=200 gateway
```

DoD по логам:

* нет циклического `token_rejected` при валидных токенах;
* нет `500` на `portal/me` после seed (если есть, должен быть `reason_code` + `error_id`).

## Important: NEFT_SKIP_DB_BOOTSTRAP

`NEFT_SKIP_DB_BOOTSTRAP` допустима **только** для unit-tests/CI. В `docker-compose`/prod профилях эту переменную использовать нельзя — иначе core может стартовать без DB инвариантов. Убедитесь, что она не задана в compose-файлах.
