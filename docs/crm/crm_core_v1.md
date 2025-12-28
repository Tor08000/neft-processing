# CRM Core v1 (Control Plane)

CRM Core v1 — слой управления клиентами и контрактами в платформе.

## Основные сущности

- **CRM Client**: юридическое лицо/клиент в системе.
- **CRM Contract**: договор клиента, задающий billing mode, документы, профили.
- **CRM Tariff Plan**: тарифный план и базовая подписка.
- **CRM Subscription**: подписка клиента на тариф.
- **CRM Limit Profile**: набор лимитов, которые применяются к домену Fuel.
- **CRM Risk Profile**: профиль risk policy для клиента.
- **CRM Feature Flags**: включение доменов (fuel/logistics/docs/risk).

## Админские API

Базовый префикс: `/api/v1/admin/crm`.

### Clients

- `POST /clients`
- `GET /clients`
- `GET /clients/{client_id}`
- `PATCH /clients/{client_id}`

### Contracts

- `POST /clients/{client_id}/contracts`
- `GET /contracts?client_id=...`
- `POST /contracts/{contract_id}/activate`
- `POST /contracts/{contract_id}/pause`
- `POST /contracts/{contract_id}/terminate`
- `POST /contracts/{contract_id}/apply`

### Tariffs

- `POST /tariffs`
- `GET /tariffs`
- `PATCH /tariffs/{tariff_id}`

### Subscriptions

- `POST /clients/{client_id}/subscriptions`
- `GET /subscriptions?client_id=...`
- `POST /subscriptions/{id}/suspend`
- `POST /subscriptions/{id}/resume`

### Profiles

- `POST /limit-profiles`
- `GET /limit-profiles`
- `POST /risk-profiles`
- `GET /risk-profiles`

### Feature Flags

- `GET /clients/{client_id}/features`
- `POST /clients/{client_id}/features/{feature}/enable`
- `POST /clients/{client_id}/features/{feature}/disable`

## Интеграция

При активации/применении контракта:

- создаются лимиты fuel из `crm_limit_profiles.definition`;
- назначается risk policy (через `FuelRiskProfile`);
- включаются feature flags (fuel/logistics/docs/risk).

При паузе/терминации:

- домены отключаются feature flags.
