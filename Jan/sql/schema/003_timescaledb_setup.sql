-- TimescaleDB Setup for OLAP Performance
-- This migration converts the trade_aggregates table to a TimescaleDB hypertable
-- for improved time-series query performance and automatic compression.
--
-- IMPORTANT: This migration requires TimescaleDB extension to be installed.
-- Run this AFTER the initial schema (001_create_trade_aggregates.sql) is applied.

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Drop existing partitions and constraints that conflict with hypertable
-- (TimescaleDB handles its own partitioning)
DO $$
BEGIN
    -- Drop the existing partitions if they exist
    DROP TABLE IF EXISTS trade_aggregates_2026_01 CASCADE;
    DROP TABLE IF EXISTS trade_aggregates_2026_02 CASCADE;
    DROP TABLE IF EXISTS trade_aggregates_2026_03 CASCADE;
    DROP TABLE IF EXISTS trade_aggregates_default CASCADE;

    -- Detach partitions from parent (in case they weren't dropped)
    -- This may fail if partitions don't exist, which is fine
    EXCEPTION WHEN OTHERS THEN
        NULL;
END $$;

-- Convert trade_aggregates to a hypertable
-- chunk_time_interval: 1 day chunks for efficient pruning
-- migrate_data: true to move existing data into chunks
SELECT create_hypertable(
    'trade_aggregates',
    'window_start',
    chunk_time_interval => INTERVAL '1 day',
    migrate_data => true,
    if_not_exists => true
);

-- Enable compression for older data
-- Compression reduces storage by 10-20x for time-series data
ALTER TABLE trade_aggregates SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'window_start DESC'
);

-- Add compression policy: compress chunks older than 7 days
-- This runs automatically in the background
SELECT add_compression_policy(
    'trade_aggregates',
    compress_after => INTERVAL '7 days',
    if_not_exists => true
);

-- Add retention policy: drop data older than 90 days (optional)
-- Uncomment if you want automatic data expiration
-- SELECT add_retention_policy(
--     'trade_aggregates',
--     drop_after => INTERVAL '90 days',
--     if_not_exists => true
-- );

-- Create continuous aggregate for hourly VWAP (auto-refreshing materialized view)
-- This pre-computes hourly aggregates for fast dashboard queries
CREATE MATERIALIZED VIEW IF NOT EXISTS cagg_hourly_vwap
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', window_start) AS bucket,
    symbol,
    -- Weighted average of minute VWAPs
    SUM(vwap * total_volume) / NULLIF(SUM(total_volume), 0) AS hourly_vwap,
    SUM(total_volume) AS hourly_volume,
    SUM(trade_count) AS hourly_trades,
    MAX(max_price) AS hourly_high,
    MIN(min_price) AS hourly_low,
    COUNT(*) AS minute_count
FROM trade_aggregates
GROUP BY time_bucket('1 hour', window_start), symbol
WITH NO DATA;

-- Add refresh policy for continuous aggregate
-- Refreshes every 5 minutes, looking back 2 hours
SELECT add_continuous_aggregate_policy(
    'cagg_hourly_vwap',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => true
);

-- Create continuous aggregate for daily summary
CREATE MATERIALIZED VIEW IF NOT EXISTS cagg_daily_summary
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', window_start) AS bucket,
    symbol,
    -- Daily VWAP
    SUM(vwap * total_volume) / NULLIF(SUM(total_volume), 0) AS daily_vwap,
    SUM(total_volume) AS daily_volume,
    SUM(trade_count) AS daily_trades,
    MAX(max_price) AS daily_high,
    MIN(min_price) AS daily_low,
    -- First and last VWAP of the day (open/close)
    first(vwap, window_start) AS open_vwap,
    last(vwap, window_start) AS close_vwap
FROM trade_aggregates
GROUP BY time_bucket('1 day', window_start), symbol
WITH NO DATA;

-- Refresh policy for daily summary
SELECT add_continuous_aggregate_policy(
    'cagg_daily_summary',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => true
);

-- Create indexes on continuous aggregates for faster queries
CREATE INDEX IF NOT EXISTS idx_cagg_hourly_symbol_bucket
ON cagg_hourly_vwap (symbol, bucket DESC);

CREATE INDEX IF NOT EXISTS idx_cagg_daily_symbol_bucket
ON cagg_daily_summary (symbol, bucket DESC);

-- Grant permissions (adjust as needed for your setup)
-- GRANT SELECT ON cagg_hourly_vwap TO readonly_user;
-- GRANT SELECT ON cagg_daily_summary TO readonly_user;

-- Verify setup
DO $$
DECLARE
    hypertable_count INTEGER;
    cagg_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO hypertable_count
    FROM timescaledb_information.hypertables
    WHERE hypertable_name = 'trade_aggregates';

    SELECT COUNT(*) INTO cagg_count
    FROM timescaledb_information.continuous_aggregates
    WHERE view_name IN ('cagg_hourly_vwap', 'cagg_daily_summary');

    RAISE NOTICE 'TimescaleDB setup complete:';
    RAISE NOTICE '  - Hypertables: %', hypertable_count;
    RAISE NOTICE '  - Continuous aggregates: %', cagg_count;
END $$;
