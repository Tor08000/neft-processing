# OPS 17 — Billing Enforcement → Unblocking

## Goal
Prove that billing status enforces real access control and payment automatically restores access (end-to-end).

## Actors & Roles
- Finance
- Sales
- Admin/Ops
- Client (Org owner)

## Prerequisites
- Core API running with `postgres`.
- Admin portal access.
- An org with overdue invoice and subscription in `OVERDUE`.

## Baseline State (DEBT)
**Client**
- Org: ООО Ромашка
- Plan: CONTROL family, resolved to an active monthly `CONTROL_*` SKU from the live subscriptions catalog
- Subscription: `OVERDUE`
- Invoice: `ISSUED → DUE → OVERDUE`

**Entitlements snapshot (examples)**
```json
{
  "exports": { "allowed": false, "reason": "billing_overdue" },
  "integrations": { "allowed": false },
  "analytics": { "allowed": true, "mode": "read_only" },
  "cards_write": false
}
```

**Runtime enforcement (server-side, not only UI)**
- Export CSV/XLSX → ❌ blocked (`403 billing_blocked`).
- Export ETA / streaming → ❌ blocked.
- Scheduled reports → ⏸ skipped.
- Helpdesk outbound → ❌ blocked.
- Fleet write ops → ❌ blocked.
- Analytics → ✅ read-only.
- Invoices → ✅ read.

## Payment Intake (manual)
1. Client opens invoice in portal.
2. Clicks **Report payment**.
3. Uploads payment proof.
4. Status: `payment_intake = PENDING`.

## Bank Reconciliation (preferred)
1. Admin uploads bank statement (`CSV / 1C / MT940`).
2. Import → Parse → Match.
3. Auto-match found (`invoice_id + amount`).
4. Auto-approve.

## Unblocking (automatic)
**Trigger**
- `payment_intake.status = APPROVED`, or
- bank transaction matched → auto-approve.

**State transitions**
1. Invoice: `ISSUED → PAID`.
2. Subscription: `OVERDUE → ACTIVE`.
3. Entitlements v2: `recompute_entitlements(org_id)` → new snapshot, hash changed.

**Entitlements snapshot after recompute (example)**
```json
{
  "exports": { "allowed": true },
  "integrations": { "allowed": true },
  "analytics": { "allowed": true },
  "cards_write": true
}
```

**Runtime effects**
- Guards stop blocking.
- Scheduled jobs resume.
- UI refreshes immediately.

**Notifications**
- Client: “Payment received, access restored.”
- Admin: audit + revenue metrics.
- Support: auto-ticket “Billing resolved” (if suspended).

## Proof / Control Point
- `GET /api/v1/client/me` → `entitlements.org_status = ACTIVE`.
- `POST /api/v1/client/exports` → succeeds.
- `POST /api/v1/client/reports` → job created.
- `GET /api/v1/admin/revenue/summary` → `overdue=0`.

## SOP — “Close overdue client in 3 clicks”
**Role:** Finance / Sales / Admin

### Step 1 — Find overdue
Admin UI → Finance → Revenue
- Filter: `Status = OVERDUE`, `Bucket = 7–14 days`.
- Click client → invoice, amount, suspend date, payment intake status.

### Step 2 — Confirm payment
- **Option A:** Payment intake already exists.
  - Open intake → verify proof → **Approve**.
- **Option B:** Bank statement arrived.
  - Admin → Reconciliation → Upload statement → Auto-match → Apply.

### Step 3 — Done
System does it automatically:
- Invoice → `PAID`.
- Subscription → `ACTIVE`.
- Entitlements → recompute.
- Access → restored.
- Notifications → sent.

Sales can tell the client: “Access restored, everything works.”

## UI Flow
**Admin portal**
- Finance → Revenue (overdue list).
- Billing → Payment intakes (approve).
- Reconciliation → Upload statement → Match.

## API Flow
1. `GET /api/v1/admin/revenue/overdue` — find overdue orgs.
2. `GET /api/v1/admin/billing/payment-intakes?status=PENDING` — list intakes.
3. `POST /api/v1/admin/billing/payment-intakes/{id}/approve` — approve payment.
4. `POST /api/core/v1/admin/reconciliation/external/statements` — upload bank statement.
5. `POST /api/core/v1/admin/reconciliation/run` — run reconciliation.
6. `GET /api/v1/client/me` — verify entitlements snapshot.

## DB Touchpoints
- `billing_invoices`, `billing_payment_intakes`.
- `org_subscriptions` / `subscription_invoices`.
- `org_entitlements_snapshot`.
- `audit_log`.

## Events & Audit
- `PAYMENT_INTAKE_APPROVED`.
- `INVOICE_MARKED_PAID`.
- `SUBSCRIPTION_STATUS_CHANGED`.
- `commercial_entitlements_recomputed`.

## Security / Gates
- Admin permissions required (`admin:billing:*`, `admin:reconciliation:*`).
- Client permissions enforced by entitlements at runtime.

## Failure modes
- Intake already approved → `409 already_approved`.
- Invoice missing → `404 invoice_not_found`.
- Statement already uploaded → `409 statement_already_uploaded`.

## VERIFIED
- pytest: `platform/processing-core/app/tests/integration/test_finance_negative_scenarios.py` (SCN-2 overdue → paid).
- pytest: `platform/processing-core/app/tests/test_client_me_api.py` (entitlements ACTIVE).
- smoke cmd: `scripts/smoke_billing_enforcement_unblock.cmd` (delegates to real `scripts/smoke_commerce_overdue_unblock_e2e.cmd` flow).
- PASS: overdue invoice transitions to paid; entitlements snapshot updated; access restored.
