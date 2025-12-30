# Recovery test v1

## Disaster Recovery сценарии
- DB corruption
- Lost primary node
- Deleted document object
- Broken deployment

## RPO / RTO (v1)
- **RPO:** ≤ 24h
- **RTO:** ≤ 2–4h

## Dry-run восстановления (обязательное упражнение)

### План
1. Развернуть восстановленный стенд из последнего бэкапа.
2. Прогнать health checks.
3. Выполнить money replay.
4. Выполнить invoice replay.
5. Проверить document integrity (sha256).

### Результаты
- Дата: TBD
- Восстановленный стенд: TBD
- Health: TBD
- Money replay: TBD
- Invoice replay: TBD
- Document integrity (sha256): TBD
- Итог: TBD
