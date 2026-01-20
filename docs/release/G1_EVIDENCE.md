# G1 Evidence Pack — Sprint E/F (MoR Runtime Hardening)

## Финальный E2E сценарий

**Команда**

```cmd
scripts\smoke_mor_e2e_full.cmd
```

**Ожидаемый результат**

- `SMOKE_MOR_E2E_FULL: PASS`
- Логи: `logs/smoke_mor_e2e_full_*.log`

**Проверки (assertions)**

- ❌ exports запрещены при `OVERDUE`
- ✅ exports разрешены после `PAID`
- ❌ payout до `finalized_at`
- ✅ payout только после settlement snapshot
- ledger / revenue / payout сходятся с snapshot

## Load test

**Команда**

```cmd
python scripts\load_mor_settlement.py ^
  --orders 10000 ^
  --partners 100 ^
  --payout-batches 100 ^
  --runs 3
```

**PASS критерии**

- `settlement_immutable_violation_total == 0`
- no double payout
- no negative partner balances without reason
- payout batching стабильный
- нет drift между snapshot / ledger / revenue

**Отчёты**

- JSON: `reports/load_mor_settlement.json`
- CSV: `reports/load_mor_settlement.csv`
- Runbook: `docs/ops/load_test_mor.md`

## Alerts & Grafana

**Alerts**

- `core_api_mor_settlement_immutable_violation_total > 0`
- `core_api_mor_payout_pending_over_threshold > 0`
- `core_api_mor_settlement_override_total` (admin override spike)
- `core_api_mor_payout_failed_total` / payout delay

**Dashboard**

- Grafana: **MoR Ops** (`infra/grafana/mor_prod_dashboard.json`)
- Alert rules: `docs/ops/mor_ops_alerts.md`

## Release gate

**Checklist**

- [ ] Immutable settlement
- [ ] Payout safety
- [ ] Negative scenarios runtime
- [ ] Admin ops ready
- [ ] E2E PASS
- [ ] Load test PASS
- [ ] Alerts active

**Дата:** ____________________

**Ответственный:** ____________________
