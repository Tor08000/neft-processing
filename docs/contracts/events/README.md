# Event contracts registry

Этот каталог содержит JSON Schema для доменных событий NEFT.

## Формат события
Каждое событие **обязано** содержать:
- `event_id` (uuid)
- `occurred_at` (ISO 8601)
- `correlation_id`
- `trace_id`
- `schema_version`
- `event_type`
- `payload`

## Версионирование
- Любое breaking-изменение в payload или метаданных требует повышения `schema_version`.
- Non-breaking: добавление **optional** полей в `payload`.
- Запрещено без версии:
  - удалять поля;
  - менять типы;
  - менять смысл полей и кодов.

## Правило выпуска новой версии
1. Создайте новую схему с увеличенным `schema_version`.
2. Обновите тесты и потребителей.
3. Проверьте `pytest -m contracts`.

## Список событий
- OPERATION_AUTHORIZED
- OPERATION_DECLINED
- FUEL_SETTLED
- MONEY_FLOW_LINK_WRITTEN
- INVOICE_ISSUED
- OPS_ESCALATION_CREATED
- FLEET_ACTION_APPLIED
- FLEET_EFFECT_RECORDED
- CRM_SUBSCRIPTION_CHANGED
