# Marketplace — Stage C: Promotions + Gamification

This document captures the Stage C Marketplace scope for promotions, coupons, flash sales, sponsored placements, and partner gamification. It defines the core data model, pricing rules, audit requirements, and API surface.

## 1) Promo Economy

### 1.1 Promo types

**Discounts**
- `PRODUCT_DISCOUNT`: discount for specific product/service
- `CATEGORY_DISCOUNT`: discount for a category
- `BUNDLE_DISCOUNT`: bundle pricing ("cheaper together")
- `TIER_DISCOUNT`: discount for selected client segments

**Coupons**
- `PUBLIC_COUPON`: shared code
- `TARGETED_COUPON`: code bound to a client/segment
- `AUTO_COUPON`: auto-applied (no code entry)

**Flash / Time-window**
- `FLASH_SALE`: short windows (e.g., 2 hours)
- `HAPPY_HOURS`: off-peak time windows

**Sponsored / Boost**
- `SPONSORED_PLACEMENT`: paid promotion in ranking blocks
- **Billing model**: start with CPA (simpler + fairer), optional CPC later

### 1.2 Economy constraints (margin guardrails)

Each promo carries:
- **Price floor** or **max discount**
- **Budget** (for sponsored)
- **Time + volume limits**
- **Stacking rules** with other promotions

Stacking variants:
- `BEST_ONLY`: apply only the best discount
- `ALLOW_STACK_WITH_CAP`: stack up to a % cap
- `NO_STACK`: no stacking

## 2) Data Model (tables + schemas)

### 2.1 Promotions (single model for all promo types)

```sql
CREATE TABLE promotions (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  partner_id UUID NOT NULL,

  promo_type TEXT NOT NULL, -- PRODUCT_DISCOUNT, COUPON, FLASH_SALE, SPONSORED
  status TEXT NOT NULL,     -- DRAFT, ACTIVE, PAUSED, ENDED, ARCHIVED

  title TEXT NOT NULL,
  description TEXT,

  scope JSONB NOT NULL,      -- product/category/all
  eligibility JSONB NOT NULL, -- segments/regions/roles
  rules JSONB NOT NULL,      -- discount + stacking
  budget JSONB NULL,         -- sponsored only
  limits JSONB NULL,         -- per-client/per-day/total
  schedule JSONB NOT NULL,   -- valid_from/valid_to + time windows

  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_promotions_partner_status ON promotions(partner_id, status);
CREATE INDEX ix_promotions_active_window
  ON promotions(status, (schedule->>'valid_from'), (schedule->>'valid_to'));
```

**Scope examples**

```json
{ "type":"PRODUCT", "product_ids":["p1","p2"] }
```

```json
{ "type":"CATEGORY", "category_codes":["OILS","TIRES"] }
```

**Rules example**

```json
{
  "discount_type": "PERCENT",
  "discount_value": 15,
  "price_floor": 2500,
  "stacking": "BEST_ONLY"
}
```

### 2.2 Coupons

Use **batches + instances** to control issuance and redemption.

```sql
CREATE TABLE coupon_batches (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  partner_id UUID NOT NULL,
  promotion_id UUID NOT NULL REFERENCES promotions(id),

  code_prefix TEXT,
  total_count INT,
  issued_count INT DEFAULT 0,
  redeemed_count INT DEFAULT 0,

  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE coupons (
  id UUID PRIMARY KEY,
  batch_id UUID NOT NULL REFERENCES coupon_batches(id),
  code TEXT UNIQUE NOT NULL,

  status TEXT NOT NULL,  -- NEW, ISSUED, REDEEMED, EXPIRED, CANCELED
  client_id UUID NULL,   -- targeted coupons
  redeemed_order_id UUID NULL,

  issued_at TIMESTAMPTZ NULL,
  redeemed_at TIMESTAMPTZ NULL,
  expires_at TIMESTAMPTZ NULL
);
```

### 2.3 Sponsored budgets

```sql
CREATE TABLE promo_budgets (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  promotion_id UUID NOT NULL REFERENCES promotions(id),

  model TEXT NOT NULL, -- CPA or CPC
  currency TEXT NOT NULL DEFAULT 'RUB',
  total_budget NUMERIC NOT NULL,
  spent_budget NUMERIC NOT NULL DEFAULT 0,

  max_bid NUMERIC NOT NULL,
  daily_cap NUMERIC NULL,

  status TEXT NOT NULL, -- ACTIVE/PAUSED/EXHAUSTED
  updated_at TIMESTAMPTZ NOT NULL
);
```

### 2.4 Promotion application logs (audit)

```sql
CREATE TABLE promotion_applications (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  promotion_id UUID NOT NULL,
  order_id UUID NOT NULL,
  partner_id UUID NOT NULL,
  client_id UUID NOT NULL,

  applied_discount NUMERIC NOT NULL,
  applied_reason JSONB NOT NULL, -- why applied/why rejected
  final_price_snapshot JSONB NOT NULL, -- price breakdown snapshot

  created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_promo_apps_order ON promotion_applications(order_id);
```

**Audit requirements (trust layer)**
- Hash payloads
- Sign events
- Append-only logs for promotion changes and applications

## 3) Pricing & Application Rules

### 3.1 Canonical price pipeline

On checkout/order creation:

1. `base_price` from partner price list
2. Apply promos in strict order:
   - hard constraints (`price_floor`, eligibility)
   - stacking rule (`BEST_ONLY`, etc.)
3. Compute `final_price`
4. Calculate:
   - `partner_revenue`
   - `platform_fee` (plan-driven)
   - `promo_cost` (sponsored)
5. Persist `price_snapshot` on the order and log `promotion_applications`

### 3.2 Invariants

