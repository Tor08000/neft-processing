# Partner Money E2E — инварианты

## Инвариант Partner Money

- partner token всегда содержит org context.
- seed всегда возвращает org id.
- smoke никогда не продолжает после seed FAIL.
- payout невозможен без audit trail.

## Manual verification

### Реальные URL-ы (локально)

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
