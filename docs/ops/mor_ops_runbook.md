# MoR Ops Runbook (Sprint G1)

This runbook is the **minimum** operational guide for MoR incidents. It focuses on
real-money invariants and recovery actions that do not require code changes.

## 1) Overdue client — unblock access

**Goal**: move invoice to `PAID`, recompute entitlements, and confirm access.

### Steps

1. Identify the overdue invoice.

```cmd
set CORE_ADMIN=http://localhost/api/v1/admin/billing
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" "%CORE_ADMIN%/invoices?status=OVERDUE&limit=5"
```

2. Apply payment (full amount).

```cmd
set CORE_PUBLIC=http://localhost/api/v1
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" ^
  -X POST "%CORE_PUBLIC%/admin/finance/payments" ^
  -d "{\"invoice_id\":\"<INVOICE_ID>\",\"amount\":<FULL_AMOUNT>,\"currency\":\"RUB\",\"idempotency_key\":\"ops-overdue-pay-1\"}"
```

3. Verify invoice status is `PAID` and entitlements recompute.

```cmd
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" "%CORE_ADMIN%/invoices/<INVOICE_ID>"
```

### Expected outcome

- Invoice status is `PAID` and `amount_due == 0`.
- Entitlements recompute is triggered (exports/integrations unblocked).

---

## 2) Partner payout blocked

**Goal**: identify blocker and unblock with legal/ops actions.

### Steps

1. Check payout batches for the partner.

```cmd
set CORE_PAYOUTS=http://localhost/api/v1/payouts
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" "%CORE_PAYOUTS%/batches?partner_id=<PARTNER_ID>&limit=5"
```

2. Inspect last payout block reason via audit log.

```cmd
psql "$DATABASE_URL" -c "select created_at, after->>'reasons' as reasons from audit_log where event_type='MARKETPLACE_PAYOUT_BLOCKED' and after->>'partner_id'='<PARTNER_ID>' order by created_at desc limit 5;"
```

3. Resolve blocker:

- `LEGAL_PENDING` → verify legal profile/details and mark verified.
- `DISPUTES_OPEN` → resolve open disputes.
- `MIN_THRESHOLD` / `HOLD_ACTIVE` → wait for threshold or hold period.

### Expected outcome

- New payout batch can be created without `MARKETPLACE_PAYOUT_BLOCKED`.
- `balance_available` remains non-negative.

---

## 3) Double payment

**Goal**: prevent double payout and preserve ledger balance.

### Steps

1. List payments for the invoice.

```cmd
set CORE_PUBLIC=http://localhost/api/v1
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" "%CORE_PUBLIC%/admin/finance/payments?invoice_id=<INVOICE_ID>"
```

2. Verify that the second payment is recorded as `OVERPAID` and creates a credit.

```cmd
psql "$DATABASE_URL" -c "select id, reason, amount from credit_notes where invoice_id='<INVOICE_ID>' order by created_at desc limit 3;"
```

### Expected outcome

- Invoice remains `PAID`.
- Overpayment is stored as credit; no additional payout is created.

---

## 4) Penalty dispute

**Goal**: confirm penalty is applied before payout and reflected in net.

### Steps

1. Inspect the settlement snapshot and item for the order.

```cmd
psql "$DATABASE_URL" -c "select id, penalty_amount, net_partner_amount from marketplace_settlement_items where order_id='<ORDER_ID>';"
psql "$DATABASE_URL" -c "select penalties, partner_net, finalized_at from marketplace_settlement_snapshots where order_id='<ORDER_ID>';"
```

2. Verify payout batch totals reflect the penalty.

```cmd
psql "$DATABASE_URL" -c "select id, total_amount, meta from payout_batches where partner_id='<PARTNER_ID>' order by created_at desc limit 3;"
```

### Expected outcome

- `penalties` > 0 in snapshot **before** payout.
- `partner_net` is reduced and payout reflects reduced net.

---

## 5) Admin override (strictly controlled)

**Goal**: apply override with audit and metric increment.

### Steps

1. Use internal admin tooling to call `override_settlement_snapshot` with a reason.
2. Verify the audit log and metrics.

```cmd
psql "$DATABASE_URL" -c "select created_at, event_type, after->>'reason' as reason from audit_log where event_type='SETTLEMENT_OVERRIDE' order by created_at desc limit 3;"
curl -s http://localhost/metrics | findstr core_api_mor_admin_override_total
```

### Expected outcome

- Audit event `SETTLEMENT_OVERRIDE` exists with the reason.
- `core_api_mor_admin_override_total` increments.
