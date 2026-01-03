# Virtual Fuel Network demo

## Quick start

1. Ensure the core-api container is running with access to `data/virtual_fuel_network/config.yaml`.
2. Enable the provider connection for a client with provider code `virtual_fuel_network`.
3. Use the admin endpoints to seed stations, set prices, and generate transactions.

## Sample admin flow

```bash
# inspect config
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/core/v1/admin/virtual-network/config | jq

# seed stations
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"count": 5, "region": "Moscow", "city": "Moscow"}' \
  http://localhost:8000/api/core/v1/admin/virtual-network/stations/seed | jq

# set prices
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prices": {"VN-0001": {"AI95": 60.2, "DT": 62.0}}}' \
  http://localhost:8000/api/core/v1/admin/virtual-network/prices/set | jq

# generate transactions
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"client_id": "<client-id>", "card_alias": "NEFT-00001234", "count": 3}' \
  http://localhost:8000/api/core/v1/admin/virtual-network/txns/generate | jq
```

## Demo checklist

- Stations visible in admin stations list (or map if enabled).
- Transactions appear in fleet transactions list after provider poll.
- Breaches and anomalies visible in alerts.
- Auto-block status reflected on the card.
