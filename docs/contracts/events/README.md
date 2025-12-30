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

Для marketplace событий дополнительно обязательны поля:
- `actor`
- `owner`
- `entity`

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
- EDO_DOCUMENT_SENT
- EDO_DOCUMENT_DELIVERED
- EDO_DOCUMENT_SIGNED_COUNTERPARTY
- EDO_DOCUMENT_REJECTED
- EDO_DOCUMENT_FAILED
- MARKETPLACE_ORDER_CREATED
- MARKETPLACE_ORDER_PAYMENT_AUTHORIZED
- MARKETPLACE_ORDER_PAID
- MARKETPLACE_ORDER_CONFIRMED_BY_PARTNER
- MARKETPLACE_ORDER_STARTED
- MARKETPLACE_ORDER_COMPLETED
- MARKETPLACE_ORDER_CANCELLED
- MARKETPLACE_ORDER_FAILED
- MARKETPLACE_ORDER_DOCUMENT_ISSUED
- MARKETPLACE_ORDER_DOCUMENT_SIGN_REQUESTED
- MARKETPLACE_ORDER_DOCUMENT_SIGNED
- MARKETPLACE_ORDER_DOCUMENT_EDO_DISPATCHED
- MARKETPLACE_ORDER_DOCUMENT_EDO_STATUS_CHANGED
- MARKETPLACE_SETTLEMENT_ALLOCATED
- MARKETPLACE_PAYOUT_BATCH_CREATED
- MARKETPLACE_PAYOUT_BATCH_SENT
- MARKETPLACE_PAYOUT_BATCH_SETTLED
- MARKETPLACE_REFUND_REQUESTED
- MARKETPLACE_REFUND_APPROVED
- MARKETPLACE_REFUND_DENIED
- MARKETPLACE_REFUND_COMPLETED
- MARKETPLACE_DISPUTE_OPENED
- MARKETPLACE_DISPUTE_RESOLVED
