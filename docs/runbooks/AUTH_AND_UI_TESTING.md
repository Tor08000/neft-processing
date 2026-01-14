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

### Быстрая проверка (должно вернуть 200)

```bash
curl -i -X POST http://localhost/api/auth/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"admin@example.com\",\"password\":\"admin\"}"
```

### Admin login

```bash
curl -s -X POST "http://localhost/api/auth/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${NEFT_BOOTSTRAP_ADMIN_EMAIL}\",\"password\":\"${NEFT_BOOTSTRAP_ADMIN_PASSWORD}\"}"
```

### Client login

```bash
curl -s -X POST "http://localhost/api/auth/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${NEFT_BOOTSTRAP_CLIENT_EMAIL}\",\"password\":\"${NEFT_BOOTSTRAP_CLIENT_PASSWORD}\"}"
```

### Partner login

```bash
curl -s -X POST "http://localhost/api/auth/v1/auth/login" \
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
cd frontends
npm install
scripts\ui_snapshot.cmd
```

Ожидаемая строка в stdout:

```
UI audit saved to: ui-audit/<RUN_ID>
```

Выходные файлы:

- `frontends/ui-audit/<RUN_ID>/REPORT.md`
- Скриншоты: `frontends/ui-audit/<RUN_ID>/<app>/*.png`

Эталонный запуск из `frontends`:

```bat
npm run ui:snapshot
```

## 2.1) Smoke: gateway UI assets + SPA fallback (curl)

Проверьте, что SPA корни и ассеты отвечают корректно:

```bash
curl -I http://localhost/admin/
curl -I http://localhost/admin/assets/
curl -I http://localhost/client/
curl -I http://localhost/client/assets/
curl -I http://localhost/partner/
curl -I http://localhost/partner/assets/
```

Проверьте, что JS/CSS ассеты не возвращают HTML:

```bash
curl -I http://localhost/admin/assets/index-*.js
curl -I http://localhost/admin/assets/index-*.css
curl -I http://localhost/client/assets/index-*.js
curl -I http://localhost/client/assets/index-*.css
curl -I http://localhost/partner/assets/index-*.js
curl -I http://localhost/partner/assets/index-*.css
```

Ожидания:

- HTTP 200.
- `Content-Type: application/javascript` (или `text/javascript`) для JS.
- `Content-Type: text/css` для CSS.

### Обязательные smoke-команды (Windows CMD)

Извлекаем реальное имя ассета и проверяем Content-Type (без wildcard `*`):

```bat
curl -I http://localhost/admin/ | findstr /I "200"
curl -s http://localhost/admin/ | findstr /I "assets/index-"
```

Возьмите реальное имя `index-XXXX.js`/`index-XXXX.css` из HTML и проверьте:

```bat
curl -I http://localhost/admin/assets/index-XXXX.js | findstr /I "Content-Type"
curl -I http://localhost/admin/assets/index-XXXX.css | findstr /I "Content-Type"
```

Повторите для client/partner:

```bat
curl -I http://localhost/client/ | findstr /I "200"
curl -s http://localhost/client/ | findstr /I "assets/index-"
curl -I http://localhost/client/assets/index-XXXX.js | findstr /I "Content-Type"
curl -I http://localhost/client/assets/index-XXXX.css | findstr /I "Content-Type"

curl -I http://localhost/partner/ | findstr /I "200"
curl -s http://localhost/partner/ | findstr /I "assets/index-"
curl -I http://localhost/partner/assets/index-XXXX.js | findstr /I "Content-Type"
curl -I http://localhost/partner/assets/index-XXXX.css | findstr /I "Content-Type"
```

Проверка на 404 (ассет не должен отдавать HTML):

```bat
curl -i http://localhost/admin/assets/THIS_SHOULD_404.css | findstr /I "HTTP/ Content-Type"
curl -i http://localhost/client/assets/THIS_SHOULD_404.css | findstr /I "HTTP/ Content-Type"
curl -i http://localhost/partner/assets/THIS_SHOULD_404.css | findstr /I "HTTP/ Content-Type"
```

Быстрый скрипт (вытащит реальные имена ассетов и проверит Content-Type):

```bat
scripts\ui_smoke_assets.cmd
```

Скрипт также проверяет auth login POST:

```bat
curl -i -X POST http://localhost/api/auth/v1/auth/login -H "Content-Type: application/json" -d "{\"email\":\"admin@example.com\",\"password\":\"admin\"}"
```

## 2.2) Проверка что HTML не подменяет ассеты

Вытащите реальные имена ассетов из HTML:

```bat
curl -s http://localhost/admin/ | findstr /i "assets/index-"
curl -s http://localhost/client/ | findstr /i "assets/index-"
curl -s http://localhost/partner/ | findstr /i "assets/index-"
```

Проверьте реальные файлы (подставьте имена из предыдущего шага):

```bash
curl -I http://localhost/admin/assets/index-XXXX.js
curl -I http://localhost/admin/assets/index-XXXX.css
curl -I http://localhost/client/assets/index-XXXX.js
curl -I http://localhost/client/assets/index-XXXX.css
curl -I http://localhost/partner/assets/index-XXXX.js
curl -I http://localhost/partner/assets/index-XXXX.css
```

Ожидания:

- HTTP 200.
- `Content-Type` не `text/html`.

## 2.3) Проверка login JSON

```bash
curl -i -X POST http://localhost/api/auth/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"admin@example.com\",\"password\":\"admin\"}"
```

Ожидание:

- HTTP/1.1 200
- Content-Type: application/json

## 2.4) Обязательные smoke-проверки

```bash
curl -I http://localhost/admin/assets/index-XXXX.js
curl -I http://localhost/client/assets/index-XXXX.css
```

Ожидания:

- JS отдаёт `Content-Type: application/javascript`.
- CSS отдаёт `Content-Type: text/css`.

```bash
curl -i -X POST http://localhost/api/auth/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"admin@example.com\",\"password\":\"admin\"}"
```

Ожидание:

- HTTP 200.

## 3) UI Link Crawl (ui_link_crawl.spec.ts)

```bat
cd frontends
npm install
scripts\ui_link_crawl.cmd
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
