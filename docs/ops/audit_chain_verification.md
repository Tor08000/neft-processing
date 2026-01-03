# Audit chain verification

## Purpose / Что проверяем
Проверяем неизменяемую цепочку хэшей в `processing_core.audit_log`: наличие `prev_hash`, корректность вычисления `hash` по формуле из сервиса, отсутствие разрывов цепочки и невозможность UPDATE/DELETE (DB trigger `audit_log_immutable`).

## Prerequisites / Что нужно
- Запущенный стенд: `docker compose up -d`.
- Доступ к gateway: `http://localhost`.
- Установлены `curl`, `docker`, `psql` (через `docker compose exec`).

## Step-by-step / Пошагово
1. Получите admin-токен (используйте значения из `.env`):
   ```cmd
   curl -X POST http://localhost/api/auth/login -H "Content-Type: application/json" -d "{\"email\":\"admin@example.com\",\"password\":\"change-me\"}"
   ```
   Скопируйте `access_token` из ответа.

2. Сгенерируйте контрольное audit-событие через публичный endpoint транзакций (создаёт `audit_log` с `event_type=TX_AUTH`):
   ```cmd
   curl -X POST http://localhost/api/v1/transactions/authorize -H "Content-Type: application/json" -d "{\"client_id\":\"demo-client\",\"card_id\":\"CARD123\",\"terminal_id\":\"TERM-1\",\"merchant_id\":\"MERCH-1\",\"amount\":1000,\"currency\":\"RUB\",\"ext_operation_id\":\"TX-AUDIT-CHECK-001\"}"
   ```
   Запомните `operation_id` из ответа (он попадёт в `entity_id`).

3. Посмотрите последние N записей в `audit_log` (реальные поля таблицы):
   ```cmd
   docker compose exec -T postgres psql -U neft -d neft -c "SET search_path TO processing_core; SELECT id, ts, event_type, entity_type, entity_id, prev_hash, hash FROM audit_log ORDER BY ts DESC, id DESC LIMIT 5;"
   ```

4. Нажимной (admin) способ проверки цепочки через API:
   ```cmd
   curl -X POST http://localhost/api/v1/audit/verify -H "Authorization: Bearer <ACCESS_TOKEN>" -H "Content-Type: application/json" -d "{\"from\":\"2000-01-01T00:00:00Z\",\"to\":\"2099-12-31T23:59:59Z\",\"tenant_id\":null}"
   ```

5. Ручная проверка формулы хэша (последние 5 записей):
   ```cmd
   docker compose exec -T core-api python -c "import os, json, hashlib, ipaddress; from datetime import datetime, timezone; import psycopg; from sqlalchemy.engine import make_url; dsn=os.environ['DATABASE_URL']; url=make_url(dsn); url=url.set(drivername='postgresql') if url.drivername.endswith('+psycopg') else url; dsn=url.render_as_string(hide_password=False); conn=psycopg.connect(dsn, options='-c search_path=processing_core'); cur=conn.cursor(row_factory=psycopg.rows.dict_row); cur.execute('SELECT id, ts, tenant_id, actor_type, actor_id, actor_email, actor_roles, ip, user_agent, request_id, trace_id, event_type, entity_type, entity_id, action, visibility, before, after, diff, external_refs, reason, attachment_key, prev_hash, hash FROM audit_log ORDER BY ts DESC, id DESC LIMIT 5'); rows=cur.fetchall(); rows.reverse(); def normalize(value):\n    if isinstance(value, datetime):\n        return value.astimezone(timezone.utc).isoformat();\n    if isinstance(value, (ipaddress.IPv4Address, ipaddress.IPv6Address)):\n        return str(value);\n    if isinstance(value, dict):\n        return {str(k): normalize(value[k]) for k in sorted(value)};\n    if isinstance(value, list):\n        return [normalize(v) for v in value];\n    return value;\nprev='GENESIS';\nfor row in rows:\n    data={\n        'id': row['id'],\n        'ts': row['ts'],\n        'tenant_id': row['tenant_id'],\n        'actor_type': row['actor_type'],\n        'actor_id': row['actor_id'],\n        'actor_email': row['actor_email'],\n        'actor_roles': row['actor_roles'],\n        'ip': row['ip'],\n        'user_agent': row['user_agent'],\n        'request_id': row['request_id'],\n        'trace_id': row['trace_id'],\n        'event_type': row['event_type'],\n        'entity_type': row['entity_type'],\n        'entity_id': row['entity_id'],\n        'action': row['action'],\n        'visibility': row['visibility'],\n        'before': row['before'],\n        'after': row['after'],\n        'diff': row['diff'],\n        'external_refs': row['external_refs'],\n        'reason': row['reason'],\n        'attachment_key': row['attachment_key'],\n    };\n    data={k: normalize(v) for k,v in data.items() if v is not None};\n    payload=json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False);\n    expected=hashlib.sha256(f'{payload}{prev}'.encode('utf-8')).hexdigest();\n    status='OK' if row['hash']==expected and row['prev_hash']==prev else 'BROKEN';\n    print(f\"{row['id']} {status}\");\n    prev=row['hash'];"
   ```
   Формула проверки: `hash = sha256(canonical_payload + prev_hash)`, где `canonical_payload` — JSON с сортировкой ключей и нормализацией значений.

