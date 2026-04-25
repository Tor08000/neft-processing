# NEFT Client Portal (client-web)

Клиентский кабинет размещается как отдельное фронтенд-приложение `frontends/client-portal` и отдается через
gateway по префиксу `/client/`. Это не thin UI над случайными API: текущий shell опирается на единый bootstrap
`GET /api/core/portal/me`, а дальше использует честные client owner surfaces в `processing-core`.

Визуальный owner для shared shell/token language теперь общий для всех порталов:

- canonical visual foundation: `frontends/shared/brand`
- client bridge: `brand/v1/neft-client/tokens.client.css`
- reference doc: [NEFT Visual System](./architecture/NEFT_VISUAL_SYSTEM.md)

## Client CSS owner-aware migration map

`frontends/client-portal/src/index.css` больше нельзя рассматривать как чистый residue bucket. Repo-truth сейчас показывает live families с разным ownership:

- structural bridge:
  - `.card`
  - `.stack`
  - `.card__header`
  - `.card__section`
  - `.section-title`
  - `.card-grid`
  - `.pagination`
  - `.label`
  - `.meta-grid`
- form bridge:
  - `.checkbox-row`
  - `.checkbox-grid`
- feature-owned dynamic:
  - `.achievement-badge*`
  - owner: `frontends/client-portal/src/features/achievements/components/AchievementBadge.tsx`
- feature-owned analytics:
  - `.attention-list*`
  - owner: `frontends/client-portal/src/components/analytics/AttentionList.tsx`

Practical migration rules:

- no selector removal while the family still has mounted consumers
- do not move bridge selectors into shared brand CSS just to hide duplication
- migrate self-contained feature families first
- structural bridge families move only together with a route/page-owner migration
- existing scoped CSS owners should be preferred for future migrations:
  - `frontends/client-portal/src/layout/client-layout.css`
  - `frontends/client-portal/src/pages/DashboardPage.tsx`
  - `frontends/client-portal/src/pages/dashboard/DashboardRenderer.tsx`
  - `frontends/client-portal/src/pages/stations/stations-map.css`

## Canonical seeded accounts and demo policy

Canonical runtime seed truth comes from `platform/auth-host/app/seeds/demo_users.py`:

- `client@neft.local / Client123!`
- `partner@neft.local / Partner123!`
- `admin@neft.local / Neft123!`

Important runtime rule:

- these accounts are canonical seeded users, not automatic hidden demo surfaces
- demo-rich showcase behavior is allowed only when explicit demo mode is enabled (`VITE_DEMO_MODE`) or on explicit showcase contours
- normal client routes must use live backend truth, cached truth, or honest first-use / retry / access-limited states

## Разделение порталов и безопасность

Client Portal — отдельный UI только для клиентов и их сотрудников/водителей. Он не пересекается с Partner Portal
и Admin UI (NEFT Ops). Разрешены только токены клиентской зоны (`subject_type=client_user`, client issuer/audience),
чтобы `superadmin/support/risk/finance` не могли войти в клиентский кабинет через неверный actor contour.

## Сервисы и маршрутизация

- **Static:** gateway проксирует `/client/` и `/client/assets/` в upstream `client-web`.
- **Canonical bootstrap:** `GET /api/core/portal/me` — SSoT для actor/org/subscription/capabilities/access state.
- **Canonical client business namespace:** `/api/core/client/*`.
- **Onboarding-token namespace:** `/api/core/client/v1/onboarding/*` and `/api/core/client/docflow/*` are pass-through gateway routes guarded by processing-core onboarding tokens, not regular client JWT auth.
- **Compatibility bootstrap wrapper:** `GET /api/core/client/me` — client-focused wrapper over the same portal payload.
- **Legacy/public business family:** `/api/client/*` — still mounted for compatibility/public consumers where migration is incomplete; this family is not the bootstrap owner.
- **Auth:** client login/session still go through `auth-host`.

## Типы клиентов и shell composition

Client shell now differentiates actors by `org.org_type` from `/api/core/portal/me`:

