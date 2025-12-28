# Tariff JSON v2

This document describes the canonical tariff definition for subscriptions v2.

## Schema

```json
{
  "version": 2,
  "base_fee": {
    "amount_minor": 2990000,
    "currency": "RUB",
    "proration": "DAILY"
  },
  "included": [
    { "metric": "CARDS_COUNT", "value": 50, "proration": "DAILY" },
    { "metric": "FUEL_TX_COUNT", "value": 2000, "proration": "LINEAR" }
  ],
  "overage": [
    { "metric": "CARDS_COUNT", "unit_price_minor": 10000 },
    { "metric": "FUEL_TX_COUNT", "unit_price_minor": 80 }
  ],
  "metric_rules": [
    {
      "if": { "metric": "FUEL_TX_COUNT", "op": ">", "value": 10000 },
      "then": { "set_overage_price_minor": 60, "metric": "FUEL_TX_COUNT" }
    },
    {
      "if": { "metric": "LOGISTICS_ORDERS", "op": ">", "value": 2000 },
      "then": { "add_base_fee_minor": 2000000 }
    }
  ],
  "caps": [
    { "metric": "FUEL_TX_COUNT", "max_overage_amount_minor": 5000000 }
  ],
  "domains": {
    "fuel_enabled": true,
    "logistics_enabled": true,
    "documents_enabled": true,
    "risk_blocking_enabled": true
  }
}
```

## Determinism rules

- `metric_rules` are evaluated strictly in the JSON order.
- All arithmetic runs in minor units.
- Rounding always floors (down).

