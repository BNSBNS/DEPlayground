-- Energy Trading Platform - Indexing Strategy
-- Question 6: Indexing for Common Access Patterns
--
-- Index design considerations:
-- 1. BRIN index on window_start - optimized for time-series data (sorted inserts)
-- 2. B-tree index on symbol - for symbol-specific lookups
-- 3. Composite indexes for common query patterns
-- 4. Partial indexes for active data windows

-- ============================================================================
-- Trade Aggregates Indexes
-- ============================================================================

-- BRIN index on window_start for time-range queries
-- BRIN (Block Range Index) is ideal for time-series data that is inserted in order
-- Much smaller than B-tree, efficient for range scans on monotonically increasing data
CREATE INDEX IF NOT EXISTS idx_trade_aggregates_window_start_brin
    ON trade_aggregates USING BRIN (window_start)
    WITH (pages_per_range = 128);

-- B-tree index on symbol for symbol lookups
-- Supports WHERE symbol = 'POWER_DE' efficiently
CREATE INDEX IF NOT EXISTS idx_trade_aggregates_symbol
    ON trade_aggregates USING BTREE (symbol);

-- Composite index for common dashboard query pattern:
-- "Get aggregates for a symbol in a time range ordered by time"
CREATE INDEX IF NOT EXISTS idx_trade_aggregates_symbol_time
    ON trade_aggregates USING BTREE (symbol, window_start DESC);

-- Index for total_volume queries (top symbols by volume)
CREATE INDEX IF NOT EXISTS idx_trade_aggregates_volume
    ON trade_aggregates USING BTREE (total_volume DESC)
    WHERE total_volume > 0;

-- Partial index for recent data (last 24 hours)
-- This accelerates queries on the "hot" portion of data
-- Note: Requires periodic recreation or use of expression with NOW()
-- In production, use a more sophisticated approach like pg_partman
CREATE INDEX IF NOT EXISTS idx_trade_aggregates_recent
    ON trade_aggregates USING BTREE (symbol, window_start DESC)
    WHERE window_start >= NOW() - INTERVAL '24 hours';


-- ============================================================================
-- Raw Trades Indexes (if storing raw events)
-- ============================================================================

-- Index on event_timestamp for time-range queries
CREATE INDEX IF NOT EXISTS idx_raw_trades_event_timestamp
    ON raw_trades USING BRIN (event_timestamp)
    WITH (pages_per_range = 128);

-- Index on symbol for symbol-specific lookups
CREATE INDEX IF NOT EXISTS idx_raw_trades_symbol
    ON raw_trades USING BTREE (symbol);

-- Composite index for trader activity queries
CREATE INDEX IF NOT EXISTS idx_raw_trades_trader_time
    ON raw_trades USING BTREE (trader_id, event_timestamp DESC);


-- ============================================================================
-- DLQ Messages Indexes
-- ============================================================================

-- Index for finding unprocessed DLQ messages
CREATE INDEX IF NOT EXISTS idx_dlq_messages_unprocessed
    ON dlq_messages USING BTREE (failed_at DESC)
    WHERE processed = FALSE;

-- Index on consumer_group for filtering
CREATE INDEX IF NOT EXISTS idx_dlq_messages_consumer_group
    ON dlq_messages USING BTREE (consumer_group, failed_at DESC);


-- ============================================================================
-- Index Documentation
-- ============================================================================

COMMENT ON INDEX idx_trade_aggregates_window_start_brin IS
    'BRIN index for efficient time-range scans on time-series data';

COMMENT ON INDEX idx_trade_aggregates_symbol IS
    'B-tree index for symbol-specific lookups';

COMMENT ON INDEX idx_trade_aggregates_symbol_time IS
    'Composite index for dashboard queries: symbol + time range';

COMMENT ON INDEX idx_trade_aggregates_volume IS
    'Partial index on volume for top-N queries';


-- ============================================================================
-- Materialized View for Common Aggregations (Q6: OLTP Optimization)
-- ============================================================================

-- Materialized view for hourly aggregates (reduces query load)
-- Refresh periodically with: REFRESH MATERIALIZED VIEW CONCURRENTLY mv_hourly_aggregates;
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_hourly_aggregates AS
SELECT
    symbol,
    date_trunc('hour', window_start) AS hour_start,
    -- Weighted average of VWAP (weighted by volume)
    SUM(vwap * total_volume) / NULLIF(SUM(total_volume), 0) AS hourly_vwap,
    SUM(total_volume) AS hourly_volume,
    SUM(trade_count) AS hourly_trade_count,
    MAX(max_price) AS hourly_max_price,
    MIN(min_price) AS hourly_min_price,
    COUNT(*) AS minutes_with_trades
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '7 days'
GROUP BY symbol, date_trunc('hour', window_start)
WITH DATA;

-- Unique index required for CONCURRENTLY refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_hourly_aggregates_pk
    ON mv_hourly_aggregates (symbol, hour_start);

-- Index for time-based queries on materialized view
CREATE INDEX IF NOT EXISTS idx_mv_hourly_aggregates_time
    ON mv_hourly_aggregates (hour_start DESC);

COMMENT ON MATERIALIZED VIEW mv_hourly_aggregates IS
    'Pre-aggregated hourly data for dashboard performance. Refresh with REFRESH MATERIALIZED VIEW CONCURRENTLY mv_hourly_aggregates;';


-- ============================================================================
-- Daily Summary Materialized View
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_summary AS
SELECT
    symbol,
    date_trunc('day', window_start) AS trading_day,
    SUM(vwap * total_volume) / NULLIF(SUM(total_volume), 0) AS daily_vwap,
    SUM(total_volume) AS daily_volume,
    SUM(trade_count) AS daily_trade_count,
    MAX(max_price) AS daily_high,
    MIN(min_price) AS daily_low,
    -- First and last VWAP of the day (approximation)
    (ARRAY_AGG(vwap ORDER BY window_start ASC))[1] AS opening_vwap,
    (ARRAY_AGG(vwap ORDER BY window_start DESC))[1] AS closing_vwap
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '30 days'
GROUP BY symbol, date_trunc('day', window_start)
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_summary_pk
    ON mv_daily_summary (symbol, trading_day);

COMMENT ON MATERIALIZED VIEW mv_daily_summary IS
    'Daily OHLC-style summary for historical analysis';
