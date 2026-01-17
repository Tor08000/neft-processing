-- ===== CORE ENTITIES =====
CREATE TABLE IF NOT EXISTS clients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id BIGINT,
  name TEXT,
  status TEXT DEFAULT 'ACTIVE',
  email TEXT UNIQUE,
  full_name TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS client_organizations (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  name TEXT NOT NULL,
  status TEXT DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUSPENDED', 'ONBOARDING', 'DRAFT')),
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS client_cards (
  id BIGSERIAL PRIMARY KEY,
  client_id UUID REFERENCES clients(id),
  card_id TEXT NOT NULL,
  pan_masked TEXT,
  status TEXT DEFAULT 'ACTIVE',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS client_cards_client_idx ON client_cards(client_id);

CREATE TABLE IF NOT EXISTS client_operations (
  id BIGSERIAL PRIMARY KEY,
  client_id UUID REFERENCES clients(id),
  card_id TEXT,
  operation_type TEXT,
  status TEXT,
  amount INTEGER,
  currency TEXT DEFAULT 'RUB',
  performed_at TIMESTAMPTZ DEFAULT now(),
  fuel_type TEXT
);

CREATE INDEX IF NOT EXISTS client_operations_client_idx ON client_operations(client_id);
CREATE INDEX IF NOT EXISTS client_operations_status_idx ON client_operations(status);
CREATE INDEX IF NOT EXISTS client_operations_date_idx ON client_operations(performed_at);

CREATE TABLE IF NOT EXISTS client_limits (
  id BIGSERIAL PRIMARY KEY,
  client_id UUID REFERENCES clients(id),
  limit_type TEXT,
  amount NUMERIC,
  currency TEXT DEFAULT 'RUB',
  used_amount NUMERIC DEFAULT 0,
  period_start TIMESTAMPTZ,
  period_end TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS client_limits_client_idx ON client_limits(client_id);

CREATE TABLE IF NOT EXISTS wallets (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  client_id UUID REFERENCES clients(id),
  currency TEXT DEFAULT 'RUB',
  balance NUMERIC DEFAULT 0,
  hold NUMERIC DEFAULT 0,
  status TEXT DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS cards (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  client_id UUID REFERENCES clients(id),
  wallet_id BIGINT REFERENCES wallets(id),
  token TEXT UNIQUE,
  status TEXT DEFAULT 'ACTIVE',
  pin_hash TEXT,
  expires_at DATE
);

CREATE TABLE IF NOT EXISTS partners (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  name TEXT,
  type TEXT,
  status TEXT DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS azs (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  partner_id BIGINT REFERENCES partners(id),
  name TEXT,
  address TEXT,
  region TEXT,
  status TEXT DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS pos (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  azs_id BIGINT REFERENCES azs(id),
  terminal_id TEXT,
  vendor TEXT,
  status TEXT DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS products (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  code TEXT,
  name TEXT,
  uom TEXT DEFAULT 'L'
);

-- версионируемый прайс-лист
CREATE TABLE IF NOT EXISTS price_list (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  azs_id BIGINT REFERENCES azs(id),
  product_id BIGINT REFERENCES products(id),
  version INT DEFAULT 1,
  price NUMERIC,
  start_at TIMESTAMPTZ,
  end_at TIMESTAMPTZ,
  status TEXT DEFAULT 'ACTIVE'
);

-- правила
CREATE TABLE IF NOT EXISTS rules (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  scope TEXT,            -- CARD/CLIENT/WALLET/AZS/POS/PRODUCT/SEGMENT
  subject_id TEXT,       -- id/маска/сегмент
  selector JSONB,        -- {"azs_id":1,"hour":[7,8],"product":"AI95"}
  window TEXT,           -- DAILY/MONTHLY/ROLLING_24H
  metric TEXT,           -- LITERS/AMOUNT/COUNT
  value NUMERIC,
  uom TEXT,              -- L/RUB/COUNT
  policy TEXT,           -- ALLOW/HARD_DECLINE/SOFT_DECLINE/APPLY_*
  priority INT DEFAULT 100,
  enabled BOOLEAN DEFAULT TRUE
);

-- транзакции
CREATE TABLE IF NOT EXISTS transactions (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  ext_id TEXT,
  state TEXT,            -- PRE_AUTH/CAPTURED/DECLINED/REVERSED
  reason TEXT,
  client_id UUID,
  wallet_id BIGINT,
  card_id BIGINT,
  azs_id BIGINT,
  pos_id BIGINT,
  product_id BIGINT,
  qty NUMERIC,
  amount NUMERIC,
  currency TEXT DEFAULT 'RUB',
  auth_ts TIMESTAMPTZ,
  capture_ts TIMESTAMPTZ,
  meta JSONB
);

-- клиринг/инвойсы/выплаты/споры
CREATE TABLE IF NOT EXISTS clearing (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  period DATE,
  totals JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS invoices (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  party TEXT,           -- CLIENT|PARTNER
  party_id BIGINT,
  period DATE,
  amount NUMERIC,
  currency TEXT DEFAULT 'RUB',
  status TEXT DEFAULT 'DRAFT', -- DRAFT/ISSUED/PAID/CLOSED/OVERDUE
  meta JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS payouts (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  partner_id BIGINT,
  amount NUMERIC,
  status TEXT DEFAULT 'CREATED', -- CREATED/SENT/DONE/FAILED
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS disputes (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  txn_id BIGINT,
  status TEXT DEFAULT 'OPEN', -- OPEN/UNDER_REVIEW/RESOLVED_REFUND/RESOLVED_DENY/CLOSED
  sla_due TIMESTAMPTZ,
  attachments JSONB,
  resolution JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- лояльность/купоны
CREATE TABLE IF NOT EXISTS loyalty_schemes (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  name TEXT,
  config JSONB,
  status TEXT DEFAULT 'ACTIVE'
);
CREATE TABLE IF NOT EXISTS coupons (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  pool TEXT,
  code TEXT,
  rule JSONB,
  used BOOLEAN DEFAULT FALSE
);

-- комплаенс
CREATE TABLE IF NOT EXISTS kyc (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  client_id UUID,
  files JSONB,
  status TEXT
);
CREATE TABLE IF NOT EXISTS aml_case (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  client_id UUID,
  data JSONB,
  status TEXT
);
CREATE TABLE IF NOT EXISTS sanctions (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  subject TEXT,
  result JSONB,
  checked_at TIMESTAMPTZ DEFAULT now()
);

-- фичефлаги/аудит/файлы
CREATE TABLE IF NOT EXISTS feature_flags (
  key TEXT PRIMARY KEY,
  on BOOLEAN,
  segment TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ DEFAULT now(),
  actor TEXT,
  action TEXT,
  target TEXT,
  payload JSONB,
  hash TEXT
);
CREATE TABLE IF NOT EXISTS attachments (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  bucket TEXT,
  path TEXT,
  kind TEXT,
  tags TEXT[]
);

-- подписки/биллинг (NEFT Client Portal)
CREATE TABLE IF NOT EXISTS subscription_plans (
  id BIGSERIAL PRIMARY KEY,
  code TEXT NOT NULL,
  version INT DEFAULT 1,
  title TEXT,
  description TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (code, version)
);

CREATE TABLE IF NOT EXISTS subscription_plan_modules (
  id BIGSERIAL PRIMARY KEY,
  plan_id BIGINT NOT NULL REFERENCES subscription_plans(id),
  module_code TEXT NOT NULL,
  enabled BOOLEAN DEFAULT TRUE,
  tier TEXT,
  limits_json JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (plan_id, module_code)
);

CREATE TABLE IF NOT EXISTS subscription_plan_features (
  id BIGSERIAL PRIMARY KEY,
  plan_id BIGINT NOT NULL REFERENCES subscription_plans(id),
  feature_key TEXT NOT NULL,
  availability TEXT NOT NULL CHECK (availability IN ('ENABLED', 'DISABLED', 'LIMITED', 'ADDON_ELIGIBLE')),
  limits_json JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (plan_id, feature_key)
);

CREATE TABLE IF NOT EXISTS addons (
  id BIGSERIAL PRIMARY KEY,
  code TEXT NOT NULL,
  title TEXT,
  description TEXT,
  billing_type TEXT NOT NULL CHECK (billing_type IN ('RECURRING', 'ONE_TIME', 'USAGE_BASED')),
  default_price NUMERIC(18,2),
  currency TEXT DEFAULT 'RUB' CHECK (currency IN ('RUB', 'USD', 'EUR')),
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (code)
);

CREATE TABLE IF NOT EXISTS support_plans (
  id BIGSERIAL PRIMARY KEY,
  code TEXT NOT NULL,
  sla_targets JSONB,
  included_channels TEXT[],
  escalation_enabled BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (code)
);

CREATE TABLE IF NOT EXISTS slo_tiers (
  id BIGSERIAL PRIMARY KEY,
  code TEXT NOT NULL,
  included_slos_json JSONB,
  penalties_json JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (code)
);

CREATE TABLE IF NOT EXISTS org_subscriptions (
  id BIGSERIAL PRIMARY KEY,
  org_id BIGINT NOT NULL REFERENCES client_organizations(id),
  plan_id BIGINT NOT NULL REFERENCES subscription_plans(id),
  status TEXT NOT NULL CHECK (status IN ('TRIAL', 'ACTIVE', 'SUSPENDED', 'OVERDUE', 'CANCELED')),
  starts_at TIMESTAMPTZ,
  ends_at TIMESTAMPTZ,
  billing_cycle TEXT NOT NULL CHECK (billing_cycle IN ('MONTHLY', 'YEARLY')),
  auto_renew BOOLEAN DEFAULT TRUE,
  grace_period_days INT DEFAULT 0,
  suspend_blocked_until TIMESTAMPTZ,
  support_plan_id BIGINT REFERENCES support_plans(id),
  slo_tier_id BIGINT REFERENCES slo_tiers(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (org_id)
);

CREATE TABLE IF NOT EXISTS org_subscription_addons (
  id BIGSERIAL PRIMARY KEY,
  org_subscription_id BIGINT NOT NULL REFERENCES org_subscriptions(id),
  addon_id BIGINT NOT NULL REFERENCES addons(id),
  status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'SUSPENDED', 'CANCELED')),
  starts_at TIMESTAMPTZ,
  ends_at TIMESTAMPTZ,
  price_override NUMERIC(18,2),
  config_json JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (org_subscription_id, addon_id)
);

CREATE TABLE IF NOT EXISTS org_subscription_overrides (
  id BIGSERIAL PRIMARY KEY,
  org_subscription_id BIGINT NOT NULL REFERENCES org_subscriptions(id),
  feature_key TEXT NOT NULL,
  availability TEXT NOT NULL CHECK (availability IN ('ENABLED', 'DISABLED', 'LIMITED', 'ADDON_ELIGIBLE')),
  limits_json JSONB,
  reason TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (org_subscription_id, feature_key)
);

CREATE TABLE IF NOT EXISTS org_entitlements_snapshot (
  id BIGSERIAL PRIMARY KEY,
  org_id BIGINT NOT NULL REFERENCES client_organizations(id),
  subscription_id BIGINT NOT NULL REFERENCES org_subscriptions(id),
  computed_at TIMESTAMPTZ DEFAULT now(),
  entitlements_json JSONB,
  hash TEXT,
  version INT DEFAULT 1
);

CREATE TABLE IF NOT EXISTS pricing_catalog (
  id BIGSERIAL PRIMARY KEY,
  item_type TEXT NOT NULL CHECK (item_type IN ('PLAN', 'ADDON', 'USAGE_METER')),
  item_id BIGINT NOT NULL,
  currency TEXT DEFAULT 'RUB' CHECK (currency IN ('RUB', 'USD', 'EUR')),
  price_monthly NUMERIC(18,2),
  price_yearly NUMERIC(18,2),
  effective_from TIMESTAMPTZ,
  effective_to TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  CHECK (effective_to IS NULL OR effective_to > effective_from)
);

CREATE TABLE IF NOT EXISTS billing_accounts (
  id BIGSERIAL PRIMARY KEY,
  org_id BIGINT NOT NULL REFERENCES client_organizations(id),
  legal_name TEXT,
  inn TEXT,
  kpp TEXT,
  ogrn TEXT,
  billing_email TEXT,
  currency TEXT DEFAULT 'RUB' CHECK (currency IN ('RUB', 'USD', 'EUR')),
  status TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (org_id)
);

CREATE TABLE IF NOT EXISTS billing_invoices (
  id BIGSERIAL PRIMARY KEY,
  org_id BIGINT NOT NULL REFERENCES client_organizations(id),
  subscription_id BIGINT REFERENCES org_subscriptions(id),
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('DRAFT', 'ISSUED', 'PAID', 'OVERDUE', 'VOID')),
  total_amount NUMERIC(18,2),
  currency TEXT DEFAULT 'RUB' CHECK (currency IN ('RUB', 'USD', 'EUR')),
  pdf_object_key TEXT,
  issued_at TIMESTAMPTZ,
  due_at TIMESTAMPTZ,
  paid_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS billing_invoice_lines (
  id BIGSERIAL PRIMARY KEY,
  invoice_id BIGINT NOT NULL REFERENCES billing_invoices(id),
  line_type TEXT NOT NULL CHECK (line_type IN ('PLAN', 'ADDON', 'USAGE', 'SETUP', 'DISCOUNT')),
  ref_code TEXT,
  description TEXT,
  quantity NUMERIC(18,6),
  unit_price NUMERIC(18,2),
  amount NUMERIC(18,2),
  meta_json JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS billing_dunning_events (
  id BIGSERIAL PRIMARY KEY,
  org_id BIGINT NOT NULL REFERENCES client_organizations(id),
  invoice_id BIGINT NOT NULL REFERENCES billing_invoices(id),
  event_type TEXT NOT NULL CHECK (event_type IN ('DUE_SOON_7D', 'DUE_SOON_1D', 'OVERDUE_1D', 'OVERDUE_7D', 'PRE_SUSPEND_1D', 'SUSPENDED')),
  channel TEXT NOT NULL CHECK (channel IN ('EMAIL', 'IN_APP')),
  status TEXT NOT NULL CHECK (status IN ('SENT', 'FAILED', 'SKIPPED')),
  sent_at TIMESTAMPTZ,
  idempotency_key TEXT NOT NULL UNIQUE,
  error TEXT
);

CREATE TABLE IF NOT EXISTS usage_meters (
  id BIGSERIAL PRIMARY KEY,
  code TEXT NOT NULL,
  title TEXT,
  unit TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (code)
);

CREATE TABLE IF NOT EXISTS usage_events (
  id BIGSERIAL PRIMARY KEY,
  org_id BIGINT NOT NULL REFERENCES client_organizations(id),
  meter_id BIGINT NOT NULL REFERENCES usage_meters(id),
  quantity NUMERIC(18,6),
  occurred_at TIMESTAMPTZ DEFAULT now(),
  meta_json JSONB
);

CREATE TABLE IF NOT EXISTS usage_aggregates (
  id BIGSERIAL PRIMARY KEY,
  org_id BIGINT NOT NULL REFERENCES client_organizations(id),
  meter_id BIGINT NOT NULL REFERENCES usage_meters(id),
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  quantity NUMERIC(18,6),
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (org_id, meter_id, period_start, period_end)
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_org_subscriptions_updated_at ON org_subscriptions;
CREATE TRIGGER trg_org_subscriptions_updated_at
BEFORE UPDATE ON org_subscriptions
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- ===== INDEXES =====
CREATE INDEX IF NOT EXISTS idx_txn_ts ON transactions(auth_ts);
CREATE INDEX IF NOT EXISTS idx_txn_card ON transactions(card_id);
CREATE INDEX IF NOT EXISTS idx_rules_scope ON rules(scope, subject_id, enabled, priority);
CREATE INDEX IF NOT EXISTS idx_price_active ON price_list(azs_id, product_id, status, start_at, end_at);
CREATE INDEX IF NOT EXISTS idx_pricing_catalog_effective ON pricing_catalog(effective_from, effective_to);
CREATE INDEX IF NOT EXISTS idx_pricing_catalog_item ON pricing_catalog(item_type, item_id, effective_from);
CREATE INDEX IF NOT EXISTS idx_org_entitlements_hash ON org_entitlements_snapshot(hash);
CREATE INDEX IF NOT EXISTS idx_org_entitlements_org_time ON org_entitlements_snapshot(org_id, computed_at DESC);
CREATE INDEX IF NOT EXISTS idx_org_subscription_addons_status ON org_subscription_addons(org_subscription_id, status);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_period ON billing_invoices(org_id, period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_due ON billing_invoices(status, due_at);
CREATE INDEX IF NOT EXISTS idx_billing_invoice_lines_invoice ON billing_invoice_lines(invoice_id);
CREATE INDEX IF NOT EXISTS idx_billing_dunning_events_org ON billing_dunning_events(org_id, sent_at);
CREATE INDEX IF NOT EXISTS idx_billing_dunning_events_invoice ON billing_dunning_events(invoice_id);
CREATE INDEX IF NOT EXISTS idx_billing_dunning_events_channel ON billing_dunning_events(channel, status);
CREATE INDEX IF NOT EXISTS idx_usage_events_org_meter_time ON usage_events(org_id, meter_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_usage_aggregates_org_meter_period ON usage_aggregates(org_id, meter_id, period_start);
