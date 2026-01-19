# G1 Production Gate — MoR Readiness

G1 is **READY** only if every checklist item below is completed.

## Checklist (P0)

- [ ] Load test passed (`scripts/load_mor_settlement.py`) and recorded in `docs/ops/load_test_mor.md`.
- [ ] E2E overdue → payment → unblock → payout passed (`scripts/smoke_mor_e2e_prod.cmd`).
- [ ] Alerts enabled in production (see `docs/ops/mor_ops_alerts.md`).
- [ ] Grafana dashboard **MoR Ops** is live and readable in under 30 seconds.
- [ ] Finance negative scenarios reviewed (`docs/ops/finance_negative_scenarios.md`).
- [ ] Ops runbooks published (`docs/ops/mor_ops_runbook.md`).
- [ ] Admin override policy approved.

## Release rule

❌ **Do not release** if any checkbox above is not completed.

## Status after G1

| Area | Status |
| --- | --- |
| Client portal | ✅ |
| Partner core | ✅ |
| Partner monetization | ✅ |
| MoR finance | ✅ |
| Trust layer | ✅ |
| Runtime invariants | ✅ |
| Production readiness | 🔒 READY |
