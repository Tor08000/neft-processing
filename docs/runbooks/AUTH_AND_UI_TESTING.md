# Auth & UI Testing Runbook (Gateway + UI)

## 1) Проверка auth через gateway (curl)

Перед запуском убедитесь, что заданы обязательные креды демо-пользователей:

```
NEFT_BOOTSTRAP_ADMIN_EMAIL
NEFT_BOOTSTRAP_ADMIN_PASSWORD
NEFT_BOOTSTRAP_CLIENT_EMAIL
NEFT_BOOTSTRAP_CLIENT_PASSWORD
NEFT_BOOTSTRAP_PARTNER_EMAIL
NEFT_BOOTSTRAP_PARTNER_PASSWORD
```

Также для авто-сидинга:

```
NEFT_BOOTSTRAP_ENABLED=1
DEMO_SEED_FORCE_PASSWORD_RESET=1
NEFT_BOOTSTRAP_PASSWORD_VERSION=1
```

Ключи RSA `auth-host` хранятся в volume `auth-keys` (`/data/keys`). Чтобы пересоздать ключи: `docker compose down -v`. Чтобы сохранить ключи между рестартами: `docker compose down` без `-v`.

### Admin login

```bash
curl -s -X POST "http://localhost/api/auth/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${NEFT_BOOTSTRAP_ADMIN_EMAIL}\",\"password\":\"${NEFT_BOOTSTRAP_ADMIN_PASSWORD}\"}"
```

### Client login

```bash
curl -s -X POST "http://localhost/api/auth/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${NEFT_BOOTSTRAP_CLIENT_EMAIL}\",\"password\":\"${NEFT_BOOTSTRAP_CLIENT_PASSWORD}\"}"
```

### Partner login

```bash
curl -s -X POST "http://localhost/api/auth/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${NEFT_BOOTSTRAP_PARTNER_EMAIL}\",\"password\":\"${NEFT_BOOTSTRAP_PARTNER_PASSWORD}\"}"
```

Ожидаемый результат: стабильные успешные ответы 10/10 раз (без 502 от gateway).
Типичный успешный ответ содержит `access_token` и `token_type`:

```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```

### Быстрый smoke auth-host

```bash
scripts/smoke_auth_host.sh
```

Windows CMD:

```bat
scripts\smoke_auth_host.cmd
```

Скрипт проверяет `/api/auth/health`, логины admin/client/partner и `/api/auth/v1/auth/public-key`. Возвращает `0` при успехе.

## 2) UI Snapshot (ui_snapshot.cmd)

```bat
frontends\scripts\ui_snapshot.cmd
```

Ожидаемая строка в stdout:

```
UI audit saved to: ui-audit/<RUN_ID>
```

Выходные файлы:

- `frontends/ui-audit/<RUN_ID>/REPORT.md`
- Скриншоты: `frontends/ui-audit/<RUN_ID>/<app>/*.png`

## 3) UI Link Crawl (ui_link_crawl.spec.ts)

```bat
frontends\scripts\ui_link_crawl.cmd
```

Выходные файлы:

- `frontends/ui-audit/<RUN_ID>/LINK_REPORT.md`
- Скриншоты: `frontends/ui-audit/<RUN_ID>/crawl/<app>/*.png`

Путь к `LINK_REPORT.md` также выводится в stdout:

```
LINK_REPORT: <path>
```

## 4) Где искать ошибки

- `REPORT.md` / `LINK_REPORT.md` содержит статус по маршрутам и ссылки на скриншоты.
- Скриншоты с ошибками именуются с префиксом `FAIL_...`.
