-- Project Argus — Feature F014: Data Governance, Tiered Retention & Metric Downsampling
-- ClickHouse Tiered Storage (Hot SSD -> Cold S3/SeaweedFS -> Drop TTL)
-- Metric Downsampling Rollups (Raw -> 1m -> 1h via Materialized Views)

CREATE DATABASE IF NOT EXISTS default;
CREATE DATABASE IF NOT EXISTS signoz_metrics;

--------------------------------------------------------------------------------
-- 1. METRIC DOWNSAMPLING: DEFAULT SCHEMA (default.otel_metrics_1m & 1h)
--------------------------------------------------------------------------------

-- 1-minute rollup table for OpenTelemetry gauge & sum metrics
CREATE TABLE IF NOT EXISTS default.otel_metrics_1m
(
    ServiceName LowCardinality(String) CODEC(ZSTD(1)),
    MetricName LowCardinality(String) CODEC(ZSTD(1)),
    Attributes Map(LowCardinality(String), String) CODEC(ZSTD(1)),
    TimeUnix DateTime CODEC(Delta, ZSTD(1)),
    Last SimpleAggregateFunction(anyLast, Float64) CODEC(ZSTD(1)),
    Min SimpleAggregateFunction(min, Float64) CODEC(ZSTD(1)),
    Max SimpleAggregateFunction(max, Float64) CODEC(ZSTD(1)),
    Sum SimpleAggregateFunction(sum, Float64) CODEC(ZSTD(1)),
    Count SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1))
) ENGINE = AggregatingMergeTree()
PARTITION BY toDate(TimeUnix)
ORDER BY (ServiceName, MetricName, toStartOfHour(TimeUnix), cityHash64(Attributes), TimeUnix)
TTL TimeUnix + INTERVAL 30 DAY TO VOLUME 'cold',
    TimeUnix + INTERVAL 90 DAY
SETTINGS storage_policy = 'tiered_hot_cold', index_granularity = 8192, ttl_only_drop_parts = 1;

-- Materialized View: Raw otel_metrics_gauge -> 1-minute rollup
CREATE MATERIALIZED VIEW IF NOT EXISTS default.otel_metrics_gauge_1m_mv TO default.otel_metrics_1m
AS SELECT
    ServiceName,
    MetricName,
    Attributes,
    toStartOfMinute(TimeUnix) AS TimeUnix,
    anyLast(Value) AS Last,
    min(Value) AS Min,
    max(Value) AS Max,
    sum(Value) AS Sum,
    count(*) AS Count
FROM default.otel_metrics_gauge
GROUP BY
    ServiceName,
    MetricName,
    Attributes,
    TimeUnix;

-- Materialized View: Raw otel_metrics_sum -> 1-minute rollup
CREATE MATERIALIZED VIEW IF NOT EXISTS default.otel_metrics_sum_1m_mv TO default.otel_metrics_1m
AS SELECT
    ServiceName,
    MetricName,
    Attributes,
    toStartOfMinute(TimeUnix) AS TimeUnix,
    anyLast(Value) AS Last,
    min(Value) AS Min,
    max(Value) AS Max,
    sum(Value) AS Sum,
    count(*) AS Count
FROM default.otel_metrics_sum
GROUP BY
    ServiceName,
    MetricName,
    Attributes,
    TimeUnix;

-- 1-hour rollup table for OpenTelemetry metrics (rolled up from 1m)
CREATE TABLE IF NOT EXISTS default.otel_metrics_1h
(
    ServiceName LowCardinality(String) CODEC(ZSTD(1)),
    MetricName LowCardinality(String) CODEC(ZSTD(1)),
    Attributes Map(LowCardinality(String), String) CODEC(ZSTD(1)),
    TimeUnix DateTime CODEC(Delta, ZSTD(1)),
    Last SimpleAggregateFunction(anyLast, Float64) CODEC(ZSTD(1)),
    Min SimpleAggregateFunction(min, Float64) CODEC(ZSTD(1)),
    Max SimpleAggregateFunction(max, Float64) CODEC(ZSTD(1)),
    Sum SimpleAggregateFunction(sum, Float64) CODEC(ZSTD(1)),
    Count SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1))
) ENGINE = AggregatingMergeTree()
PARTITION BY toDate(TimeUnix)
ORDER BY (ServiceName, MetricName, toStartOfHour(TimeUnix), cityHash64(Attributes), TimeUnix)
TTL TimeUnix + INTERVAL 90 DAY TO VOLUME 'cold',
    TimeUnix + INTERVAL 365 DAY
SETTINGS storage_policy = 'tiered_hot_cold', index_granularity = 8192, ttl_only_drop_parts = 1;

-- Materialized View: 1-minute rollups -> 1-hour rollup
CREATE MATERIALIZED VIEW IF NOT EXISTS default.otel_metrics_1h_mv TO default.otel_metrics_1h
AS SELECT
    ServiceName,
    MetricName,
    Attributes,
    toStartOfHour(TimeUnix) AS TimeUnix,
    anyLast(Last) AS Last,
    min(Min) AS Min,
    max(Max) AS Max,
    sum(Sum) AS Sum,
    sum(Count) AS Count
FROM default.otel_metrics_1m
GROUP BY
    ServiceName,
    MetricName,
    Attributes,
    TimeUnix;

