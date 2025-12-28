# Navigator Core (Logistics v3)

## Зачем abstraction
Navigator отделяет логику маршрута от конкретного провайдера карт. Это позволяет:

- держать единый контракт для `build_route`, `estimate_eta`, `distance`, `deviation_score`;
- получать стабильные `route snapshots` и explain-пейлоады без UI и SDK;
- подключать новые провайдеры без изменений в core-логике логистики и risk/fraud.

По умолчанию используется `noop`-адаптер, который рассчитывает маршрут по прямой между точками.

## Как подключать Яндекс позже
1. Реализовать адаптер в `platform/processing-core/app/services/logistics/navigator/yandex_stub.py` с реальным HTTP-клиентом.
2. Собрать ответ провайдера в формат `RouteSnapshot` и `ETAResult`.
3. Включить флаг окружения:
   - `LOGISTICS_NAVIGATOR_PROVIDER=yandex`
   - `LOGISTICS_NAVIGATOR_ENABLED=true`

В `registry.get()` провайдер выбирается по флагу и не требует изменений в `routes`, `eta` и `deviation`.

## Explain payloads
### ETA
```json
{
  "navigator": "noop",
  "method": "straight_line",
  "distance_km": 124.6,
  "eta_minutes": 156,
  "assumptions": [
    "no traffic",
    "avg_speed=48kmh"
  ]
}
```

### Deviation
```json
{
  "expected_distance": 120.0,
  "actual_distance": 182.4,
  "delta_pct": 52,
  "score": 0.91,
  "reason": "significant off-route movement"
}
```

## Влияние на risk/fraud
Navigator добавляет сигналы в risk-context, не меняя существующую логику:

- `route_deviation_score` — числовой score отклонения от ожидаемой геометрии.
- `eta_overrun_pct` — процент превышения ETA над плановой длительностью маршрута.

Эти данные доступны в antifraud (fuel) и могут быть использованы в risk engine v4/v5 shadow.