6. Проверьте неизменяемость (UPDATE/DELETE должны завершиться ошибкой):
   ```cmd
   docker compose exec -T postgres psql -U neft -d neft -c "SET search_path TO processing_core; UPDATE audit_log SET action = 'TAMPER' WHERE id = '<AUDIT_ID_FROM_STEP_3>';"
   docker compose exec -T postgres psql -U neft -d neft -c "SET search_path TO processing_core; DELETE FROM audit_log WHERE id = '<AUDIT_ID_FROM_STEP_3>';"
   ```

## Expected results / Ожидаемые результаты
- В `audit_log` есть записи с заполненными `prev_hash` и `hash`.
- В `audit_log` для первой записи цепочки `prev_hash` = `GENESIS`.
- `/api/v1/audit/verify` возвращает:
  ```json
  {"status":"OK","checked":<N>,"broken_at_id":null,"message":""}
  ```
- Ручная проверка (step 5) показывает `OK` для каждой записи.
- UPDATE/DELETE возвращают ошибку вида:
  - `ERROR: audit_log is immutable`

## Troubleshooting / Если не получилось
- **403 при вызове `/api/v1/audit/verify`** → token без admin-ролей. Проверьте логин через `/api/auth/login` и роли в `.env` (`NEFT_BOOTSTRAP_ADMIN_ROLES`).
- **Нет записей в `audit_log`** → убедитесь, что вызвали `POST /api/v1/transactions/authorize` и core-api healthy.
- **`status=BROKEN` в verify** → временной диапазон захватил разные `tenant_id`; попробуйте ограничить `tenant_id` или сузить диапазон `from/to`.
- **Ручная проверка показывает BROKEN** → запись была изменена вручную или включены альтернативные миграции. Проверьте, что поиск идёт по `processing_core.audit_log`.
- **UPDATE/DELETE проходят без ошибки** → миграция `0042_audit_log.py` не применена. Проверьте логи core-api и таблицу `alembic_version_core`.

## Evidence checklist / Что приложить аудитору
- Команда login + ответ с `access_token` (можно замаскировать токен).
- Команда создания контрольного события (`POST /api/v1/transactions/authorize`) и ответ.
- Вывод SQL с `prev_hash`/`hash` (`audit_log`).
- Ответ `/api/v1/audit/verify` со статусом `OK`.
- Вывод ручной проверки хэшей (step 5).
- Ошибка `audit_log is immutable` при UPDATE/DELETE.
