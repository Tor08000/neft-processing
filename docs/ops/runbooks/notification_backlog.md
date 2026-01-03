# Runbook: Notification backlog

## Symptoms
- Рост outbox очереди.
- Пользователи не получают уведомления.
- Увеличение retries.

## Impact
- Потеря уведомлений и задержка отправок.
- Негативный пользовательский опыт.

## Primary dashboards/queries
- Grafana dashboard: **Logs Overview** (Loki) — фильтр `service=workers` или `service=core-api`.
- Grafana dashboard: **Core Incident Logs** — панель “Notification errors”.
- Prometheus queries:
  - `notification_outbox_pending_total`
  - `notification_send_retries_total`
- Loki queries:
  - `{service=~"core-api|workers"} |= "notification" |= "send" |= "failed"`
  - `{service=~"core-api|workers"} |= "webhook" |= "signature"`

## Immediate actions (первые 5 минут)
1. Проверить health sender worker и рост outbox.
2. Проверить доступность провайдеров (email/telegram/webpush/sms_stub/voice_stub).
3. Проверить последние ошибки notification в Loki.

## Diagnosis steps
1. Проверить retries и дедупликацию.
2. Проверить throttle/limits у провайдеров.
3. Проверить подписи webhook.

## Mitigation
- Перезапустить sender worker.
- Включить/усилить throttle для провайдеров.
- Очистить зависшие задания и переотправить outbox.

## Verification
- Outbox уменьшается.
- Уведомления снова доставляются.
- Ошибки в Loki сокращаются.

## Postmortem checklist
- Сохранить метрики retries/outbox.
- Зафиксировать ошибки провайдера и webhook signature.
- Описать первопричину и действия.

## Windows CMD commands
```
curl -fsS http://localhost:8001/api/core/health
curl -fsS http://localhost:5555/api/workers?refresh=1

docker compose logs workers --since 30m

docker compose restart workers
```
