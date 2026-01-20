# G1 Production Gate — MoR Readiness

G1 is **READY** only if every checklist item below is completed.

## Checklist (P0)

- [x] Immutable settlement (snapshot immutability enforced; no violations).
- [x] Payout safety (payout only after snapshot/finalize).
- [x] Negative scenarios runtime reviewed (`docs/ops/finance_negative_scenarios.md`).
- [x] Admin ops ready (runbooks + override policy approved).
- [x] E2E PASS (`scripts/smoke_mor_e2e_full.cmd`).
- [x] Load test PASS (`scripts/load_mor_settlement.py`) and recorded in `docs/ops/load_test_mor.md`.
- [x] Alerts active in production (`docs/ops/mor_ops_alerts.md`).
- [x] Grafana dashboard **MoR Ops** is live and readable in under 30 seconds.

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
