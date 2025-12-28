# Tariffs & Subscriptions

CRM v1 хранит тарифы и подписки, но не выполняет расчёт списаний.

## Tariff Plan

Поля:

- `id`: человекочитаемый код тарифа (`FUEL_BASIC`, `FUEL_PRO`).
- `billing_period`: `MONTHLY` или `YEARLY`.
- `base_fee_minor`: базовый платёж (minor units).
- `features`: JSON-флаги (`fuel`, `logistics`, `docs`, `risk`).
- `limits_defaults`: дефолтные настройки лимитов (опционально).

## Subscription

Поля:

- `client_id`, `tariff_id`
- `status`: `ACTIVE`, `PAST_DUE`, `SUSPENDED`, `CANCELLED`
- `started_at`, `renew_at`, `ended_at`

Подписка в v1 нужна как сущность, даже если реальное списание не включено.
