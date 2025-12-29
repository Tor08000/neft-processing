# Contract testing (CDC + provider verification)

## Инструмент
Выбран инструмент **Schemathesis** для provider verification по OpenAPI (HTTP). Он генерирует кейсы по спецификации, проверяет статусы/схемы ответов и даёт regression gate в CI.

## Область покрытия
Минимальный набор контрактов:

**Core API (gateway/core)**
- Fuel API: `/api/v1/fuel/transactions/authorize`, `/api/v1/fuel/transactions/{transaction_id}/settle`
- Unified Explain API: `/api/core/v1/admin/explain`
- Money Flow API: `/api/core/v1/admin/money/health`, `/api/core/v1/admin/money/replay`, `/api/core/v1/admin/money/cfo-explain`
- CRM Control Plane API: `/api/core/v1/admin/crm/tariffs`, `/api/core/v1/admin/crm/tariffs/{tariff_id}`, `/api/core/v1/admin/crm/clients/{client_id}/subscriptions`
- Logistics/Navigator API: `/api/core/v1/admin/logistics/orders/{order_id}/eta/recompute`, `/api/core/v1/admin/logistics/routes/{route_id}/navigator`, `/api/core/v1/admin/logistics/routes/{route_id}/navigator/explain`
- Ops Workflow API: `/api/core/v1/admin/ops/escalations`, `/api/core/v1/admin/ops/reports/sla`

**Event contracts**
- `docs/contracts/events/*.json` — JSON Schema-реестр для доменных событий.

## Правила версионирования
### Breaking changes (требуют версии)
- Новый путь `/v2/...` или изменение существующего контракта без обратной совместимости.
- Удаление/переименование/смена типов полей без новой версии.
- Изменение смысла decline codes без bump версии.
- Для событий — увеличение `schema_version`.
- Для CRM Control Plane — bump `X-CRM-Version`.

### Non-breaking changes
- Добавление новых полей **только optional**.
- Сохранение всех существующих полей и их типов.

### Запрещено без версии
- Удалять поля.
- Менять типы полей.
- Менять meaning decline codes.

## CI merge-gate
В CI выполняются контрактные тесты:

```bash
pytest -m contracts
```

Эти проверки должны быть **required** в настройках репозитория (branch protection rules).

## Как правильно выпускать v2
1. Добавить новый путь `/v2/...` или увеличить `schema_version`/`X-CRM-Version`.
2. Обновить OpenAPI или JSON Schema.
3. Добавить/обновить контрактные тесты.
4. Убедиться, что CI проходит.
