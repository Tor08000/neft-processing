# Индексация журнала `operations` (план v0.1.2)

## Аудит использования колонок
- **Фильтры по идентификаторам**: `operation_id`, `card_id`, `client_id`, `merchant_id`, `terminal_id`, `parent_operation_id` используются для поиска операций и построения таймлайнов в админском API и публичном журнале.【F:services/core-api/app/routers/admin/operations.py†L88-L131】【F:services/core-api/app/services/operations_query.py†L8-L33】
- **Статус и тип операции**: `operation_type` и `status` участвуют в фильтрации и построении транзакций/clearing.【F:services/core-api/app/routers/admin/operations.py†L88-L110】【F:services/core-api/app/services/transactions.py†L257-L290】
- **Диапазоны по времени**: `created_at` используется для пагинации, выборок по диапазону и сортировки журналов и транзакций.【F:services/core-api/app/routers/admin/operations.py†L102-L116】【F:services/core-api/app/services/transactions.py†L257-L282】【F:services/core-api/app/services/operations_query.py†L8-L33】
- **Числовые ограничения**: `amount`, `captured_amount`, `refunded_amount` применяются в фильтрах и агрегациях биллинга/лимитов.【F:services/core-api/app/routers/admin/operations.py†L112-L120】【F:services/core-api/app/services/reports_billing.py†L21-L45】【F:services/core-api/app/services/limits_engine.py†L81-L95】
- **Продуктовые атрибуты**: `mcc`, `product_category`, `tx_type` фильтруют админский журнал и отчёты.【F:services/core-api/app/routers/admin/operations.py†L112-L120】【F:services/core-api/app/services/reports_billing.py†L21-L45】

## Новые индексы (миграция `20260115_0011_operations_indexes`)
- **Составные под сортировку журнала**: `(merchant_id, created_at DESC)`, `(terminal_id, created_at DESC)`, `(client_id, created_at DESC)`, `(card_id, created_at DESC)`, `(operation_type, created_at DESC)` ускоряют выборки с фильтрами по ключам и пагинацией по дате.【F:services/core-api/app/alembic/versions/20260115_0011_operations_indexes.py†L20-L54】
- **Частичный индекс на открытые операции**: `idx_operations_open_only` по `created_at` со `status = 'OPEN'` для дешёвых выборок незавершённых транзакций.【F:services/core-api/app/alembic/versions/20260115_0011_operations_indexes.py†L56-L64】
- **BRIN по времени**: `idx_operations_created_brin` ускоряет сканы больших диапазонов `created_at` без лишних B-Tree-страниц.【F:services/core-api/app/alembic/versions/20260115_0011_operations_indexes.py†L66-L73】

## Изменения запросов
- Сортировки журналов и таймлайнов теперь используют `created_at` вместе с `operation_id` для детерминированного порядка, лучше совпадающего с новыми индексами по времени.【F:services/core-api/app/crud/operations.py†L45-L54】【F:services/core-api/app/services/operations_query.py†L8-L33】【F:services/core-api/app/services/transactions.py†L257-L282】【F:services/core-api/app/routers/admin/operations.py†L217-L231】

## Рекомендации по обслуживанию
- После деплоя миграции выполнить `ANALYZE operations;` или запланировать `VACUUM ANALYZE operations;` для обновления статистики планировщика.
- Для крупных таблиц с BRIN увеличить частоту autovacuum на `operations`:
  - `autovacuum_vacuum_scale_factor = 0.01`
  - `autovacuum_analyze_scale_factor = 0.005`
  - при высоком темпе вставок рассмотреть `maintenance_work_mem` под построение BRIN.
- Регулярно проверять `pg_stat_all_indexes` и менять fillfactor/REINDEX только при явной фрагментации.
