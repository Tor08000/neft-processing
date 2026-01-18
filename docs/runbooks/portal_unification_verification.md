# Portal Unification Verification (Windows CMD)

> Все команды рассчитаны на Windows CMD. Замените значения `API_BASE`, `ADMIN_TOKEN`, `USER_TOKEN`, `ORG_ID`.

## Environment

```cmd
set API_BASE=http://localhost/api/core
set ADMIN_TOKEN=REPLACE_WITH_ADMIN_TOKEN
set USER_TOKEN=REPLACE_WITH_PORTAL_TOKEN
set ORG_ID=12345
```

---

## Scenario A — Client becomes Partner

```cmd
curl -X POST "%API_BASE%/v1/admin/commercial/orgs/%ORG_ID%/roles/add" ^
  -H "Authorization: Bearer %ADMIN_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"role\":\"PARTNER\",\"reason\":\"partner onboarding\"}"
```

```cmd
curl -X GET "%API_BASE%/portal/me" -H "Authorization: Bearer %USER_TOKEN%"
```

Expected:
- `capabilities` includes `PARTNER_CORE`.
- UI shows partner navigation sections.

---

## Scenario B — Partner becomes Client

```cmd
curl -X POST "%API_BASE%/v1/admin/commercial/orgs/%ORG_ID%/roles/add" ^
  -H "Authorization: Bearer %ADMIN_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"role\":\"CLIENT\",\"reason\":\"client onboarding\"}"
```

```cmd
curl -X GET "%API_BASE%/portal/me" -H "Authorization: Bearer %USER_TOKEN%"
```

Expected:
- `capabilities` includes `CLIENT_CORE` and `CLIENT_BILLING` (при активной подписке).
- UI shows client navigation sections.

---

## Scenario C — Billing overdue affects only client

```cmd
curl -X GET "%API_BASE%/portal/me" -H "Authorization: Bearer %USER_TOKEN%"
```

If subscription status is `OVERDUE`:
- `CLIENT_BILLING` (и другие billing-scoped client capabilities) отсутствуют.
- Partner capabilities остаются доступны.

