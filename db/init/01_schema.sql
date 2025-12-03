-- ===== CORE ENTITIES =====
CREATE TABLE IF NOT EXISTS clients (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  name TEXT,
  status TEXT DEFAULT 'ACTIVE',
  email TEXT UNIQUE,
  full_name TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS client_cards (
  id BIGSERIAL PRIMARY KEY,
  client_id BIGINT REFERENCES clients(id),
  card_id TEXT NOT NULL,
  pan_masked TEXT,
  status TEXT DEFAULT 'ACTIVE',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS client_cards_client_idx ON client_cards(client_id);

CREATE TABLE IF NOT EXISTS client_operations (
  id BIGSERIAL PRIMARY KEY,
  client_id BIGINT REFERENCES clients(id),
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
  client_id BIGINT REFERENCES clients(id),
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
  client_id BIGINT REFERENCES clients(id),
  currency TEXT DEFAULT 'RUB',
  balance NUMERIC DEFAULT 0,
  hold NUMERIC DEFAULT 0,
  status TEXT DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS cards (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  client_id BIGINT REFERENCES clients(id),
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
  client_id BIGINT,
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
  client_id BIGINT,
  files JSONB,
  status TEXT
);
CREATE TABLE IF NOT EXISTS aml_case (
  id BIGSERIAL PRIMARY KEY,
  tenant_id BIGINT,
  client_id BIGINT,
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

-- ===== INDEXES =====
CREATE INDEX IF NOT EXISTS idx_txn_ts ON transactions(auth_ts);
CREATE INDEX IF NOT EXISTS idx_txn_card ON transactions(card_id);
CREATE INDEX IF NOT EXISTS idx_rules_scope ON rules(scope, subject_id, enabled, priority);
CREATE INDEX IF NOT EXISTS idx_price_active ON price_list(azs_id, product_id, status, start_at, end_at);
