# AI Risk Scorer (ai-risk)

Черновое описание сервиса AI-скоринга, на который ходит processing-core.

## REST API

### `POST /v1/ai/score`

Возвращает скоринговое решение для авторизации операции. Временной лимит вызова на стороне processing-core — 3 секунды (можно переопределить переменной `AI_SCORE_TIMEOUT_SECONDS`). При таймауте или ошибке вызывающая сторона переходит в graceful fallback.

**Request body** (JSON):

```json
{
  "client_id": "uuid",
  "card_id": "uuid",
  "amount": 12345.67,
  "currency": "RUB",
  "merchant": "merchant-uuid",
  "qty": 42,
  "hour": 14,
  "metadata": {
    "terminal_id": "terminal-uuid",
    "product_type": "DIESEL",
    "product_category": "FUEL",
    "mcc": "5541",
    "tx_type": "AUTH",
    "unit_price": 48.9,
    "product_id": "sku-1",
    "tariff_id": "T-1",
    "geo": "55.7522,37.6156",
    "extra": "..."
  }
}
```

**Successful response** (`200 OK`):

```json
{
  "risk_score": 0.76,           // float 0..1
  "decision": "HIGH",         // или "LOW"/"MEDIUM"/"HARD_DECLINE"
  "reason_codes": ["ai_high"], // список кодов причин
  "model_version": "v1.2.3",  // опционально
  "flags": {"any": "extra"}  // опционально
}
```

Поддерживается обратная совместимость с полями `score` и `risk_result`.

**Ошибки**

- `4xx/5xx` — возвращаются с текстом ошибки; вызывающая сторона логирует статус и переходит в fallback.
- Сетевые ошибки / таймаут (`>3s`) также приводят к fallback и увеличивают счётчик ошибок подключения.

## Мониторинг

Processing-core собирает метрики при каждом вызове:

- latency вызова (`latencies_ms`),
- ошибки соединения (по типам `timeout`, `request_error`, `bad_status`),
- распределение скорингов по бакетам `0.0-0.2`, `0.2-0.5`, `0.5-0.8`, `0.8-1.0`.

Для интеграции в реальную систему экспозицию метрик можно повесить на Prometheus/StatsD, используя те же события.