--------------------------------------------------------------------------------
-- 2. METRIC DOWNSAMPLING: SIGNOZ SCHEMA (signoz_metrics.samples_1m & 1h)
--------------------------------------------------------------------------------

-- 1-minute rollup table for SigNoz metric samples
CREATE TABLE IF NOT EXISTS signoz_metrics.samples_1m
(
    env LowCardinality(String) DEFAULT 'default',
    temporality LowCardinality(String) DEFAULT 'Unspecified',
    metric_name LowCardinality(String),
    fingerprint UInt64 CODEC(ZSTD(1)),
    unix_milli Int64 CODEC(Delta(8), ZSTD(1)),
    last SimpleAggregateFunction(anyLast, Float64) CODEC(ZSTD(1)),
    min SimpleAggregateFunction(min, Float64) CODEC(ZSTD(1)),
    max SimpleAggregateFunction(max, Float64) CODEC(ZSTD(1)),
    sum SimpleAggregateFunction(sum, Float64) CODEC(ZSTD(1)),
    count SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1))
) ENGINE = AggregatingMergeTree()
PARTITION BY toDate(unix_milli / 1000)
ORDER BY (env, temporality, metric_name, fingerprint, unix_milli)
TTL toDateTime(unix_milli / 1000) + INTERVAL 30 DAY TO VOLUME 'cold',
    toDateTime(unix_milli / 1000) + INTERVAL 90 DAY
SETTINGS storage_policy = 'tiered_hot_cold', index_granularity = 8192, ttl_only_drop_parts = 1;

-- Materialized View: Raw signoz_metrics.samples_v4 -> 1-minute rollup
CREATE MATERIALIZED VIEW IF NOT EXISTS signoz_metrics.samples_1m_mv TO signoz_metrics.samples_1m
AS SELECT
    env,
    temporality,
    metric_name,
    fingerprint,
    intDiv(unix_milli, 60000) * 60000 AS unix_milli,
    anyLast(value) AS last,
    min(value) AS min,
    max(value) AS max,
    sum(value) AS sum,
    count(*) AS count
FROM signoz_metrics.samples_v4
GROUP BY
    env,
    temporality,
    metric_name,
    fingerprint,
    unix_milli;

-- 1-hour rollup table for SigNoz metric samples
CREATE TABLE IF NOT EXISTS signoz_metrics.samples_1h
(
    env LowCardinality(String) DEFAULT 'default',
    temporality LowCardinality(String) DEFAULT 'Unspecified',
    metric_name LowCardinality(String),
    fingerprint UInt64 CODEC(ZSTD(1)),
    unix_milli Int64 CODEC(Delta(8), ZSTD(1)),
    last SimpleAggregateFunction(anyLast, Float64) CODEC(ZSTD(1)),
    min SimpleAggregateFunction(min, Float64) CODEC(ZSTD(1)),
    max SimpleAggregateFunction(max, Float64) CODEC(ZSTD(1)),
    sum SimpleAggregateFunction(sum, Float64) CODEC(ZSTD(1)),
    count SimpleAggregateFunction(sum, UInt64) CODEC(ZSTD(1))
) ENGINE = AggregatingMergeTree()
PARTITION BY toDate(unix_milli / 1000)
ORDER BY (env, temporality, metric_name, fingerprint, unix_milli)
TTL toDateTime(unix_milli / 1000) + INTERVAL 90 DAY TO VOLUME 'cold',
    toDateTime(unix_milli / 1000) + INTERVAL 365 DAY
SETTINGS storage_policy = 'tiered_hot_cold', index_granularity = 8192, ttl_only_drop_parts = 1;

-- Materialized View: 1-minute rollups -> 1-hour rollup
CREATE MATERIALIZED VIEW IF NOT EXISTS signoz_metrics.samples_1h_mv TO signoz_metrics.samples_1h
AS SELECT
    env,
    temporality,
    metric_name,
    fingerprint,
    intDiv(unix_milli, 3600000) * 3600000 AS unix_milli,
    anyLast(last) AS last,
    min(min) AS min,
    max(max) AS max,
    sum(sum) AS sum,
    sum(count) AS count
FROM signoz_metrics.samples_1m
GROUP BY
    env,
    temporality,
    metric_name,
    fingerprint,
    unix_milli;

--------------------------------------------------------------------------------
-- 3. TIERED RETENTION & TTL POLICIES (HOT LOCAL -> COLD S3 -> DROP)
--------------------------------------------------------------------------------

-- The base tables already have 30-day TTL configured at table creation time in otel-schema.sql.
-- ALTER TABLE default.otel_traces MODIFY TTL toDateTime(Timestamp) + INTERVAL 30 DAY;
-- ALTER TABLE default.otel_logs MODIFY TTL toDateTime(Timestamp) + INTERVAL 30 DAY;
-- ALTER TABLE default.otel_metrics_gauge MODIFY TTL TimeUnix + INTERVAL 30 DAY;
-- ALTER TABLE default.otel_metrics_sum MODIFY TTL TimeUnix + INTERVAL 30 DAY;
-- ALTER TABLE default.otel_metrics_histogram MODIFY TTL TimeUnix + INTERVAL 30 DAY;
-- ALTER TABLE default.otel_metrics_summary MODIFY TTL TimeUnix + INTERVAL 30 DAY;
-- ALTER TABLE default.otel_metrics_exp_histogram MODIFY TTL TimeUnix + INTERVAL 30 DAY;
