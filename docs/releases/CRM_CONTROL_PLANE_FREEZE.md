# CRM Control Plane Freeze (v1)

## Цель
CRM фиксируется как контур управления, а не набор CRUD. Изменения публичного контракта требуют миграции и версии.

## Стабильные сущности
Следующие сущности считаются стабильными и не меняются без версии:

- clients
- contracts
- tariffs
- subscriptions
- feature_flags
- risk_profiles
- limit_profiles

## Public contract (поля, требующие версии)
### clients
- `id`, `tenant_id`, `legal_name`, `tax_id`, `kpp`, `country`, `timezone`, `status`

### contracts
- `id`, `tenant_id`, `client_id`, `contract_number`, `status`, `valid_from`, `valid_to`
- `billing_mode`, `currency`, `risk_profile_id`, `limit_profile_id`, `documents_required`
- `crm_contract_version`

### tariffs
- `id`, `name`, `status`, `billing_period`, `base_fee_minor`, `currency`, `features`, `limits_defaults`

### subscriptions
- `id`, `tenant_id`, `client_id`, `tariff_plan_id`, `status`, `billing_cycle`, `billing_day`
- `started_at`, `paused_at`, `ended_at`

### feature_flags
- `tenant_id`, `client_id`, `feature`, `enabled`

### risk_profiles
- `id`, `tenant_id`, `name`, `status`, `risk_policy_id`, `threshold_set_id`, `shadow_enabled`

### limit_profiles
- `id`, `tenant_id`, `name`, `status`, `definition`

## Стабильные endpoints
Админ-API, считающиеся публичным контрактом:

- `GET /admin/crm/clients`
- `GET /admin/crm/clients/{client_id}`
- `POST /admin/crm/clients`
- `PATCH /admin/crm/clients/{client_id}`
- `GET /admin/crm/clients/{client_id}/decision-context`

- `GET /admin/crm/contracts`
- `POST /admin/crm/clients/{client_id}/contracts`
- `POST /admin/crm/contracts/{contract_id}/activate`
- `POST /admin/crm/contracts/{contract_id}/pause`
- `POST /admin/crm/contracts/{contract_id}/terminate`

- `GET /admin/crm/tariffs`
- `POST /admin/crm/tariffs`
- `PATCH /admin/crm/tariffs/{tariff_id}`

- `GET /admin/crm/subscriptions`
- `POST /admin/crm/clients/{client_id}/subscriptions`
- `POST /admin/crm/subscriptions/{subscription_id}/change-tariff`
- `POST /admin/crm/subscriptions/{subscription_id}/pause`
- `POST /admin/crm/subscriptions/{subscription_id}/cancel`

- `GET /admin/crm/limit-profiles`
- `POST /admin/crm/limit-profiles`
- `GET /admin/crm/risk-profiles`
- `POST /admin/crm/risk-profiles`
- `GET /admin/crm/clients/{client_id}/features`
- `POST /admin/crm/clients/{client_id}/features/{feature}/enable`
- `POST /admin/crm/clients/{client_id}/features/{feature}/disable`

## Правила freeze
- Любое изменение публичного контракта требует:
  - миграции схемы
  - повышения `crm_contract_version`
  - audit event `CRM_CONTRACT_VERSION_BUMPED`
- Запрещены «тихие изменения» без версии и аудита.

## Policy alignment
- CRM
  - `CRM_*` actions: управление сущностями CRM
- MONEY
  - `MONEY_*` actions: explain/replay для денег
- OPS
  - `OPS_*` actions: ack/close/kpi для OPS

## Почему можно/нельзя
- Можно: расширять контракт через новую версию и миграцию, документируя изменения.
- Нельзя: менять или удалять поля/эндпойнты без версии, миграции и аудит-события.
