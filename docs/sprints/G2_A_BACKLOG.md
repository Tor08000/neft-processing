# Sprint G2-A — Backlog

Фокус: ограниченный прод-контур (Client + Partner + MoR) без деградации денег, доверия и ops. Только проверка существующей системы в реальной эксплуатации.

## Неделя 1 — Enable & Observe

### Platform / Backend (P0)
- Включение feature-flags org-scope для pilot orgs.
- Проверка `/portal/me` для client+partner ролей.
- Проверка billing enforcement (soft-block).
- Проверка payout gating (threshold / hold).

### Admin Ops (P0)
- Проверка Admin Ops UI:
  - settlement batches.
  - payout queue.
  - partner balances.
- Проверка manual override flows (read-only).

### Finance Ops (P0)
- Проверка invoice lifecycle: ISSUED → PAID → unblock.
- Проверка dunning (due / overdue).
- Проверка payment intake → unblock.

### Partner Ops (P0)
- Partner portal:
  - settlement breakdown.
  - ledger explain.
  - payout preview (blocked/allowed reasons).

### Observability (P0)
- Grafana MoR dashboard доступен.
- Alerts включены (but not paging).

## Неделя 2 — Stress & Resolve

### Platform / Backend (P0)
- Финальный E2E: overdue → payment → unblock → payout.
- Проверка immutability settlement snapshots.
- Проверка no recalculation after finalize.

### Finance Ops (P0)
- SCN-2 / SCN-3 (wrong / double payment).
- Проверка credit / clawback flows.

### Partner Ops (P0)
- Partner payout trace end-to-end.
- Проверка export chain: orders → settlements → payouts.

### Observability (P0)
- Проверка alert firing (test violation).
- Проверка metrics drift = 0.
