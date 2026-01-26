# Admin Portal + Partner Portal — Master Backlog (P0–P2)

Source of truth: **SSoT** payloads must drive UI behavior. Admin UI must rely solely on `GET /api/core/v1/admin/me`. Partner Portal must rely solely on `GET /api/core/portal/me`.

## 🟥 P0 — Критический контур (инварианты, деньги, контроль)

### A. Admin Portal — P0

**A1. Admin SSoT bootstrap**
- Title: Admin SSoT `/api/core/v1/admin/me` — канон
- Why: UI не имеет права гадать
- API: `GET /api/core/v1/admin/me`
- DoD:
  - возвращает `roles`, `permissions`, `environment`, `read_only`
  - UI строится только по этому ответу
- Smoke:
  - `curl -i http://localhost/api/core/v1/admin/me -H "Authorization: Bearer <ADMIN_TOKEN>"`

**A2. Global read-only mode**
- Why: инциденты / ночь / регламент
- API: `/api/core/v1/admin/me → read_only=true`
- DoD: все write-кнопки disabled, backend запрещает writes
- Smoke: попытка write → `403 + reason_code=READ_ONLY`

**A3. OPS Runtime Center — health aggregation**
- Why: ответ «жива ли платформа?» ≤ 60 сек
- API: `GET /api/core/admin/runtime/summary`
- DoD: settlement/payout queues, MoR metrics, critical flags
- Smoke: endpoint → 200 без DB writes

**A4. OPS — immutable violations feed**
- Why: ловить инварианты до денег
- API: `GET /api/core/admin/runtime/violations`
- DoD: список нарушений + `correlation_id`
- Smoke: violation → видна в UI

**A5. FINANCE — invoices list + status**
- Why: понять “почему OVERDUE”
- API: `GET /api/core/admin/invoices`
- DoD: `ISSUED / PAID / OVERDUE + dunning timeline`
- Smoke: invoice OVERDUE виден с причиной

**A6. FINANCE — manual payment intake**
- Why: ручные переводы без разработчика
- API: `POST /api/core/admin/payments/intake`
- Rules: `reason + audit` обязательны
- DoD: защита от double/partial
- Smoke: double submit → rejected

**A7. FINANCE — payout queue**
- Why: главный денежный контроль
- API: `GET /api/core/admin/payouts/queue`
- DoD: видны причины блокировок
- Smoke: blocked payout → причина отображается

**A8. FINANCE — payout approve/reject**
- Why: ручное управление деньгами
- API: `POST /api/core/admin/payouts/{id}/approve|reject`
- Rules: no settlement → no approve
- Smoke: approve без settlement → 409

**A9. FINANCE — settlement snapshot viewer**
- Why: “почему не платится?”
- API: `GET /api/core/admin/settlements/{id}`
- DoD: gross/fee/penalty/net immutable
- Smoke: snapshot readonly

**A10. AUDIT — unified audit feed**
- Why: всё объяснимо
- API: `GET /api/core/admin/audit`
- DoD: фильтры money/auth/override
- Smoke: любое write → audit event

**A11. Audit correlation chain**
- Why: расследование инцидентов
- API: `GET /api/core/admin/audit/{correlation_id}`
- DoD: цепочка действий видна целиком

### B. Partner Portal — P0

**B1. Partner SSoT via `/portal/me`**
- Why: единый вход без второго логина
- API: `GET /api/core/portal/me`
- DoD: partner_profile + finance_state
- Smoke: partner token → корректный payload

**B2. Partner Dashboard (finance summary)**
- Why: прозрачность доходов
- API: `GET /api/core/partner/dashboard`
- DoD: balance / pending / blocked / penalties
- Smoke: balance сходится с ledger

**B3. Partner Ledger (read-only)**
- Why: источник правды
- API: `GET /api/core/partner/ledger`
- DoD: начисления / штрафы / удержания
- Smoke: сумма = balance

**B4. Partner Payout preview**
- Why: “почему столько?”
- API: `GET /api/core/partner/payouts/preview`
- DoD: причины блокировок видны
- Smoke: blocked → reason shown

**B5. Partner request payout**
- Why: самосервис
- API: `POST /api/core/partner/payouts/request`
- Rules: threshold / legal OK
- Smoke: illegal state → 409

**B6. Partner Documents**
- Why: финальная прозрачность
- API: `GET /api/core/partner/docs`
- DoD: invoices/acts/appendixes
- Smoke: download signed URL

## 🟧 P1 — Управление и масштабирование

### Admin Portal — P1

**A12. COMMERCIAL — plans & add-ons**
- Why: продажи без dev
- API: `GET /api/core/admin/plans`
- Rules: dry-run available
- Smoke: dry-run ≠ apply

**A13. Feature overrides**
- Why: ручное включение/выключение
- API: `GET /api/core/admin/overrides`
- Rules: audit + reason
- Smoke: override visible in SSoT

**A14. LEGAL — contract packs**
- Why: юр. контроль
- API: `GET /api/core/admin/contracts`
- Smoke: history visible

**A15. Partner legal status**
- Why: блокировки выплат
- API: `GET /api/core/admin/partners/{id}/legal`
- Smoke: LEGAL_BLOCK → payout blocked

**A16. SUPPORT — tickets (readonly)**
- Why: support без риска
- API: `GET /api/core/admin/tickets`
- DoD: no writes allowed

**A17. Admin RBAC enforcement tests**
- Why: OPS ≠ FINANCE
- DoD: backend rejects invalid role

### Partner Portal — P1

**B7. Orders / Services list**
- Why: источник дохода
- API: `GET /api/core/partner/orders`
- Smoke: SLA timers visible

**B8. SLA penalties explanation**
- Why: “за что штраф?”
- API: `GET /api/core/partner/penalties`
- Smoke: penalty linked to order

**B9. Partner status gating**
- Why: не пугать ошибками
- States: `LEGAL_PENDING / PAYOUT_BLOCKED`
- DoD: UI state, не crash

**B10. Org switcher (Client ↔ Partner)**
- Why: один user — два контекста
- DoD: меню перестраивается

## 🟨 P2 — Комфорт и глубина

### Admin Portal — P2

**A18. Ops diagnostics deep-dive**
- Why: сложные инциденты
- API: `GET /api/core/admin/runtime/details`

**A19. Export audit to CSV**
- Why: регуляторы / разборы

**A20. Admin activity timeline**
- Why: post-mortem

### Partner Portal — P2

**B11. Tax profile**
- Why: корректные выплаты

**B12. Legal document upload**
- Why: ускорение проверки

**B13. Partner notifications**
- Why: SLA/blocked alerts

## 📊 Итог по backlog

| Контур | P0 | P1 | P2 |
| --- | --- | --- | --- |
| Admin | 11 | 6 | 3 |
| Partner | 6 | 4 | 3 |
| Всего | 17 | 10 | 6 |

> Минимально необходимый объём, чтобы:
> - Admin Portal реально управлял деньгами и инвариантами
> - Partner Portal стал прозрачным денежным кабинетом
> - система не требовала разработчика для операционных решений
