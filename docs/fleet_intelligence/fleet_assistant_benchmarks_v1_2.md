# Fleet Assistant Benchmarks v1.2 (No-ML)

## Что это
Benchmark mode отвечает на вопрос: «Это нормально или хуже, чем у других?» и строит
детерминированные сравнения на данных Fleet Intelligence без ML и без внешних датасетов.

## Ограничения
- Нет ML/кластеризации.
- Нет внешних данных и cross-tenant сравнения.
- Нет влияния на блокировки.
- Только сравнение в рамках парка клиента или (опционально) тенанта.

## Peer group (детерминированно)
- По умолчанию используется **client peer group** (в рамках одного клиента).
- При включённом флаге `FLEET_BENCHMARK_USE_TENANT=true` используется **tenant peer group**.
- Для станций сравнение всегда в пределах тенанта, с учётом `network_id` (если есть).

### Фильтры
**Driver**
- `client_id` совпадает.
- `window_days` совпадает (7d/30d).
- Берутся последние `computed_at` за день.

**Vehicle**
- `client_id` совпадает.
- Только ТС с доступной дистанцией (наличие `fuel_per_100km`).

**Station**
- `tenant_id` совпадает.
- `network_id` совпадает (если есть).
- `window_days` = 30d.

## Метрики
**Driver**
- `driver_behavior_score` (больше = хуже).
- `trend_label` из history сравнения.

**Vehicle**
- `vehicle_efficiency_delta_pct` (больше = хуже).
- `fuel_per_100km` (если доступно).

**Station**
- `station_trust_score` (больше = лучше) — для percentiles инвертируется.
- `risk_block_rate` (если доступно из station daily).

## Percentiles
Для метрик “больше = хуже”:
```
percentile = rank(value) / (n - 1)
```
Выводится текст вида “хуже, чем X%”.

Для `station_trust_score` применяется инверсия:
```
value_badness = 100 - trust_score
```

### Выводимые percentiles
- p50 (median), p80, p90.
- percentile текущей сущности.

### Малые выборки
Если `n < 10`, benchmark помечается как `INSUFFICIENT_SAMPLE` и показывается только история.

## Историческое сравнение (history)
В benchmark включается сравнение с самим собой: текущие 7d vs прошлые 30d (из trends v2).

Пример:
```
"history": {
  "trend_label": "DEGRADING",
  "delta_7d": 9.2
}
```

## Текст ответа
- Driver: “Этот водитель хуже, чем X% водителей вашего парка за последние 7 дней.”
- Vehicle: “Перерасход хуже, чем у X% ваших ТС.”
- Station: “Эта станция в нижних X% по доверенности среди станций сети …”

## Basis
Benchmark payload включает:
- `n` (sample size),
- `scope` (CLIENT/TENANT),
- `window_days`.

