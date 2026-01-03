# Finance negative scenarios (integration + runbook)

This runbook covers four deterministic negative scenarios for the finance contour:

- **SCN-1 Partial payment** — verify PARTIALLY_PAID → PAID, outstanding amount, ledger balance, idempotency.
- **SCN-2 Overdue** — invoice transitions to OVERDUE and can be paid after overdue, with audit trail.
- **SCN-3 Cancel/Void** — cancellation is allowed only from permitted states, idempotent, and excluded from settlement.
- **SCN-4 Refund after SLA penalty** — SLA breach → penalty/credit → payment → refund, with balanced ledger and settlement adjustment.

## Integration tests (recommended)

```cmd
pytest platform/processing-core/app/tests/integration/test_finance_negative_scenarios.py
```

If you run tests inside docker-compose CI:

```cmd
docker-compose -f docker-compose.test.yml run --rm processing-core pytest platform/processing-core/app/tests/integration/test_finance_negative_scenarios.py
```

## Manual run (Windows CMD)

> Tip: run each scenario with a **fresh invoice**. The easiest way is to reset the stack
> (`docker-compose down -v` → `docker-compose up -d`) between scenarios.

### 0) Prerequisites

Start the stack locally (core + auth-host + postgres) and ensure `http://localhost` is reachable.

Run the helper script if you want the SCN-1 flow automated:

```cmd
scripts\\smoke_finance_negative_scenarios.cmd
```

### 1) Get tokens

```cmd
set AUTH_URL=http://localhost:8002/api/v1/auth/login

rem Admin token
curl -s -X POST "%AUTH_URL%" -H "Content-Type: application/json" -d "{\"email\":\"admin@example.com\",\"password\":\"admin123\"}" > admin_token.json
python -c "import json,sys; data=json.load(open('admin_token.json')); sys.stdout.write(data.get('access_token',''))" > admin_token.txt
set /p ADMIN_TOKEN=<admin_token.txt

rem Client token (demo client from auth-host, required for refunds endpoint)
curl -s -X POST "%AUTH_URL%" -H "Content-Type: application/json" -d "{\"email\":\"client@neft.local\",\"password\":\"client\"}" > client_token.json
python -c "import json,sys; data=json.load(open('client_token.json')); sys.stdout.write(data.get('access_token',''))" > client_token.txt
set /p CLIENT_TOKEN=<client_token.txt
```

If the demo client is missing, use any client credentials available in your auth-host DB.

### 2) Seed demo billing data and pick an invoice

```cmd
set CORE_ADMIN=http://localhost/api/v1/admin/billing

curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" -X POST "%CORE_ADMIN%/seed" > seed.json
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" "%CORE_ADMIN%/invoices?client_id=demo-client" > invoices.json

for /f %%A in ('powershell -NoLogo -Command "(Get-Content invoices.json | ConvertFrom-Json).items[0].id"') do set INVOICE_ID=%%A
```

### SCN-1 Partial payment (admin finance endpoint)

```cmd
set CORE_PUBLIC=http://localhost/api/v1

rem partial payment 4000
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" ^
  -X POST "%CORE_PUBLIC%/admin/finance/payments" ^
  -d "{\"invoice_id\":\"%INVOICE_ID%\",\"amount\":4000,\"currency\":\"RUB\",\"idempotency_key\":\"scn1-pay-1\"}" > scn1_partial.json

rem idempotent replay (same idempotency_key)
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" ^
  -X POST "%CORE_PUBLIC%/admin/finance/payments" ^
  -d "{\"invoice_id\":\"%INVOICE_ID%\",\"amount\":4000,\"currency\":\"RUB\",\"idempotency_key\":\"scn1-pay-1\"}" > scn1_partial_replay.json

rem final payment 6000
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" ^
  -X POST "%CORE_PUBLIC%/admin/finance/payments" ^
  -d "{\"invoice_id\":\"%INVOICE_ID%\",\"amount\":6000,\"currency\":\"RUB\",\"idempotency_key\":\"scn1-pay-2\"}" > scn1_full.json
```

Expected:
- invoice status becomes `PARTIALLY_PAID` after the first payment and `PAID` after the final payment.
- repeating the same idempotency key does not create a duplicate payment.

### SCN-2 Overdue

```cmd
rem mark invoice overdue
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" ^
  -X POST "%CORE_ADMIN%/invoices/%INVOICE_ID%/status" ^
  -d "{\"status\":\"OVERDUE\",\"reason\":\"overdue_check\"}" > scn2_overdue.json
```

Expected:
- invoice status becomes `OVERDUE` (audit event `INVOICE_STATUS_CHANGED`).
- after payment, it transitions to `PAID`.

### SCN-3 Cancel/Void

