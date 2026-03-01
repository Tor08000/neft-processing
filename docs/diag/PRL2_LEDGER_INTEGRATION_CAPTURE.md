# PR-L2: Internal Ledger v1 integration for Fuel CAPTURE/SETTLE

## Integration point

Business settlement path is `settle_fuel_tx()` in:
- `platform/processing-core/app/services/fuel/settlement.py`

The endpoint entrypoint is:
- `platform/processing-core/app/api/v1/endpoints/fuel_transactions.py` (`POST /api/v1/fuel/transactions/{transaction_id}/settle`)

## Idempotency key

For ledger v1 CAPTURE posting:
- `fuel:capture:<fuel_tx_id>`

## Correlation and dimensions

`InternalLedgerService.post_entry(...)` receives:
- `entry_type = CAPTURE`
- `correlation_id = <fuel_tx_id>`
- narrative with tx/client/partner/gross/fee/net

Minimum dimensions sent:
- `client_id`
- `partner_id`
- `fuel_tx_id`

Optional dimensions when available:
- `merchant_id`
- `contract_id`
- `station_id`
- `invoice_id`

## Posting schema (double-entry)

For amounts in RUB:
- `gross_amount = fuel purchase amount`
- `platform_fee >= 0`
- `partner_net = gross_amount - platform_fee`
- invariant: `gross_amount = partner_net + platform_fee`

Ledger lines for CAPTURE:
1. `DR CLIENT_AR` (owner_type `CLIENT`, owner_id = client)
2. `CR PARTNER_AP` (owner_type `PARTNER`, owner_id = partner)
3. `CR PLATFORM_FEES_REVENUE` (owner_type `PLATFORM`, owner_id null) — created only when fee > 0

If fee is `0`, posting remains balanced with 2 lines (`DR CLIENT_AR`, `CR PARTNER_AP`).
