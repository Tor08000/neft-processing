CREATE TABLE IF NOT EXISTS ch_order_events (
    tenant_id UInt32,
    client_id String,
    partner_id String,
    entity_id String,
    order_id String,
    event_id String,
    event_type String,
    occurred_at DateTime,
    status String,
    amount Int64,
    currency String,
    correlation_id String,
    payload_json String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(occurred_at)
ORDER BY (tenant_id, occurred_at, entity_id);

CREATE TABLE IF NOT EXISTS ch_orders (
    tenant_id UInt32,
    client_id String,
    partner_id String,
    entity_id String,
    occurred_at DateTime,
    status String,
    amount Int64,
    currency String,
    service_id String,
    offer_id String,
    correlation_id String,
    payload_json String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(occurred_at)
ORDER BY (tenant_id, occurred_at, entity_id);

CREATE TABLE IF NOT EXISTS ch_payout_events (
    tenant_id UInt32,
    partner_id String,
    entity_id String,
    settlement_id String,
    payout_batch_id String,
    event_type String,
    occurred_at DateTime,
    amount_gross Int64,
    amount_net Int64,
    amount_commission Int64,
    currency String,
    correlation_id String,
    payload_json String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(occurred_at)
ORDER BY (tenant_id, occurred_at, entity_id);

CREATE TABLE IF NOT EXISTS ch_decline_events (
    tenant_id UInt32,
    client_id String,
    partner_id String,
    entity_id String,
    occurred_at DateTime,
    primary_reason String,
    amount Int64,
    product_type String,
    station_id String,
    correlation_id String,
    payload_json String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(occurred_at)
ORDER BY (tenant_id, occurred_at, entity_id);

CREATE TABLE IF NOT EXISTS ch_daily_metrics (
    tenant_id UInt32,
    scope_type String,
    scope_id String,
    occurred_at DateTime,
    spend_total Int64,
    orders_total Int64,
    orders_completed Int64,
    refunds_total Int64,
    payouts_total Int64,
    declines_total Int64,
    top_primary_reason String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(occurred_at)
ORDER BY (tenant_id, occurred_at, scope_id);