- `INDIVIDUAL` — personal client mode with reduced finance/team surface.
- `BUSINESS` — company mode with broader finance/team/management surface.

Frontend must derive this segmentation from bootstrap truth only; it must not invent a second client-kind source.

## Онбординг

Текущий canonical flow:

- frontend `/onboarding*`
- backend `/api/core/client/onboarding/*`

Legacy `/connect*` routes remain compatibility redirects into the same onboarding contour and must not become a second owner surface.

Commercial-layer endpoints `/api/client/onboarding/state` and `/api/client/onboarding/step` still exist as compatibility/public state helpers, but they are not the primary authenticated onboarding owner.

## API клиента

Практически важные owner surfaces для client portal сегодня:

- `GET /api/core/portal/me` — bootstrap, access state, `org.org_type`, subscription, capabilities.
- `GET /api/core/client/dashboard` — grounded dashboard data.
- `GET /api/core/client/invoices` and `GET /api/core/client/invoices/{invoice_id}` — canonical client-portal-v1 subscription invoice surface.
- `GET /api/core/client/documents*` — canonical general documents surface.
- `GET /api/core/client/docs/*` — client-portal read/download projections for contracts, invoices, acts, and generic downloadable artifacts.
- `GET /api/core/client/onboarding/*` — authenticated onboarding.
- `GET /api/client/fleet/*` — current mounted fleet owner surface; this family is still public/live and has not been handed off to a core-prefixed namespace.
- `GET /api/marketplace/client/recommendations` and `POST /api/marketplace/client/events` — canonical marketplace recommendation/event owners.
- `GET /api/v1/marketplace/client/recommendations` and `POST /api/v1/marketplace/client/events` — current gateway/public transport entrypoints used by the client portal frontend; they resolve into the same marketplace owner contour and are not a second product owner.

Not every `/api/client/*` route has route-parity with `/api/core/client/*`. Example: public `/api/client/invoices*` from `portal.py` still serves the legacy `invoice_ref`/`Invoice` contour, while canonical `/api/core/client/invoices*` serves the subscription/billing-invoice contour from `client_portal_v1`.

Parity-adjacent client compatibility tails remain explicit:

- `/api/client/marketplace/recommendations`
- `/api/client/marketplace/events`

These marketplace routes are compatibility/internal shadow routes over the canonical `/api/marketplace/client/*` family and should not be treated as the owner surface in the client portal.

The repo also keeps additive `/api/core/v1/marketplace/client/*` projections and app-mounted `/v1/marketplace/client/*` transport paths for the same marketplace owner. They are route-transport surfaces, not separate product ownership.

Documents-specific route ownership also stays explicit:

- frontend `/client/documents*` is the canonical general document/docflow contour
- frontend `/documents/:id` remains the final legacy compatibility tail for closing-doc detail/file/history UX
- `/api/core/client/documents/{document_id}/ack` is the additive canonical general-docflow acknowledgement surface
- `/api/v1/client/documents/{document_type}/{document_id}/ack` and `/api/v1/client/closing-packages/{package_id}/ack` remain manual-ack compatibility tails for invoice/reconciliation/closing-package semantics

Documents list/detail state truth:

- `/client/documents` must distinguish:
  - first-use empty
  - filtered empty
  - load failure with retry
- `/client/documents/:id` must not render blank files/history tabs; absent files and absent timeline are explicit empty states
- legacy `/documents/:id` remains compatibility-only detail UX and should stay honest about missing files/history instead of pretending the contour is fully populated

## Dashboard / recommendation truth

Client dashboard remains a grounded read surface over `GET /api/core/client/dashboard`.

- role-aware spotlight / next-step blocks are allowed only as a projection of the returned dashboard role (`OWNER`, `ACCOUNTANT`, `FLEET_MANAGER`, `DRIVER`)
- documents discovery from dashboard widgets must stay on canonical `/client/documents*`, never backslide into legacy `/documents*`
- empty dashboard widgets must render honest first-use / no-data states with a real next action, not fake KPI filler or generic “AI recommendation” cards

## Portal composition / visibility map

Mounted client shell composition now follows one product rule-set:

