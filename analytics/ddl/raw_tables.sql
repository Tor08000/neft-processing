-- ClickHouse raw ingestion tables (append-only)
CREATE TABLE IF NOT EXISTS raw_operations (
    source_id String,
    source_updated_at DateTime,
    ingested_at DateTime DEFAULT now(),
    hash String,
    payload String
) ENGINE = MergeTree()
ORDER BY (source_updated_at, source_id);

CREATE TABLE IF NOT EXISTS raw_invoices (
    source_id String,
    source_updated_at DateTime,
    ingested_at DateTime DEFAULT now(),
    hash String,
    payload String
) ENGINE = MergeTree()
ORDER BY (source_updated_at, source_id);

CREATE TABLE IF NOT EXISTS raw_payments (
    source_id String,
    source_updated_at DateTime,
    ingested_at DateTime DEFAULT now(),
    hash String,
    payload String
) ENGINE = MergeTree()
ORDER BY (source_updated_at, source_id);

CREATE TABLE IF NOT EXISTS raw_settlements (
    source_id String,
    source_updated_at DateTime,
    ingested_at DateTime DEFAULT now(),
    hash String,
    payload String
) ENGINE = MergeTree()
ORDER BY (source_updated_at, source_id);

CREATE TABLE IF NOT EXISTS raw_marketplace_orders (
    source_id String,
    source_updated_at DateTime,
    ingested_at DateTime DEFAULT now(),
    hash String,
    payload String
) ENGINE = MergeTree()
ORDER BY (source_updated_at, source_id);

CREATE TABLE IF NOT EXISTS raw_payouts (
    source_id String,
    source_updated_at DateTime,
    ingested_at DateTime DEFAULT now(),
    hash String,
    payload String
) ENGINE = MergeTree()
ORDER BY (source_updated_at, source_id);

CREATE TABLE IF NOT EXISTS raw_fuel_operations (
    source_id String,
    source_updated_at DateTime,
    ingested_at DateTime DEFAULT now(),
    hash String,
    payload String
) ENGINE = MergeTree()
ORDER BY (source_updated_at, source_id);
