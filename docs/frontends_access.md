# Доступ к фронтендам (копировать/вставить)

Ниже собраны **рабочие ссылки** и **дефолтные доступы** для каждого фронта. Ссылки сгруппированы так, чтобы можно было просто копировать и вставлять.

## Через gateway (рекомендуемый способ)

> Используйте, если поднят `gateway` в `docker compose`.

```text
Admin UI:   http://localhost/admin/
Client UI:  http://localhost/client/
Partner UI: http://localhost/partner/
```

Gateway проксирует SPA фронты по путям `/admin/`, `/client/`, `/partner/`.【F:gateway/nginx.conf†L246-L319】

## Напрямую по портам контейнеров

> Полезно, если нужно зайти напрямую в сервис фронта, минуя gateway.

```text
Admin UI (direct):   http://localhost:4173/
Client UI (direct):  http://localhost:4174/
Partner UI (direct): http://localhost:4175/
```

Порты соответствуют фронтендам в compose-каталоге сервисов.【F:docs/as-is/SERVICE_CATALOG.md†L28-L32】

## Доступы (дефолтные логины)

> Дефолтные логины/пароли берутся из логин-страниц фронтов и e2e-утилит. Можно заменить через переменные окружения для e2e (см. примечания ниже).

```text
Admin
  email:    admin@example.com
  password: change-me

Client
  email:    client@neft.local
  password: Neft123! (регистр важен)

Partner
  email:    partner@neft.local
  password: partner
```

Источники дефолтов:
- Admin UI: `NEFT_DEMO_ADMIN_EMAIL` / `NEFT_DEMO_ADMIN_PASSWORD` (или только email, если пароль скрыт в UI).【F:frontends/admin-ui/src/pages/LoginPage.tsx†L11-L15】
- Client UI: `client@neft.local` / `Neft123!`.【F:frontends/client-portal/src/pages/LoginPage.tsx†L14-L17】
- Partner UI: `partner@neft.local` / `partner`.【F:frontends/partner-portal/src/pages/LoginPage.tsx†L11-L14】

В dev окружении эти пользователи детерминированно сидятся через auth-host seed/CLI — см. runbook
`docs/runbooks/DEMO_USERS_AND_LOGIN.md`.

## Примечание про override доступов

В e2e сценариях логины можно переопределять через переменные окружения:
- `ADMIN_EMAIL`, `ADMIN_PASSWORD`
- `CLIENT_EMAIL`, `CLIENT_PASSWORD`
- `PARTNER_EMAIL`, `PARTNER_PASSWORD`

Это используется в e2e-утилитах при логине.【F:frontends/e2e/tests/utils.ts†L3-L28】

Эти же переменные учитываются auth-host seed/CLI для детерминированного сброса демо-паролей.


## Client portal base/env contract

```text
BASE_URL=/client/
VITE_AUTH_API_BASE=/api/v1/auth
VITE_CORE_API_BASE=/api/core
```

Для клиентского портала канонический demo-вход: `client@neft.local` / `Neft123!` (регистр важен).