- onboarding: `/onboarding*` while `access_state=NEEDS_ONBOARDING`
- dashboard + support + canonical documents: visible for both `INDIVIDUAL` and `BUSINESS`
- finance/business contours:
  - `/invoices`
  - `/balances`
  - `/finance/*`
  - `/exports*`
  - `/billing*`
  - `/settings/management`
  remain business/finance-facing surfaces and must stay hidden for reduced personal mode
- marketplace/recommendation blocks may appear only when the mounted actor actually has the workspace/capability and the block points into a real owner route
- recommendation transport families that exist in code/docs must not be treated as internal-gate green unless the mounted client contour is actually runtime-verified in the current stack

The shell must not expose wrong-kind navigation, empty tabs, or soft-disabled business affordances for personal users.

## Support / finance state-quality truth

- `/client/support` is a client-owned inbox surface:
  - first-use empty must offer ticket creation
  - filtered empty must offer filter reset
  - load failure must offer retry
- `/client/support/:id` must distinguish:
  - `403` forbidden
  - `404` not found
  - transient load error with retry
  - empty comments vs existing discussion
- `/client/support/new` must honor contour deep links like `?topic=document_signature`, `?topic=document_edo`, `?topic=billing`, `?topic=subscription_change`:
  - the form should prefill subject/context when the owner route already knows the requested contour
  - these links must not land users on a blank generic form with no guidance
- finance route visibility follows shell segmentation from `portal/me`:
  - `support` remains mounted for both `INDIVIDUAL` and `BUSINESS`
  - `/invoices`, `/balances`, `/finance/*`, `/exports*`, `/billing*`, `/settings/management` remain business/finance-facing surfaces and should not appear as fake affordances for reduced personal mode
- client finance detail pages must prefer explicit empty sections over blank tables:
  - missing payment intake history
  - missing payments
  - missing usage lines
  - missing refunds
  are all rendered as honest empty states with contour-specific explanations
- `/finance/reconciliation` must keep request creation honest:
  - non-finance roles see an explicit access-limited state instead of a disabled pseudo-form
  - invalid period order is a local validation state, not a silent backend roundtrip
  - duplicate active periods stay in the request contour as a visible status hint, not a fake second action
- `/exports/:id` must keep export detail honest:
  - missing totals
  - absent ERP timeline
  - absent reconciliation summary
  must render explicit empty states and a real support CTA, not a fake “support queued” action

## Frozen / compatibility UI tails

- `/documents/:id` stays the final legacy compatibility detail tail for closing-doc/doc-history semantics
- `/client/documents*` stays the canonical document entry surface
- legacy compatibility tails may stay mounted, but they must not regain ownership in navigation, dashboard cards, or recommendations
- removed/frozen client UI tails should be documented before route handoff or CSS cleanup so the portal does not regress into hidden fake entrypoints

## Pre-external exclusions

The client shell now treats the following as deliberate closeout statuses before the provider phase:

- `FROZEN_EXCLUSION_BEFORE_EXTERNAL_PHASE`
  - production provider-backed OTP delivery
  - marketplace recommendation tails without mounted owner proof
  - production EDO transport, bank API, ERP/1C sync, external fuel/logistics credentials
- `OPTIONAL_NOT_CONFIGURED`
  - disabled BI / ClickHouse contours outside the current launch gate only
- `VERIFIED_SKIP_OK`
  - local email-adjacent verification where the mounted owner is proven but Mailpit/provider infrastructure is intentionally absent

What this means in practice:

- no hidden demo fallback or fake local OTP parity is allowed in normal client routes
- frozen contours may stay as honest empty/frozen/degraded states, but they must not be presented as green product ownership
- marketplace order details now keep the credits and penalties tab honest with a mounted consequences read: `200` returns an `items` list, and an empty list renders honest no-credits/no-penalties copy
- mounted client owners remain grounded in dashboard, onboarding, support/cases, documents, billing, marketplace order loop, logistics reads, trip create, fuel-consumption analytics reads, and provider-backed fuel-consumption writes

## Клиентские роли (RBAC)