```cmd
rem cancel invoice
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" ^
  -X POST "%CORE_ADMIN%/invoices/%INVOICE_ID%/status" ^
  -d "{\"status\":\"CANCELLED\",\"reason\":\"void\"}" > scn3_cancel.json
```

Expected:
- invoice status becomes `CANCELLED`.
- repeat cancel is idempotent (no extra transition logs).

### SCN-4 Refund after SLA penalty

This scenario requires a fresh invoice and a deterministic SLA breach. The integration test is the most reliable
way to validate the SLA + finance interplay. To run manually:

1. Create the SLA breach and penalty in Python (service-level, no DB edits):

```cmd
python -c "from datetime import datetime, timedelta, timezone; from app.db import get_sessionmaker; from app.models.marketplace_contracts import Contract, ContractObligation, ContractStatus; from app.models.marketplace_order_sla import MarketplaceOrderEvent; from app.services.order_sla_service import evaluate_order_event; from app.services.order_sla_consequence_service import apply_sla_consequences; from app.services.audit_service import RequestContext; from app.models.audit_log import ActorType; ctx=RequestContext(actor_type=ActorType.USER, actor_id='cli', actor_roles=['ADMIN'], tenant_id=1); Session=get_sessionmaker(); db=Session(); contract=Contract(contract_number='C-SLA-CLI', contract_type='service', party_a_type='client', party_a_id='22222222-2222-2222-2222-222222222222', party_b_type='partner', party_b_id='33333333-3333-3333-3333-333333333333', currency='USD', effective_from=datetime.now(timezone.utc)-timedelta(days=1), effective_to=None, status=ContractStatus.ACTIVE.value, audit_event_id='11111111-1111-1111-1111-111111111111'); obligation=ContractObligation(contract_id=contract.id, obligation_type='response', metric='response_time', threshold='30', comparison='<=', window='order', penalty_type='credit', penalty_value='1500'); db.add(contract); db.flush(); obligation.contract_id=contract.id; db.add(obligation); db.commit(); created=MarketplaceOrderEvent(order_id='order-cli', client_id='22222222-2222-2222-2222-222222222222', partner_id='33333333-3333-3333-3333-333333333333', event_type='MARKETPLACE_ORDER_CREATED', occurred_at=datetime.now(timezone.utc)-timedelta(minutes=33)); accepted=MarketplaceOrderEvent(order_id='order-cli', client_id='22222222-2222-2222-2222-222222222222', partner_id='33333333-3333-3333-3333-333333333333', event_type='MARKETPLACE_ORDER_CONFIRMED_BY_PARTNER', occurred_at=datetime.now(timezone.utc)); db.add_all([created, accepted]); db.commit(); summary=evaluate_order_event(db, order_event_id=str(accepted.id), request_ctx=ctx); db.commit(); apply_sla_consequences(db, evaluation_id=str(summary.violations[0].id), request_ctx=ctx); db.commit(); db.close()"
```

2. Apply credit note via admin finance, then pay and refund (use a fresh invoice id):

```cmd
rem credit note (SLA penalty)
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" ^
  -X POST "%CORE_PUBLIC%/admin/finance/credit-notes" ^
  -d "{\"invoice_id\":\"%INVOICE_ID%\",\"amount\":1500,\"currency\":\"USD\",\"reason\":\"sla_penalty\",\"idempotency_key\":\"scn4-credit-1\"}" > scn4_credit.json

rem pay remainder
curl -s -H "Authorization: Bearer %ADMIN_TOKEN%" -H "Content-Type: application/json" ^
  -X POST "%CORE_PUBLIC%/admin/finance/payments" ^
  -d "{\"invoice_id\":\"%INVOICE_ID%\",\"amount\":8500,\"currency\":\"USD\",\"idempotency_key\":\"scn4-pay-1\"}" > scn4_pay.json

rem refund part of the paid amount
curl -s -H "Authorization: Bearer %CLIENT_TOKEN%" -H "Content-Type: application/json" ^
  -X POST "%CORE_PUBLIC%/invoices/%INVOICE_ID%/refunds" ^
  -d "{\"amount\":2000,\"external_ref\":\"SCN4-REFUND\",\"provider\":\"bank_stub\"}" > scn4_refund.json
```

Expected:
- audit events include `SLA_BREACH_DETECTED`, `SLA_CONSEQUENCE_APPLIED`, `CREDIT_NOTE_ALLOCATED`, `REFUND_ALLOCATED`.
- ledger remains balanced (double-entry) for credit, payment, and refund.
- settlement net remains non-negative.

## Troubleshooting

- **403 on payments/refunds**: check that the JWT contains a `client_id` matching the invoice client.
- **409 invalid transition**: ensure the invoice is in `SENT`/`PARTIALLY_PAID`/`OVERDUE` before payment.
- **Ledger imbalance**: check `internal_ledger_entries` for the ledger transaction created for the payment/refund.
