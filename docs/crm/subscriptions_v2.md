# Subscriptions v2

## Workflow

1. Build subscription segments for the billing period.
2. Collect usage counters per segment.
3. Apply tariff proration and metric rules deterministically.
4. Upsert segment-aware charges.
5. Ensure invoice (idempotent) and issue documents.
6. Emit a money flow event linked to the invoice.

## Admin endpoints

- `POST /api/v1/admin/crm/subscriptions/{id}/preview-billing?period_id=...`
- `POST /api/v1/admin/crm/subscriptions/{id}/change-tariff`
- `POST /api/v1/admin/crm/subscriptions/{id}/pause`
- `POST /api/v1/admin/crm/subscriptions/{id}/resume`
- `POST /api/v1/admin/crm/subscriptions/{id}/cancel`

## Idempotency keys

- Charge key: `sub:{sub_id}:period:{period_id}:seg:{seg_start}-{seg_end}:code:{BASE|OVERAGE|RULE_ADJ}:{metric}`
- Invoice key: `subscription:{sub_id}:period:{period_id}:v2`
- Money flow key: `money:subscription:{sub_id}:period:{period_id}:invoice:{invoice_id}:v2`