Роли существуют только внутри компании клиента и не пересекаются с платформенными ролями:

- **OWNER** — владелец компании, полный доступ в рамках своей организации.
- **ADMIN** — управление пользователями, картами и лимитами.
- **ACCOUNTANT** — документы/счета/акты/выгрузки.
- **FLEET_MANAGER** — автопарк/водители/карты/лимиты по ТС.
- **LOGISTICIAN** — рейсы/маршруты/контроль расхода (если модуль включён).
- **DRIVER** — доступ только к своим картам/операциям/лимитам.

## Company Shell и онбординг компании

Онбординг компании выполняется внутри клиентского кабинета после входа:

1. Регистрация аккаунта (email/пароль; OTP flow по repo-truth не подтвержден).
2. Вход в Client Portal.
3. Экран доступа определяется через `GET /api/core/portal/me`.
4. Если `access_state=NEEDS_ONBOARDING`, пользователь попадает в canonical `/onboarding` flow:
   - профиль организации;
   - договор / contract step;
   - выбор подписки и модулей, где это поддержано backend truth.
5. После активации доступны базовые разделы: **Карты**, **Пользователи**, **Документы**.

## Минимальные разделы Client Portal (v1)

1. **Подписка** — текущий план, доступные планы, модули, ограничения (cards/users/vehicles).
2. **Карты** — список, выпуск (если разрешено), статусы, лимиты, привязки (водитель/ТС/подразделение),
   история операций по карте.
3. **Сотрудники/водители** — приглашения, роли, доступ к ресурсам (карты/документы/подразделения).
4. **Документы и договоры** — договор, счета, акты, закрывающие документы.
5. **Marketplace** — витрина/заказы/документы (если модуль включён).

## Client Portal — Коммерциализация (vC)

### 0) Принцип коммерциализации (ключевой)

Мы не продаём фичи поштучно. Мы продаём:

- уровень контроля;
- уровень ответственности;
- уровень интеграции;
- уровень SLA.

Фичи — инструмент внутри пакета.

### 1) Базовая линейка тарифов (каноническая)

#### 1.1 FREE / BASIC (Entry)

Цель: затянуть клиента в экосистему.

Включено:

- Client Portal.
- Cards / Users / Docs.
- Exports (CSV, async).
- BI Analytics (summary).
- User dashboards (базовые).
- Support (internal).
- Notifications (in-app).

Ограничения:

- ❌ Helpdesk integrations.
- ❌ BI Drill-down.
- ❌ Export ETA.
- ❌ SLO/SLA framework.
- ❌ Email notifications (или ограничено).
- ❌ Advanced analytics.

#### 1.2 CONTROL (SMB)

Цель: контроль операций.

Включено:

- Всё из BASIC.
- BI Drill-down.
- Export ETA.
- User Dashboards (role-based).
- Email notifications.
- Scheduled reports (CSV).
- Support SLA (фиксированный, базовый).

Ограничения:

- ❌ Helpdesk integrations.
- ❌ SLO tiers.
- ❌ Advanced analytics.

#### 1.3 INTEGRATE (Business / Enterprise Light)

Цель: интеграция и масштаб.

Включено:

- Всё из CONTROL.
- Helpdesk integrations (Zendesk / Jira SM).
- Inbound + outbound sync.
- Scheduled reports (XLSX).
- Export retention extended.
- Advanced notifications.
- SLO monitoring (read-only).

Ограничения:

- ❌ Custom SLO.
- ❌ Burn-rate / error budget.
- ❌ Enterprise support.

#### 1.4 ENTERPRISE

Цель: ответственность и гарантия.

Включено:

- Всё из INTEGRATE.
- SLO tiers (на выбор).
- SLA contracts.
- Advanced analytics.
- Priority support.
- Incident handling.
- Dedicated support channel.

### 2) Платные интеграции (Add-ons)

Интеграции — всегда платные, даже для Enterprise (кроме пакета).

#### 2.1 Helpdesk integrations

- Zendesk.
- Jira Service Management.

Модель оплаты:

- per org / per month;
- или per ticket volume (P2).

