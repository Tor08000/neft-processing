# Unified Explain v1

## Fleet Manager View

`unified_explain.sources.fuel.fleet_view` и `unified_explain.sources.logistics.fleet_view` возвращают удобный для менеджера маршрутный контекст.

```json
{
  "fleet_view": {
    "where": {
      "stop_id": "...",
      "distance_km": 12.4,
      "timestamp": "2025-01-10T12:32:00Z"
    },
    "threshold": {
      "max_deviation_km": 5
    },
    "recommendations": [
      "Маршрут отклонён более чем на 12 км"
    ]
  }
}
```

## Accountant View

`unified_explain.accountant_view` даёт лимитный контекст для бухгалтерии.

```json
{
  "accountant_view": {
    "limit": {
      "type": "DAILY",
      "value": 50000,
      "currency": "RUB"
    },
    "period": "2025-01-01 → 2025-01-31",
    "reason": "Превышение лимита",
    "recommendations": [
      "Проверьте лимит клиента на период"
    ]
  }
}
```

## CFO Money Summary

`unified_explain.money_summary` агрегирует итоговые суммы по денежному потоку.

```json
{
  "money_summary": {
    "charged": 120000,
    "paid": 80000,
    "due": 40000,
    "refunded": 0,
    "currency": "RUB"
  },
  "money_replay": {
    "replay_id": "...",
    "admin_url": "/admin/money/replay/{id}"
  },
  "invariants": {
    "status": "OK",
    "violations": []
  }
}
```

## CRM Context

`unified_explain.crm` и `unified_explain.crm_effect` описывают тариф, подписку и влияние CRM.

```json
{
  "crm": {
    "tariff": {
      "id": "enterprise_fuel_v4",
      "name": "Enterprise Fuel"
    },
    "subscription": {
      "status": "ACTIVE",
      "period": "2025-01"
    },
    "metrics_used": {
      "fuel_tx_count": 124,
      "drivers": 12
    },
    "feature_flags": [
      "FUEL_ENABLED",
      "LOGISTICS_ENABLED"
    ]
  },
  "crm_effect": {
    "allowed": false,
    "reason": "Тариф не включает ночные заправки"
  }
}
```
