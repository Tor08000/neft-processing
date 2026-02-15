CREATE DATABASE IF NOT EXISTS neft_geo;
USE neft_geo;

CREATE TABLE IF NOT EXISTS dim_stations
(
  station_id String,
  name String,
  address String,
  lat Float64,
  lon Float64,
  partner_id Nullable(String),
  risk_zone LowCardinality(String),
  health_status LowCardinality(String),
  updated_at DateTime
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (station_id);

CREATE TABLE IF NOT EXISTS raw_fuel_events
(
  event_id String,
  event_ts DateTime,
  day Date MATERIALIZED toDate(event_ts),
  station_id String,
  status LowCardinality(String),
  amount Float64,
  liters Float64,
  captured UInt8,
  decline UInt8,
  risk_red UInt8,
  risk_yellow UInt8,
  tenant_id Nullable(UInt64)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_ts)
ORDER BY (event_ts, station_id, event_id);

CREATE TABLE IF NOT EXISTS fact_station_day
(
  day Date,
  station_id String,
  tx_count UInt32,
  captured_count UInt32,
  declined_count UInt32,
  amount_sum Float64,
  liters_sum Float64,
  risk_red_count UInt32,
  risk_yellow_count UInt32
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, station_id);

CREATE TABLE IF NOT EXISTS fact_tiles_day
(
  day Date,
  zoom UInt8,
  tile_x UInt32,
  tile_y UInt32,
  tx_count UInt32,
  captured_count UInt32,
  declined_count UInt32,
  amount_sum Float64,
  liters_sum Float64,
  risk_red_count UInt32,
  risk_yellow_count UInt32
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, zoom, tile_x, tile_y);

CREATE TABLE IF NOT EXISTS fact_tiles_overlays_day
(
  day Date,
  zoom UInt8,
  overlay_kind LowCardinality(String),
  tile_x UInt32,
  tile_y UInt32,
  value UInt32
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, zoom, overlay_kind, tile_x, tile_y);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_raw_to_station_day
TO fact_station_day
AS
SELECT
  day,
  station_id,
  toUInt32(count()) AS tx_count,
  toUInt32(sum(captured)) AS captured_count,
  toUInt32(sum(decline)) AS declined_count,
  sumIf(amount, captured = 1) AS amount_sum,
  sumIf(liters, captured = 1) AS liters_sum,
  toUInt32(sum(risk_red)) AS risk_red_count,
  toUInt32(sum(risk_yellow)) AS risk_yellow_count
FROM raw_fuel_events
GROUP BY day, station_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_raw_to_tiles_day
TO fact_tiles_day
AS
SELECT
  r.day AS day,
  z AS zoom,
  toUInt32(floor(((s.lon + 180.0) / 360.0) * pow(2, z))) AS tile_x,
  toUInt32(floor((1.0 - (
    log(tan((least(greatest(s.lat, -85.0511), 85.0511) * pi() / 180.0)) +
        1.0 / cos((least(greatest(s.lat, -85.0511), 85.0511) * pi() / 180.0)))
  ) / pi())) / 2.0 * pow(2, z))) AS tile_y,
  toUInt32(count()) AS tx_count,
  toUInt32(sum(r.captured)) AS captured_count,
  toUInt32(sum(r.decline)) AS declined_count,
  sumIf(r.amount, r.captured = 1) AS amount_sum,
  sumIf(r.liters, r.captured = 1) AS liters_sum,
  toUInt32(sum(r.risk_red)) AS risk_red_count,
  toUInt32(sum(r.risk_yellow)) AS risk_yellow_count
FROM raw_fuel_events r
INNER JOIN dim_stations s ON s.station_id = r.station_id
ARRAY JOIN [8,10,12] AS z
GROUP BY day, zoom, tile_x, tile_y;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_raw_to_overlays_risk_red
TO fact_tiles_overlays_day
AS
SELECT
  r.day AS day,
  z AS zoom,
  toLowCardinality('RISK_RED') AS overlay_kind,
  toUInt32(floor(((s.lon + 180.0) / 360.0) * pow(2, z))) AS tile_x,
  toUInt32(floor((1.0 - (
    log(tan((least(greatest(s.lat, -85.0511), 85.0511) * pi() / 180.0)) +
        1.0 / cos((least(greatest(s.lat, -85.0511), 85.0511) * pi() / 180.0)))
  ) / pi())) / 2.0 * pow(2, z))) AS tile_y,
  toUInt32(sum(r.risk_red)) AS value
FROM raw_fuel_events r
INNER JOIN dim_stations s ON s.station_id = r.station_id
ARRAY JOIN [8,10,12] AS z
WHERE r.risk_red = 1
GROUP BY day, zoom, overlay_kind, tile_x, tile_y;

CREATE TABLE IF NOT EXISTS fact_station_margin_day
(
  day Date,
  station_id String,
  revenue_sum Float64,
  cost_sum Float64,
  gross_margin Float64,
  tx_count UInt32,
  updated_at DateTime
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, station_id);
