# Admin Portal — Core Development Plan

## Цель
Создать Admin Portal как операционный центр платформы NEFT, обеспечивающий контроль денег, ролей, партнёров и инвариантов MoR без участия разработчиков и без прямого доступа к БД.

## 0️⃣ Общие требования (обязательные)

### Архитектура
- Admin Portal — отдельный frontend (`admin-ui`).
- Backend — только через admin API.
- Никаких прямых DB-операций.

### Требования ко всем write-действиям
- RBAC.
- `reason` (обязательный).
- audit event.
- `correlation_id`.

### Режимы
- Read-only по умолчанию.
- Write-действия:
  - подтверждение;
  - dry-run (где применимо);
  - post-action verify.

## 1️⃣ Sprint A — Admin Shell & Safety (P0)

### Цель
Безопасная основа админки, на которую можно навешивать контуры.

### Задачи

#### Frontend
- AdminShell:
  - глобальный layout;
  - environment badge (prod/stage);
  - текущий admin user + role.
- RBAC-gated navigation:
  - OPS;
  - FINANCE;
  - SALES;
  - LEGAL;
  - SUPERADMIN.
- Read-only mode indicator.
- Global Audit Warning banner.

#### Backend
- `/admin/me`:
  - roles;
  - permissions.
- RBAC middleware (admin).

### DoD
- Админ без роли не видит раздел.
- Ни одна write-кнопка не активна без прав.
- Любой экран знает who / where / why.

## 2️⃣ Sprint B — Ops Runtime Center (P0)

### Цель
За 60 секунд понять: платформа жива или нет.

### Раздел: OPS

#### Backend
Read-only endpoints:
- settlement queue;
- payout queue;
- blocked payouts;
- immutable violations;
- MoR runtime metrics.

#### Frontend
Ops Dashboard:
- queues counters;
- last 24h activity;
- red/yellow flags.
- No actions (diagnostics only).

### DoD
OPS может ответить:
«Где болит?»
без логов и SQL.

## 3️⃣ Sprint C — Finance & MoR Control (P0)

### Цель
Финансы управляются из UI, а не через dev.

### Раздел: FINANCE

#### Backend
Invoices:
- list / detail.

Payments:
- payment intake;
- reconciliation;
- Dunning timeline.

Settlements (snapshot view).

Payout queue:
- reasons for block;
- preview payout.

#### Frontend
Finance Dashboard:
- overdue exposure;
- payout queue.

Invoice detail:
- payments;
- dunning;
- block reason.

Payout review:
- approve / reject.

### DoD
Любой вопрос hooking:
«Почему не платится?»
решается в админке.

## 4️⃣ Sprint D — Commercial & Entitlements Control (P1)

### Цель
Продажи управляют продуктом, не кодом.

### Раздел: COMMERCIAL

#### Backend
Org commercial state:
- plan;
- add-ons;
- support plan;
- SLO tier.

Overrides:
- feature-level.

Entitlements snapshot:
- view;
- recompute.

Change history.

#### Frontend
Org Commercial Page:
- current state;
- planned changes.

Override editor (guarded).

Entitlements viewer (read-only).

### DoD
Любое коммерческое изменение:
- через UI;
- с reason;
- с audit.

Нет «включили временно».

## 5️⃣ Sprint E — Legal & Docs (P1)

### Цель
Юридика и бухгалтерия получают документы, а не объяснения.

### Раздел: LEGAL

#### Backend
Contract packs:
- generate;
- history.

Partner legal status.

Payout gating by legal.

#### Frontend
Legal Dashboard:
- contracts;
- acts;
- legal blocks.

One-click contract pack.

### DoD
- Один источник правды для договора.
- Документы совпадают с деньгами.

## 6️⃣ Sprint F — Audit & Forensics (P0/P1)

### Цель
Разбор инцидентов без паники.

### Раздел: AUDIT

#### Backend
Unified audit feed.

Filters:
- money;
- override;
- partner.

Correlation chain.

#### Frontend
Audit Timeline:
- who / what / why;
- drill-down to entity.

### DoD
- Любое действие можно восстановить.
- Нет «не знаем, кто нажал».

## 7️⃣ Глобальные инварианты Admin Portal

❌ No silent override

❌ No payout without snapshot

❌ No unlock without PAID

❌ No write without audit

✅ Everything explainable

## 8️⃣ Финальный критерий готовности
Admin Portal считается готовым, если:

Любой инцидент в деньгах, партнёрах или доступах
решается без разработчика и без прямого доступа к БД.
