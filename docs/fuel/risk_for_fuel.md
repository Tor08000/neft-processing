# Risk v4 for Fuel Transactions

## Context features
Fuel authorization builds a DecisionContext for the existing Risk v4 engine with:
- `amount_total_minor`
- `volume_ml`
- `fuel_type`
- `station_id`, `network_id`
- `client_id`, `card_id`, `vehicle_id`, `driver_id`
- Velocity: `tx_count_1h`, `tx_count_24h`, `total_amount_24h`, `total_volume_24h`
- Tank sanity: `volume_liters > capacity * 1.2`

## Outcomes
- **ALLOW** → `AUTHORIZED`
- **MANUAL_REVIEW** → `REVIEW_REQUIRED`
- **DECLINE** → `DECLINED`

## Explain payload
Risk declines or reviews return `risk_explain` with decision, score, thresholds, and policy metadata from the DecisionEngine payload.
