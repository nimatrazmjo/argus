-- deploy/rum/rum-schema.sql — ClickHouse Schema for Real User Monitoring (RUM) & Session Replay (F017)

CREATE TABLE IF NOT EXISTS default.rum_sessions (
    session_id String,
    user_id String,
    user_email_masked String,
    start_time DateTime64(3),
    end_time DateTime64(3),
    duration_ms UInt32,
    events_count UInt32,
    errors_count UInt32,
    trace_id String,
    user_agent String,
    page_url String,
    ip_masked String,
    metadata Map(String, String)
) ENGINE = ReplacingMergeTree()
ORDER BY (session_id, start_time);

CREATE TABLE IF NOT EXISTS default.rum_events (
    session_id String,
    event_id String,
    timestamp DateTime64(3),
    event_type LowCardinality(String),
    target_tag String,
    target_id String,
    target_class String,
    target_selector String,
    masked_value String,
    payload String,
    trace_id String
) ENGINE = MergeTree()
ORDER BY (session_id, timestamp);
