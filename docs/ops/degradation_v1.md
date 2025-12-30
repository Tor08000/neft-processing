# Graceful degradation v1

## Критические зависимости
- Postgres
- Redis
- MinIO
- document-service
- integration-hub
- external providers (ЭДО, e-sign)

## Ожидаемое поведение при отказах

| Компонент падает | Ожидаемое поведение |
| --- | --- |
| Redis | no data loss, retry, slower |
| MinIO | документы не финализируются |
| document-service | core fallback / error surfaced |
| E-sign | статус FAILED, lifecycle не двигается |
| ЭДО | async retries, core unaffected |
| ERP | reconciliation → FAILED |

## Chaos tests (минимум)

### Сценарии
- выключить document-service
- выключить integration-hub
- отключить Redis
- ограничить DB connections

### Проверки
- нет silent success
- нет неконсистентных статусов
- audit фиксирует ошибки

## Результаты
- Статус: TBD
- Дата: TBD
- Ссылка на логи/дашборды: TBD
