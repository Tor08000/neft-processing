# Partner Money E2E — инварианты

## Инвариант Partner Money

- partner token всегда содержит org context.
- seed всегда возвращает org id.
- smoke никогда не продолжает после seed FAIL.
- payout невозможен без audit trail.

## Manual verification

### Реальные URL-ы (локально)

- CORE_API_BASE: `http://localhost/api/core` (все core пути идут от него).
- Seed партнёра: `POST http://localhost/api/core/v1/admin/seed/partner-money`
- Partner auth verify: `GET http://localhost/api/core/partner/auth/verify`
- Partner portal me: `GET http://localhost/api/core/portal/me`
- Admin payout queue: `GET http://localhost/api/core/v1/admin/finance/payouts`
- Admin payout approve: `POST http://localhost/api/core/v1/admin/finance/payouts/<id>/approve`
- Admin audit: `GET http://localhost/api/core/v1/admin/audit?correlation_id=<cid>`

### Нормальные статусы

- 200/201 для seed и admin-путей.
- 204 для `partner/auth/verify`.
- 200 для `portal/me` и partner endpoints.

### Блокеры

- 401 (token/issuer/audience mismatch).
- 404 (неверный base URL или путь).
- 500 (ошибка сервиса/миграций).

### Manual verify (Windows CMD)

```cmd
set "BASE_URL=http://localhost"
set "AUTH_URL=%BASE_URL%/api/v1/auth"
set "CORE_BASE=%BASE_URL%/api/core"
set "CORE_ADMIN=%CORE_BASE%/v1/admin"
set "CORE_PARTNER=%CORE_BASE%/partner"
set "CORE_PORTAL=%CORE_BASE%/portal"

curl -s -o "%TEMP%\admin_login.json" -w "%%{http_code}" -X POST "%AUTH_URL%/login" ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"admin@example.com\",\"password\":\"admin\",\"portal\":\"admin\"}"
for /f "usebackq delims=" %%T in (`python -c "import json; print(json.load(open(r'%TEMP%\\admin_login.json')).get('access_token',''))"`) do set "ADMIN_TOKEN=%%T"

curl -s -o "%TEMP%\seed_partner.json" -w "%%{http_code}" -X POST "%CORE_ADMIN%/seed/partner-money" ^
  -H "Authorization: Bearer %ADMIN_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"partner@neft.local\",\"org_name\":\"demo-partner\",\"inn\":\"7700000000\"}"

curl -s -o "%TEMP%\partner_login.json" -w "%%{http_code}" -X POST "%AUTH_URL%/login" ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"partner@neft.local\",\"password\":\"partner\",\"portal\":\"partner\"}"
for /f "usebackq delims=" %%T in (`python -c "import json; print(json.load(open(r'%TEMP%\\partner_login.json')).get('access_token',''))"`) do set "PARTNER_TOKEN=%%T"

curl -s -o "%TEMP%\partner_verify.json" -w "%%{http_code}" -X GET "%CORE_PARTNER%/auth/verify" ^
  -H "Authorization: Bearer %PARTNER_TOKEN%"
curl -s -o "%TEMP%\portal_me.json" -w "%%{http_code}" -X GET "%CORE_PORTAL%/me" ^
  -H "Authorization: Bearer %PARTNER_TOKEN%"

curl -s -o "%TEMP%\partner_dashboard.json" -w "%%{http_code}" -X GET "%CORE_PARTNER%/dashboard" ^
  -H "Authorization: Bearer %PARTNER_TOKEN%"
curl -s -o "%TEMP%\partner_ledger.json" -w "%%{http_code}" -X GET "%CORE_PARTNER%/ledger?limit=5" ^
  -H "Authorization: Bearer %PARTNER_TOKEN%"

curl -s -o "%TEMP%\payout_request.json" -w "%%{http_code}" -X POST "%CORE_PARTNER%/payouts/request" ^
  -H "Authorization: Bearer %PARTNER_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"amount\":1000,\"currency\":\"RUB\"}"
for /f "usebackq delims=" %%T in (`python -c "import json; data=json.load(open(r'%TEMP%\\payout_request.json')); print(data.get('payout_request_id') or data.get('id') or '')"`) do set "PAYOUT_ID=%%T"
for /f "usebackq delims=" %%T in (`python -c "import json; print(json.load(open(r'%TEMP%\\payout_request.json')).get('correlation_id',''))"`) do set "CORRELATION_ID=%%T"

curl -s -o "%TEMP%\admin_payouts.json" -w "%%{http_code}" -X GET "%CORE_ADMIN%/finance/payouts" ^
  -H "Authorization: Bearer %ADMIN_TOKEN%"
curl -s -o "%TEMP%\admin_payout_approve.json" -w "%%{http_code}" -X POST "%CORE_ADMIN%/finance/payouts/%PAYOUT_ID%/approve" ^
  -H "Authorization: Bearer %ADMIN_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"reason\":\"Manual verify\",\"correlation_id\":\"%CORRELATION_ID%\"}"

curl -s -o "%TEMP%\partner_payout_detail.json" -w "%%{http_code}" -X GET "%CORE_PARTNER%/payouts/%PAYOUT_ID%" ^
  -H "Authorization: Bearer %PARTNER_TOKEN%"

curl -s -o "%TEMP%\admin_audit.json" -w "%%{http_code}" -X GET "%CORE_ADMIN%/audit?correlation_id=%CORRELATION_ID%" ^
  -H "Authorization: Bearer %ADMIN_TOKEN%"
```
