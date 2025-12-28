# CRM Limit Profiles (Examples)

## Canonical definition schema

```json
{
  "version": 1,
  "rules": [
    {
      "scope_type": "CLIENT|CARD_GROUP|CARD|VEHICLE|DRIVER",
      "scope_selector": {
        "mode": "CLIENT_ALL|GROUP_ALL|EACH_CARD|EACH_VEHICLE|EACH_DRIVER",
        "filter": {}
      },
      "limit_type": "AMOUNT|VOLUME|COUNT",
      "period": "DAILY|WEEKLY|MONTHLY",
      "value": 0,
      "currency": "RUB",
      "priority": 100,
      "constraints": {
        "fuel_type": null,
        "station_id": null,
        "network_id": null,
        "time_window_start": null,
        "time_window_end": null,
        "timezone": "Europe/Moscow"
      },
      "meta": {
        "name": "Human readable",
        "purpose": "..."
      }
    }
  ]
}
```

## Profile: FUEL_BASIC

```json
{
  "version": 1,
  "rules": [
    {
      "scope_type": "CLIENT",
      "scope_selector": { "mode": "CLIENT_ALL", "filter": {} },
      "limit_type": "AMOUNT",
      "period": "MONTHLY",
      "value": 50000000,
      "currency": "RUB",
      "priority": 500,
      "constraints": { "fuel_type": null, "station_id": null, "network_id": null, "time_window_start": null, "time_window_end": null, "timezone": "Europe/Moscow" },
      "meta": { "name": "Monthly client amount cap", "purpose": "Global spend cap" }
    },
    {
      "scope_type": "CARD",
      "scope_selector": { "mode": "EACH_CARD", "filter": {} },
      "limit_type": "AMOUNT",
      "period": "DAILY",
      "value": 300000,
      "currency": "RUB",
      "priority": 100,
      "constraints": { "fuel_type": null, "station_id": null, "network_id": null, "time_window_start": null, "time_window_end": null, "timezone": "Europe/Moscow" },
      "meta": { "name": "Daily card spend limit", "purpose": "Reduce fraud impact" }
    },
    {
      "scope_type": "CARD",
      "scope_selector": { "mode": "EACH_CARD", "filter": {} },
      "limit_type": "VOLUME",
      "period": "DAILY",
      "value": 200000,
      "currency": null,
      "priority": 90,
      "constraints": { "fuel_type": null, "station_id": null, "network_id": null, "time_window_start": null, "time_window_end": null, "timezone": "Europe/Moscow" },
      "meta": { "name": "Daily card liters limit", "purpose": "Cap liters/day (ml)" }
    },
    {
      "scope_type": "CARD",
      "scope_selector": { "mode": "EACH_CARD", "filter": {} },
      "limit_type": "COUNT",
      "period": "DAILY",
      "value": 5,
      "currency": null,
      "priority": 80,
      "constraints": { "fuel_type": null, "station_id": null, "network_id": null, "time_window_start": null, "time_window_end": null, "timezone": "Europe/Moscow" },
      "meta": { "name": "Daily fueling count limit", "purpose": "Stop rapid refuel pattern" }
    }
  ]
}
```

## Profile: FUEL_PRO

```json
{
  "version": 1,
  "rules": [
    {
      "scope_type": "CARD",
      "scope_selector": { "mode": "EACH_CARD", "filter": {} },
      "limit_type": "AMOUNT",
      "period": "DAILY",
      "value": 200000,
      "currency": "RUB",
      "priority": 100,
      "constraints": { "fuel_type": null, "station_id": null, "network_id": null, "time_window_start": null, "time_window_end": null, "timezone": "Europe/Moscow" },
      "meta": { "name": "Daily card spend", "purpose": "Base daily cap" }
    },
    {
      "scope_type": "CARD",
      "scope_selector": { "mode": "EACH_CARD", "filter": {} },
      "limit_type": "AMOUNT",
      "period": "DAILY",
      "value": 50000,
      "currency": "RUB",
      "priority": 50,
      "constraints": { "fuel_type": null, "station_id": null, "network_id": null, "time_window_start": "23:00:00", "time_window_end": "06:00:00", "timezone": "Europe/Moscow" },
      "meta": { "name": "Night spend cap", "purpose": "Night fraud reduction" }
    },
    {
      "scope_type": "VEHICLE",
      "scope_selector": { "mode": "EACH_VEHICLE", "filter": {} },
      "limit_type": "VOLUME",
      "period": "DAILY",
      "value": 250000,
      "currency": null,
      "priority": 80,
      "constraints": { "fuel_type": "DIESEL", "station_id": null, "network_id": null, "time_window_start": null, "time_window_end": null, "timezone": "Europe/Moscow" },
      "meta": { "name": "Daily diesel liters per vehicle", "purpose": "Control diesel usage per vehicle" }
    }
  ]
}
```

## Profile: ENTERPRISE

```json
{
  "version": 1,
  "rules": [
    {
      "scope_type": "CARD_GROUP",
      "scope_selector": { "mode": "GROUP_ALL", "filter": {} },
      "limit_type": "AMOUNT",
      "period": "MONTHLY",
      "value": 200000000,
      "currency": "RUB",
      "priority": 200,
      "constraints": { "fuel_type": null, "station_id": null, "network_id": null, "time_window_start": null, "time_window_end": null, "timezone": "Europe/Moscow" },
      "meta": { "name": "Monthly group budget", "purpose": "Budget per department" }
    },
    {
      "scope_type": "CARD",
      "scope_selector": { "mode": "EACH_CARD", "filter": {} },
      "limit_type": "COUNT",
      "period": "DAILY",
      "value": 3,
      "currency": null,
      "priority": 50,
      "constraints": { "fuel_type": null, "station_id": null, "network_id": null, "time_window_start": null, "time_window_end": null, "timezone": "Europe/Moscow" },
      "meta": { "name": "Daily fueling count strict", "purpose": "Stop fraud patterns" }
    },
    {
      "scope_type": "CARD",
      "scope_selector": { "mode": "EACH_CARD", "filter": {} },
      "limit_type": "AMOUNT",
      "period": "DAILY",
      "value": 150000,
      "currency": "RUB",
      "priority": 70,
      "constraints": { "fuel_type": null, "station_id": null, "network_id": "GAZPROM", "time_window_start": null, "time_window_end": null, "timezone": "Europe/Moscow" },
      "meta": { "name": "Network override cap", "purpose": "Special deal network budget guard" }
    }
  ]
}
```