- `final_price >= 0`
- `final_price >= price_floor` (if defined)
- promo applies only when `ACTIVE` and within schedule
- no duplicate application (idempotent)

## 4) Gamification (Partners)

### 4.1 KPI basis

Daily/weekly/monthly KPIs:
- revenue
- orders_completed
- cancel_rate
- refund_rate
- avg_rating
- sla_on_time
- repeat_customers_rate

### 4.2 Partner tiers

**Bronze / Silver / Gold / Platinum**
- affect ranking
- affect commission (fee discount)
- unlock promo tools (feature gating)
- trust badges in UI

```sql
CREATE TABLE partner_tiers (
  tier_code TEXT PRIMARY KEY, -- BRONZE/SILVER/GOLD/PLATINUM
  title TEXT NOT NULL,
  benefits JSONB NOT NULL, -- boosts, fee_discount, promo_slots
  thresholds JSONB NOT NULL  -- KPI thresholds
);

CREATE TABLE partner_tier_state (
  partner_id UUID PRIMARY KEY,
  tier_code TEXT NOT NULL REFERENCES partner_tiers(tier_code),
  score NUMERIC NOT NULL,
  metrics_snapshot JSONB NOT NULL,
  evaluated_at TIMESTAMPTZ NOT NULL
);
```

### 4.3 Missions (quests)

```sql
CREATE TABLE partner_missions (
  id UUID PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  rule JSONB NOT NULL,      -- conditions
  reward JSONB NOT NULL,    -- boosts, fee discounts, badges
  active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE partner_mission_progress (
  partner_id UUID NOT NULL,
  mission_id UUID NOT NULL REFERENCES partner_missions(id),
  progress NUMERIC NOT NULL,
  status TEXT NOT NULL, -- ACTIVE/COMPLETED/CLAIMED/EXPIRED
  updated_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (partner_id, mission_id)
);
```

### 4.4 Badges

```sql
CREATE TABLE partner_badges (
  id UUID PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  icon TEXT,
  rule JSONB NOT NULL
);

CREATE TABLE partner_badge_awards (
  partner_id UUID NOT NULL,
  badge_id UUID NOT NULL REFERENCES partner_badges(id),
  awarded_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NULL,
  PRIMARY KEY (partner_id, badge_id)
);
```

## 5) Ranking (Marketplace listing)

**Score (v1)**

```
rank_score = relevance + tier_boost + promo_boost + quality - penalties
```

- **tier_boost**: based on partner tier
- **promo_boost**: based on sponsored/active promos (capped)
- **quality**: rating/repeat/SLA
- **penalties**: cancellations/refunds/suspicious activity

> Promo must not override relevance; otherwise customer trust suffers.

## 6) UI/UX Scope

### 6.1 Partner Portal: Promotions

- Promotions list (draft/active/ended)
- Creation flow:
  - promo type
  - product/category scope
  - discount size
  - schedule
  - limits
  - coupons (optional)
  - budget (sponsored)
- Preview: client-facing view
- Stats: impressions, clicks, orders, revenue uplift, promo spend

### 6.2 Partner Portal: Gamification

- Tier + progress to next tier
- KPI dashboard
- Missions (active/completed)
- Rewards/badges
- Leaderboard (region/category)

### 6.3 Client Portal

- Badges on product cards: “-15%”, “Flash”, “Top partner”, “Gold seller”
- “Deals” block
- Filter by discounted
- Product card highlights:
  - time left
  - coupon applicable
  - “Best offer” label for `BEST_ONLY`

### 6.4 Admin UI (Ops/Moderation)

- Promo moderation (approve/ban)
- Global limits: max discount, anti-dumping guardrails
- Investigation for promo/click abuse
- Kill switch for promo campaigns

## 7) API Surface

### 7.1 Partner API

- `POST /api/partner/marketplace/promotions` (create draft)
- `PATCH /api/partner/marketplace/promotions/{id}` (edit)
- `POST /api/partner/marketplace/promotions/{id}/activate`
- `POST /api/partner/marketplace/promotions/{id}/pause`
- `GET /api/partner/marketplace/promotions`
- `GET /api/partner/marketplace/promotions/{id}/stats`

**Gamification**
- `GET /api/partner/gamification/tier`
- `GET /api/partner/gamification/missions`
- `POST /api/partner/gamification/missions/{id}/claim`
- `GET /api/partner/gamification/leaderboard?region=&category=`

### 7.2 Client API

- `GET /api/client/marketplace/deals`
- `POST /api/client/marketplace/coupons/apply`
- `GET /api/client/marketplace/products?discounted=true`

## 8) Finance + Trust Integration

### 8.1 Commissions

Commission depends on:
- `partner_subscription.plan_code`
- `partner_tier_state` (fee discount)
- optional product/category overrides

Commission must be reflected in:
- invoice/settlement
- partner payout
- signed audit logs

### 8.2 Trust layer (audit-bound)

Actions to log as append-only signed events:
- promotion create/update
- activation/pause
- order-level promo application

## 9) Anti-fraud (Stage C minimum)

- De-dup clicks by user/session/IP
- Limit events per product
- Flag suspicious patterns:
  - click spikes without purchases
  - abnormal night spikes
  - single IP/device dominance

Flag: `SUSPICIOUS_PROMO_ACTIVITY` → reduce promo boost + open case

## 10) Done Criteria

- Partner can create and activate a product/category discount
- Client sees discounted pricing; price is correct and persisted in snapshot
- Discount is included in payment/settlement/commission
- Promo performance reporting is available to partner
- Partner tier + missions + badges + leaderboard available
- Ranking uses tier/promo/quality without breaking relevance
- All promo operations are audit-bound (hash + signature, append-only)