#### 2.2 ERP / Accounting (v1.7+)

- 1C.
- SAP.
- Oracle.
- CSV/EDO pipelines.

### 3) SLO tiers (ключевая monetization-фича)

#### 3.1 SLO как продукт

Не «есть или нет», а уровень гарантий.

- Tier A — Monitoring: SLO visibility, breach notifications, no guarantees.
- Tier B — Committed: defined SLO, SLA breach tracking, service credits (manual).
- Tier C — Guaranteed: contractual SLA, incident response, penalties / credits, dedicated escalation.

SLO — аргумент для продаж Enterprise, не просто метрика.

### 4) Advanced Analytics (платно)

#### 4.1 Что считается «advanced»

- Period comparison (MoM / YoY).
- Trend detection.
- Outliers.
- Export of BI views.
- Drill-down depth > 1.
- Saved views.

Важно: advanced analytics не ломают базовый BI, а расширяют его.

### 5) Enterprise Support Plans

#### 5.1 Support tiers

- Standard: internal support, async response, no SLA.
- Priority: SLA response time, email + portal, escalation.
- Dedicated: SLA + SLO, incident management, on-call, postmortems.

### 6) Техническая реализация (важно)

#### 6.1 Feature gating

Все коммерческие фичи должны:

- проверяться на сервере;
- основываться на:
  - subscription plan;
  - enabled add-ons;
  - SLO tier.

Никаких if (plan === 'enterprise') во фронте.

#### 6.2 Contract / Subscription model

Рекомендуется добавить:

- subscription_plan;
- addons[];
- slo_tier;
- support_plan.

Это даст:

- гибкость продаж;
- возможность кастомных контрактов.

### 7) UI / UX коммерциализации

#### 7.1 В портале

Paywall states:

- «Доступно в INTEGRATE».
- «Требуется Enterprise».

Upgrade CTA:

- «Связаться с менеджером».
- «Запросить демо».

#### 7.2 Без self-checkout (важно!)

Для Enterprise:

- ❌ не даём купить кнопкой;
- ✅ только через sales.

### 8) Что не продаём (принципиально)

- безопасность как фичу;
- базовый аудит;
- доступ к своим данным;
- исправление багов.

Это обязанность платформы, а не upsell.

### 9) Роадмап монетизации (практичный)

#### Этап 1 (сейчас)

- зафиксировать тарифы;
- включить feature flags;
- подготовить sales deck.

#### Этап 2

- добавить paywall UI;
- SLO tiers UI;
- integration marketplace (1–2).

#### Этап 3

- contracts automation;
- usage-based pricing (exports, tickets).

## ABAC: доступ водителей к картам

Для выдачи доступа к 1..N картам используется сущность привязки:

**card_access**

- `user_id`
- `card_id`
- `scope` (READ/USE/MANAGE)
- `effective_from` / `effective_to`
- `created_by`

Это позволяет назначать временный доступ, делегировать права и формально ограничивать видимость карт.

## Пользовательский поток

1. Пользователь открывает `/client/` и видит форму логина.
2. После успешного входа:
   - сначала выполняется bootstrap `GET /api/core/portal/me`;
   - если `access_state=NEEDS_ONBOARDING`, UI ведёт в canonical `/onboarding` flow;
   - если bootstrap активен, shell строится из `org.org_type` (`INDIVIDUAL` vs `BUSINESS`), роли пользователя и capabilities.
3. Боковое меню ведёт к базовым страницам (Карты, Пользователи, Документы) и
   дополнительным разделам в зависимости от подписки.
4. Основные запросы идут к `/api/core/portal/me` и `/api/core/client/*`; legacy `/api/client/*` допустим только там, где contour ещё frozen как public compatibility family.

## Локальный запуск

```bash
# Собрать и запустить весь стек c клиентским фронтом
docker compose up --build gateway client-web

# Открыть клиентский кабинет
open http://localhost/client/
```

При использовании Vite-приложения напрямую:

```bash
cd frontends/client-portal
npm install
npm run dev -- --host --port 4174
# браузер: http://localhost:4174/client/
```
