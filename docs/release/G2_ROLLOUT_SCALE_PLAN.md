# G2 — Rollout & Scale Plan (Client + Partner + MoR)

## Цель G2
Перевести NEFT Platform из состояния «готово к продакшену» в состояние
«стабильно работающая, масштабируемая, коммерчески управляемая платформа»
без деградации доверия, денег и операций.

## 0) Принципы G2 (не обсуждаются)

### Scale ≠ Feature
В G2 мы не добавляем новые фичи — мы:
- расширяем охват,
- увеличиваем объёмы,
- ужесточаем контроль.

### Every rollout is reversible
Любой шаг должен:
- иметь feature-flag / org-scope,
- иметь rollback без миграций данных.

### Money first
Любая деградация:
- сначала бьёт по выплатам/деньгам,
- потом по UX,
- никогда наоборот.

## 1) G2-A — Controlled Rollout (P0)

### Цель
Запустить реальных клиентов и партнёров в ограниченном контуре, не ломая инварианты MoR.

### 1.1 Scope
- Клиенты: 5–10 компаний
- Партнёры: 3–5 партнёров
- Объём:
  - до 1k заказов / день
  - до 10 payout / день

### 1.2 Включаем
- Client Portal (полный)
- Partner Core + Partner Finance
- MoR settlement + payouts
- Billing enforcement + dunning
- Partner Trust Layer

### 1.3 Ограничения
- ❌ Нет кастомных тарифов
- ❌ Нет сложных SLA tiers
- ❌ Нет массовых ручных override’ов

### 1.4 Feature flags
- mor_enabled=true
- partner_finance_enabled=true
- payouts_auto_approve=false
- mixed_currency=false

### 1.5 Контроль
Ежедневно:
- MoR dashboard (settlement / payout)
- payout queue = 0 в конце дня
- no immutable violations

**Exit criteria G2-A:**
14 дней без:
- ручных фиксов в БД
- payout rollback
- partner disputes

## 2) G2-B — Ops Hardening (P0/P1)

### Цель
Сделать так, чтобы Ops/Finance/Sales могли работать без разработчиков.

### 2.1 Admin Ops must-have
- Settlement batches
- Partner balances
- Payout queue + blockers
- Dunning timeline
- Contract packs
- Reconciliation imports
- Overrides (read/write)

### 2.2 Runbooks (обязательные)
- Billing overdue
- Partner payout blocked
- Double payment
- Penalty after payout
- Partner legal suspended

Все runbook’и:
- пошаговые,
- с API/UI,
- с ожидаемыми инвариантами.

### 2.3 SLA Ops
Alert → runbook → resolution → audit

Никаких «посмотрим завтра».

**Exit criteria G2-B:**
Любой фин/партнёрский инцидент закрывается ≤ 30 минут без dev.

## 3) G2-C — Scale Envelope (P1)

### Цель
Подготовить платформу к росту x10 / x50 без переписывания ядра.

### 3.1 Целевые нагрузки
| Контур | G2 target |
| --- | --- |
| Orders/day | 10k–50k |
| Partners | 100+ |
| Payouts/day | 100–500 |
| Exports | 100k+ rows |

### 3.2 Технические меры
- Async everywhere (уже есть)
- Streaming exports (есть)
- Snapshot-based everything (есть)
- No cross-aggregate recalculation (есть)

Добавить:
- Queue backpressure alerts
- Payout batching limits
- Partner balance caps (safety)

### 3.3 Performance budgets
- Settlement finalize ≤ 500 ms
- Ledger post ≤ 200 ms
- Payout batch finalize ≤ 1 s
- Portal/me ≤ 300 ms p95

## 4) G2-D — Commercial Expansion (P1)

### Цель
Начать осознанно зарабатывать, а не просто «работать».

### 4.1 Включаем
- Add-ons (Helpdesk, ERP, API)
- SLO tiers (A/B/C)
- Custom pricing (через admin only)
- Usage-based billing (ограниченно)

### 4.2 Sales model
- CONTROL — self-serve
- INTEGRATE — assisted
- ENTERPRISE — contract-only

### 4.3 Guardrails
Любой custom deal:
- explicit override,
- audit,
- snapshot.

## 5) G2-E — Partner Confidence (P1)

### Цель
Партнёр не верит словам, он верит цифрам.

### 5.1 Обязательно
- Settlement breakdown per order
- Fee formula visible
- Penalty source visible
- Payout trace end-to-end
- Export chain (CSV/ZIP)

### 5.2 KPI
- <1% payout disputes
- 0 «непонятных» списаний
- Support tickets → self-resolved

## 6) G2-F — Governance & Safety (P0)

### Цель
Платформа переживает ошибки людей.

### 6.1 Mandatory invariants
- No payout without snapshot
- No unlock without PAID
- No recalculation after finalize
- No silent override

### 6.2 Controls
Admin override requires:
- reason
- ticket
- audit

Alerts on:
- override spike
- clawback growth
- payout delay

## 7) G2 Exit Criteria (Go → G3)

Переходим к G3 (Growth / Geography / Automation), если:
- ✅ 30 дней без MoR инцидентов
- ✅ 0 ручных DB правок
- ✅ Ops работает автономно
- ✅ Partner payouts predictable
- ✅ Revenue dashboard сходится с бухгалтерией
