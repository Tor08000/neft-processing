-- Canonical BI marts (contracted schema)
CREATE TABLE IF NOT EXISTS mart_finance_daily (
    date Date,
    gross_revenue Int64,
    net_revenue Int64,
    commission_income Int64,
    vat Int64,
    refunds Int64,
    penalties Int64,
    margin Int64
) ENGINE = MergeTree()
ORDER BY date;

CREATE TABLE IF NOT EXISTS mart_cashflow (
    date Date,
    inflow Int64,
    outflow Int64,
    net_cashflow Int64,
    balance_estimated Int64
) ENGINE = MergeTree()
ORDER BY date;

CREATE TABLE IF NOT EXISTS mart_ops_sla (
    date Date,
    total_orders Int64,
    sla_breaches Int64,
    avg_resolution_time Float64,
    p95_resolution_time Float64,
    top_partners_by_breaches String
) ENGINE = MergeTree()
ORDER BY date;

CREATE TABLE IF NOT EXISTS mart_partner_performance (
    partner_id String,
    period Date,
    orders_count Int64,
    revenue Int64,
    penalties Int64,
    payout_amount Int64,
    sla_score Float64
) ENGINE = MergeTree()
ORDER BY (partner_id, period);

CREATE TABLE IF NOT EXISTS mart_client_spend (
    client_id String,
    period Date,
    spend_total Int64,
    spend_by_product String,
    fuel_spend Int64,
    marketplace_spend Int64,
    avg_ticket Int64
) ENGINE = MergeTree()
ORDER BY (client_id, period);

CREATE TABLE IF NOT EXISTS mart_versions (
    mart_name String,
    version String,
    is_active UInt8,
    created_at DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (mart_name, version);
