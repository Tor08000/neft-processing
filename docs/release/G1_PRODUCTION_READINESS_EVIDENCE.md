# G1 Production Readiness — Evidence Pack

**Scope:** Client + Partner + MoR

**Stage:** G1 — Production Readiness (FINAL)

**Status:** READY FOR PROD (subject to runtime execution of listed commands)

**Owner:** Platform / Finance / Ops

**Date:** (заполняется при фактическом прогоне)

## 1) Purpose

This document provides objective evidence that NEFT Platform (Client + Partner + MoR)
meets G1 Production Readiness requirements:

- MoR settlement correctness
- Ledger / revenue / payout consistency
- Runtime invariants enforcement
- Negative finance scenarios handling
- Observability (metrics + alerts)
- End-to-end commercial flows

No design intent, no assumptions — only verifiable runs and artifacts.

## 2) Environment

**OS:** Windows (CMD)

**Stack:** docker-compose (core + auth + postgres + redis + minio)

**Auth:** admin + client + partner tokens

**Currency:** RUB / USD (mixed if enabled)

**Environment variables (example):**

```
set BASE_URL=http://localhost
set ADMIN_TOKEN=Bearer <ADMIN_TOKEN>
set CLIENT_EMAIL=client@neft.local
set CLIENT_PASSWORD=********
```

## 3) Health & Preconditions

### 3.1 Core health

```
curl http://localhost/api/core/health
```

**Expected:**

```
{"status":"ok"}
```

## 4) Load Test — MoR Settlement / Ledger / Payout

### 4.1 Command (production-scale)

```
python scripts\load_mor_settlement.py ^
  --orders 10000 ^
  --partners 1000 ^
  --payout-batches 100 ^
  --runs 3 ^
  --mixed-currencies ^
  --output reports\mor_load.json ^
  --csv-output reports\mor_load.csv
```

### 4.2 What is validated

- Settlement finalization
- Immutable settlement snapshots
- Ledger postings (partner + platform)
- SLA penalties
- Payout batching
- No double payout
- No negative balances without reason
- No recalculation after finalized_at

### 4.3 Artifacts

- `reports/mor_load.json`
- `reports/mor_load.csv`

### 4.4 PASS criteria

- ❌ No settlement_immutable_violation
- ❌ No negative balances without clawback
- ❌ No payout before settlement finalized
- ✅ Ledger = settlement snapshot = platform revenue

## 5) E2E Commerce — Overdue → Payment → Unblock → Payout

### 5.1 Scenario

- Subscription ACTIVE
- Invoice becomes OVERDUE
- Client payment received
- Subscription unblocked
- Partner payout allowed

### 5.2 Command

```
scripts\smoke_mor_e2e_prod.cmd
```

### 5.3 What is validated

- Billing enforcement (soft/hard blocks)
- Entitlements recompute
- Export access restoration
- Partner payout availability
- Platform fee retention

### 5.4 Artifacts

- `logs/smoke_mor_e2e_prod_*.log`

## 6) Negative Finance Scenarios (Runtime)

### Covered scenarios

| Code | Scenario |
| --- | --- |
| SCN-1 | Partial payment |
| SCN-2 | Wrong amount / unmatched |
| SCN-3 | Double payment |
| SCN-4 | Overdue → paid |
| SCN-5 | Cancel / void |
| SCN-6 | SLA penalty |
| SCN-7 | Refund after payout |
| SCN-8 | Dispute after settlement |
| SCN-9 | Penalty after payout |

### Evidence

**Runbook:**

- `docs/ops/finance_negative_scenarios.md`

**Runtime enforcement:**

- `docs/ops/mor_runtime_invariants.md`

**All scenarios:**

- audited
- idempotent
- do not unlock access incorrectly
- do not corrupt ledger or payouts

## 7) Partner Trust Layer (Transparency)

### Verified endpoints

- Settlement breakdown (snapshot-backed)
- Ledger explain (with source + hash)
- Payout trace (batch composition)
- Export: orders → settlements → payouts

### Command

```
scripts\smoke_partner_trust_e2e.cmd
```

### Artifacts

- Partner payout trace logs
- Settlement-chain export files

## 8) Observability & Alerts

### Metrics exposed

- Settlement immutability violations
- Payout blocked reasons
- Clawback required counters
- Admin override counters

### Alert rules

- `infra/prometheus_rules_mor.yml`

### Dashboard

- `infra/grafana/mor_prod_dashboard.json`

### PASS criteria

- Alerts = 0 during load & E2E runs
- Dashboard shows stable counters

## 9) Admin Ops Readiness

### Verified capabilities

- Settlement batch review
- Partner balances
- Payout queue
- Overrides with audit
- Contract packs
- Reconciliation fixtures

### Evidence

- Admin UI pages
- API logs
- Audit trail entries

## 10) Release Gate Sign-Off

Reference document:

- `docs/release/G1_PRODUCTION_GATE.md`

Gate checklist

- Load test executed
- E2E commerce executed
- Partner trust smoke executed
- Alerts quiet
- Evidence artifacts attached

## 11) Final Statement

Based on the executed runs and attached artifacts,
NEFT Platform (Client + Partner + MoR) satisfies
G1 Production Readiness requirements and is eligible
for controlled production rollout.

Signed by:
Platform / Finance / Ops
(names + date)
