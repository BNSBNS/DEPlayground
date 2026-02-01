-- Migration: Create CQRS read model tables
--
-- These tables are optimized for specific query patterns and updated
-- asynchronously via projections from domain events.

-- Read model: VWAP Summary per symbol
-- Optimized for dashboard queries like "Show current VWAP for all symbols"
CREATE TABLE IF NOT EXISTS read_vwap_summary (
    symbol VARCHAR(20) PRIMARY KEY,
    current_vwap NUMERIC(18, 8),
    current_lmp NUMERIC(18, 8),
    vwap_1h NUMERIC(18, 8),
    vwap_24h NUMERIC(18, 8),
    total_volume_24h NUMERIC(18, 8),
    trade_count_24h INTEGER,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE read_vwap_summary IS 'CQRS read model: Pre-computed VWAP summaries per symbol';

-- Read model: Symbol Activity
-- Optimized for "Which symbols are actively trading?" queries
CREATE TABLE IF NOT EXISTS read_symbol_activity (
    symbol VARCHAR(20) PRIMARY KEY,
    last_trade_time TIMESTAMPTZ,
    trades_last_minute INTEGER DEFAULT 0,
    avg_trade_size NUMERIC(18, 8),
    is_active BOOLEAN DEFAULT FALSE,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE read_symbol_activity IS 'CQRS read model: Real-time trading activity per symbol';

-- Read model: LMP Breakdown
-- Optimized for energy market analysis queries
CREATE TABLE IF NOT EXISTS read_lmp_breakdown (
    symbol VARCHAR(20) PRIMARY KEY,
    zone VARCHAR(20),
    lmp_total NUMERIC(18, 8),
    lmp_energy NUMERIC(18, 8),
    lmp_congestion NUMERIC(18, 8),
    lmp_loss NUMERIC(18, 8),
    lmp_1h_ago NUMERIC(18, 8),
    lmp_24h_ago NUMERIC(18, 8),
    avg_congestion_24h NUMERIC(18, 8),
    max_congestion_24h NUMERIC(18, 8),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE read_lmp_breakdown IS 'CQRS read model: LMP breakdown for energy analysis';

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_read_vwap_summary_updated
ON read_vwap_summary (last_updated DESC);

CREATE INDEX IF NOT EXISTS idx_read_symbol_activity_active
ON read_symbol_activity (is_active, last_trade_time DESC)
WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_read_lmp_breakdown_congestion
ON read_lmp_breakdown (lmp_congestion DESC NULLS LAST);

-- Function to update read_vwap_summary from trade_aggregates
-- This can be called by a trigger or scheduled job
CREATE OR REPLACE FUNCTION update_vwap_summary(p_symbol VARCHAR(20))
RETURNS VOID AS $$
BEGIN
    INSERT INTO read_vwap_summary (symbol, current_vwap, current_lmp, vwap_1h, vwap_24h, total_volume_24h, trade_count_24h, last_updated)
    SELECT
        p_symbol,
        (SELECT vwap FROM trade_aggregates WHERE symbol = p_symbol ORDER BY window_start DESC LIMIT 1),
        (SELECT lmp FROM trade_aggregates WHERE symbol = p_symbol AND lmp IS NOT NULL ORDER BY window_start DESC LIMIT 1),
        (SELECT AVG(vwap) FROM trade_aggregates WHERE symbol = p_symbol AND window_start > NOW() - INTERVAL '1 hour'),
        (SELECT AVG(vwap) FROM trade_aggregates WHERE symbol = p_symbol AND window_start > NOW() - INTERVAL '24 hours'),
        (SELECT SUM(total_volume) FROM trade_aggregates WHERE symbol = p_symbol AND window_start > NOW() - INTERVAL '24 hours'),
        (SELECT SUM(trade_count) FROM trade_aggregates WHERE symbol = p_symbol AND window_start > NOW() - INTERVAL '24 hours'),
        NOW()
    ON CONFLICT (symbol) DO UPDATE SET
        current_vwap = EXCLUDED.current_vwap,
        current_lmp = EXCLUDED.current_lmp,
        vwap_1h = EXCLUDED.vwap_1h,
        vwap_24h = EXCLUDED.vwap_24h,
        total_volume_24h = EXCLUDED.total_volume_24h,
        trade_count_24h = EXCLUDED.trade_count_24h,
        last_updated = NOW();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_vwap_summary IS 'Updates CQRS read model from trade_aggregates';
