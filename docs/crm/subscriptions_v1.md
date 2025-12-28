# CRM Subscriptions v1 (Billing-native)

Subscriptions v1 are server-side only and feed the existing billing pipeline.

## Data model

### crm_subscriptions

- `id`, `tenant_id`, `client_id`
- `tariff_plan_id`
- `status`: `ACTIVE`, `PAUSED`, `CANCELLED`
- `billing_cycle`: `MONTHLY`
- `billing_day`: integer (default 1)
- `started_at`, `paused_at`, `ended_at`
- `meta`, `created_at`, `updated_at`

### crm_subscription_charges

What we billed for a subscription in a billing period.

- `charge_type`: `BASE_FEE`, `OVERAGE`
- `code`, `quantity`, `unit_price`, `amount`, `currency`
- `source` JSON explains the charge

### crm_usage_counters

Monthly usage snapshots for pricing and audit.

- `metric`: `CARDS_COUNT`, `VEHICLES_COUNT`, `FUEL_TX_COUNT`, `FUEL_VOLUME`, `LOGISTICS_ORDERS`
- `value`, `limit_value`, `overage`

## Tariff definition format

Stored in `crm_tariff_plans.definition`:

```json
{
  "base_fee": { "amount": 500000, "currency": "RUB" },
  "included": { "cards": 50, "vehicles": 30, "fuel_tx": 1000 },
  "overage": {
    "cards": { "price": 2000 },
    "vehicles": { "price": 3000 },
    "fuel_tx": { "price": 50 }
  },
  "features": {
    "fuel": true,
    "logistics": true,
    "risk": "v4",
    "documents": true
  }
}
```

## Billing flow

Daily job:

`run_subscription_billing_job(today)`:

1. Picks active subscriptions where `today.day == billing_day`.
2. Resolves billing period as the previous calendar month.
3. Calls `run_subscription_billing(period_id)` for that month.

`run_subscription_billing(period_id)`:

1. Loads active subscriptions whose `billing_day` matches the period start.
2. Collects usage counters.
3. Calculates base fee and overage charges.
4. Creates invoice + documents (subscription invoice + act).
5. Posts to ledger and audits charges/job.

Risk decisions do not block billing, but mark the invoice for review via audit.

## Audit events

- `SUBSCRIPTION_BILLING_RUN_STARTED`
- `SUBSCRIPTION_CHARGES_COMPUTED`
- `SUBSCRIPTION_INVOICE_CREATED`
- `SUBSCRIPTION_INVOICE_ISSUED`
- `SUBSCRIPTION_BILLING_RUN_COMPLETED`
