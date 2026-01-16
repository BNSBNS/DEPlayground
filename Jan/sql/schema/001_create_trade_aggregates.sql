-- Energy Trading Platform - Trade Aggregates Schema
-- Question 6: Schema Design
--
-- This schema stores minute-level trade aggregates computed by the streaming consumer.
-- Design decisions:
-- 1. Composite PK (symbol, window_start) enables idempotent upserts
-- 2. NUMERIC(18,8) for exact decimal arithmetic (no floating point errors)
-- 3. Range partitioning by window_start for efficient time-range queries
-- 4. Timestamps with timezone for unambiguous UTC storage

-- Create extension for better timestamp handling
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main table: partitioned by time (monthly)
CREATE TABLE IF NOT EXISTS trade_aggregates (
    -- Composite primary key for idempotent upserts
    symbol VARCHAR(20) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,

    -- Aggregated metrics with trading-grade precision
    -- NUMERIC(18,8) supports up to 10 digits before decimal, 8 after
    vwap NUMERIC(18, 8) NOT NULL,
    total_volume NUMERIC(18, 8) NOT NULL CHECK (total_volume >= 0),
    trade_count INTEGER NOT NULL CHECK (trade_count >= 0),
    max_price NUMERIC(18, 8) NOT NULL CHECK (max_price >= 0),
    min_price NUMERIC(18, 8) NOT NULL CHECK (min_price >= 0),

    -- Audit timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Composite primary key
    PRIMARY KEY (symbol, window_start),

    -- Constraint: max_price >= min_price
    CONSTRAINT valid_price_range CHECK (max_price >= min_price),

    -- Constraint: window_end > window_start
    CONSTRAINT valid_window_range CHECK (window_end > window_start)
) PARTITION BY RANGE (window_start);

-- Create partitions for current and next few months
-- In production, use pg_partman for automatic partition management
CREATE TABLE IF NOT EXISTS trade_aggregates_2026_01
    PARTITION OF trade_aggregates
    FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2026-02-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS trade_aggregates_2026_02
    PARTITION OF trade_aggregates
    FOR VALUES FROM ('2026-02-01 00:00:00+00') TO ('2026-03-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS trade_aggregates_2026_03
    PARTITION OF trade_aggregates
    FOR VALUES FROM ('2026-03-01 00:00:00+00') TO ('2026-04-01 00:00:00+00');

-- Default partition for data outside defined ranges
CREATE TABLE IF NOT EXISTS trade_aggregates_default
    PARTITION OF trade_aggregates
    DEFAULT;


-- Raw trades table (optional, for debugging and replay)
-- In production, raw events would go to S3/cold storage
CREATE TABLE IF NOT EXISTS raw_trades (
    trade_id UUID PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    price NUMERIC(18, 8) NOT NULL CHECK (price >= 0),
    volume NUMERIC(18, 8) NOT NULL CHECK (volume > 0),
    side VARCHAR(4) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    trader_id VARCHAR(50) NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- DLQ tracking table (for monitoring failed messages)
CREATE TABLE IF NOT EXISTS dlq_messages (
    id BIGSERIAL PRIMARY KEY,
    original_message TEXT NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    failed_at TIMESTAMPTZ NOT NULL,
    consumer_group VARCHAR(100) NOT NULL,
    kafka_partition INTEGER NOT NULL,
    kafka_offset BIGINT NOT NULL,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at on trade_aggregates
DROP TRIGGER IF EXISTS update_trade_aggregates_updated_at ON trade_aggregates;
CREATE TRIGGER update_trade_aggregates_updated_at
    BEFORE UPDATE ON trade_aggregates
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- Comments for documentation
COMMENT ON TABLE trade_aggregates IS 'Minute-level trade aggregates computed by streaming consumer';
COMMENT ON COLUMN trade_aggregates.symbol IS 'Trading symbol (e.g., POWER_DE, GAS_NL)';
COMMENT ON COLUMN trade_aggregates.window_start IS 'Start of the 1-minute aggregation window (UTC)';
COMMENT ON COLUMN trade_aggregates.vwap IS 'Volume Weighted Average Price = sum(price*volume) / sum(volume)';
COMMENT ON COLUMN trade_aggregates.total_volume IS 'Sum of all trade volumes in the window';
COMMENT ON COLUMN trade_aggregates.trade_count IS 'Number of trades in the window';

COMMENT ON TABLE raw_trades IS 'Raw trade events for debugging (production uses S3/cold storage)';
COMMENT ON TABLE dlq_messages IS 'Dead Letter Queue messages for monitoring failed processing';
