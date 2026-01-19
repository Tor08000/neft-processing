# Sprint G1 Production Gate (MoR)

G1 is **DONE** only if all checks below are green.

## 1) E2E MoR smoke (required)

Run:

```cmd
scripts\smoke_mor_e2e_prod.cmd
```

**Pass criteria**

- Scenario A: client pays → order completed → settlement finalized → partner earns → payout requested → payout approved → balances 0
- Scenario B: invoice overdue → entitlements blocked → payment approved → entitlements recompute → settlement → payout
- Scenario C: SLA breach → penalty applied **before** payout → partner_net reduced → payout reflects penalty

## 2) Load test (required)

Run:

```cmd
python scripts\load_mor_settlement.py
```

**Pass criteria**

- No drift between settlement snapshot, partner ledger, platform revenue
- No double payout possible
- No negative balance without explicit reason

Record results in `docs/ops/load_test_mor.md`.

## 3) Ops runbooks (required)

Must be up-to-date and validated:

- `docs/ops/mor_ops_runbook.md`
- `docs/ops/finance_negative_scenarios.md`

## 4) Alerts enabled (required)

- Prometheus rules: `infra/prometheus_rules_mor.yml`
- Grafana dashboard: `infra/grafana/mor_prod_dashboard.json`

## 5) Runtime invariants enforced (required)

- `docs/ops/mor_runtime_invariants.md` is FINAL
- Violations emit audit events and increment metrics

## 6) Admin operational abilities (required)

Admin must be able to:

- unblock overdue client access
- explain payout block to partner
- resolve double payment
- address penalty dispute
- apply admin override with audit trail

## Release decision

G1 can be released only when all sections above are verified and signed off by
Ops + Finance.
