-- Dashboard Views for Energy Trading Platform
-- These views power the pre-built Superset dashboards
-- ============================================================================

-- ============================================================================
-- 1. REAL-TIME OVERVIEW: Last 24 hours summary by symbol
-- ============================================================================
CREATE OR REPLACE VIEW v_symbol_24h_summary AS
SELECT
    symbol,
    COUNT(*) as window_count,
    SUM(trade_count) as total_trades,
    SUM(total_volume) as total_volume,
    ROUND(AVG(vwap)::numeric, 4) as avg_vwap,
    ROUND(MIN(min_price)::numeric, 4) as period_low,
    ROUND(MAX(max_price)::numeric, 4) as period_high,
    ROUND((MAX(max_price) - MIN(min_price))::numeric, 4) as price_spread,
    MIN(window_start) as first_trade_window,
    MAX(window_start) as last_trade_window
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '24 hours'
GROUP BY symbol
ORDER BY total_volume DESC;

COMMENT ON VIEW v_symbol_24h_summary IS 'Last 24 hours trading summary by symbol';

-- ============================================================================
-- 2. VWAP TIME SERIES: For line charts over time
-- ============================================================================
CREATE OR REPLACE VIEW v_vwap_timeseries AS
SELECT
    symbol,
    window_start,
    vwap,
    total_volume,
    trade_count,
    -- Price range for candlestick-like visualization
    min_price,
    max_price,
    -- Spread percentage
    CASE
        WHEN min_price > 0 THEN ROUND(((max_price - min_price) / min_price * 100)::numeric, 2)
        ELSE 0
    END as spread_pct
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '24 hours'
ORDER BY symbol, window_start;

COMMENT ON VIEW v_vwap_timeseries IS 'VWAP and price data over time for charting';

-- ============================================================================
-- 3. VOLUME HEATMAP: Trading activity by hour and symbol
-- ============================================================================
CREATE OR REPLACE VIEW v_volume_heatmap AS
SELECT
    symbol,
    EXTRACT(DOW FROM window_start) as day_of_week,
    EXTRACT(HOUR FROM window_start) as hour_of_day,
    SUM(total_volume) as volume,
    SUM(trade_count) as trades,
    COUNT(*) as windows
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '7 days'
GROUP BY symbol, EXTRACT(DOW FROM window_start), EXTRACT(HOUR FROM window_start)
ORDER BY symbol, day_of_week, hour_of_day;

COMMENT ON VIEW v_volume_heatmap IS 'Volume heatmap by day of week and hour';

-- ============================================================================
-- 4. TOP MOVERS: Biggest price changes
-- ============================================================================
CREATE OR REPLACE VIEW v_top_movers AS
WITH hourly_agg AS (
    SELECT
        symbol,
        DATE_TRUNC('hour', window_start) as hour,
        FIRST_VALUE(vwap) OVER (PARTITION BY symbol, DATE_TRUNC('hour', window_start) ORDER BY window_start) as open_vwap,
        LAST_VALUE(vwap) OVER (PARTITION BY symbol, DATE_TRUNC('hour', window_start) ORDER BY window_start
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as close_vwap,
        SUM(total_volume) OVER (PARTITION BY symbol, DATE_TRUNC('hour', window_start)) as hour_volume
    FROM trade_aggregates
    WHERE window_start >= NOW() - INTERVAL '24 hours'
),
distinct_hourly AS (
    SELECT DISTINCT symbol, hour, open_vwap, close_vwap, hour_volume
    FROM hourly_agg
)
SELECT
    symbol,
    hour,
    open_vwap,
    close_vwap,
    hour_volume,
    ROUND((close_vwap - open_vwap)::numeric, 4) as price_change,
    CASE
        WHEN open_vwap > 0 THEN ROUND(((close_vwap - open_vwap) / open_vwap * 100)::numeric, 2)
        ELSE 0
    END as pct_change
FROM distinct_hourly
ORDER BY ABS((close_vwap - open_vwap) / NULLIF(open_vwap, 0)) DESC NULLS LAST;

COMMENT ON VIEW v_top_movers IS 'Symbols with biggest hourly price changes';

-- ============================================================================
-- 5. TRADING VELOCITY: Trades per minute over time
-- ============================================================================
CREATE OR REPLACE VIEW v_trading_velocity AS
SELECT
    DATE_TRUNC('minute', window_start) as minute,
    SUM(trade_count) as trades_per_minute,
    SUM(total_volume) as volume_per_minute,
    COUNT(DISTINCT symbol) as active_symbols,
    ROUND(AVG(vwap)::numeric, 4) as avg_vwap
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '6 hours'
GROUP BY DATE_TRUNC('minute', window_start)
ORDER BY minute;

COMMENT ON VIEW v_trading_velocity IS 'Trading velocity metrics over time';

-- ============================================================================
-- 6. LMP BREAKDOWN: Location Marginal Pricing analysis (when available)
-- ============================================================================
CREATE OR REPLACE VIEW v_lmp_breakdown AS
SELECT
    symbol,
    window_start,
    lmp,
    lmp_energy,
    lmp_congestion,
    lmp_loss,
    -- Component percentages
    CASE WHEN lmp > 0 THEN ROUND((lmp_energy / lmp * 100)::numeric, 1) ELSE 0 END as energy_pct,
    CASE WHEN lmp > 0 THEN ROUND((lmp_congestion / lmp * 100)::numeric, 1) ELSE 0 END as congestion_pct,
    CASE WHEN lmp > 0 THEN ROUND((lmp_loss / lmp * 100)::numeric, 1) ELSE 0 END as loss_pct,
    vwap,
    total_volume
FROM trade_aggregates
WHERE lmp IS NOT NULL
  AND window_start >= NOW() - INTERVAL '24 hours'
ORDER BY window_start DESC;

COMMENT ON VIEW v_lmp_breakdown IS 'LMP component breakdown for pricing analysis';

-- ============================================================================
-- 7. CUMULATIVE VOLUME: Running total volume by symbol
-- ============================================================================
CREATE OR REPLACE VIEW v_cumulative_volume AS
SELECT
    symbol,
    window_start,
    total_volume,
    SUM(total_volume) OVER (PARTITION BY symbol ORDER BY window_start) as cumulative_volume,
    SUM(trade_count) OVER (PARTITION BY symbol ORDER BY window_start) as cumulative_trades
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '24 hours'
ORDER BY symbol, window_start;

COMMENT ON VIEW v_cumulative_volume IS 'Cumulative volume and trade counts by symbol';

-- ============================================================================
-- 8. PRICE BANDS: Bollinger-like price bands (20-period moving average)
-- ============================================================================
CREATE OR REPLACE VIEW v_price_bands AS
SELECT
    symbol,
    window_start,
    vwap,
    AVG(vwap) OVER (PARTITION BY symbol ORDER BY window_start ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as ma_20,
    STDDEV(vwap) OVER (PARTITION BY symbol ORDER BY window_start ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as std_20,
    AVG(vwap) OVER (PARTITION BY symbol ORDER BY window_start ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)
        + 2 * STDDEV(vwap) OVER (PARTITION BY symbol ORDER BY window_start ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as upper_band,
    AVG(vwap) OVER (PARTITION BY symbol ORDER BY window_start ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)
        - 2 * STDDEV(vwap) OVER (PARTITION BY symbol ORDER BY window_start ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as lower_band,
    total_volume
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '24 hours'
ORDER BY symbol, window_start;

COMMENT ON VIEW v_price_bands IS 'VWAP with 20-period moving average and Bollinger bands';

-- ============================================================================
-- 9. DLQ MONITORING: Failed message statistics
-- ============================================================================
CREATE OR REPLACE VIEW v_dlq_stats AS
SELECT
    DATE_TRUNC('hour', failed_at) as hour,
    error_type,
    COUNT(*) as error_count,
    COUNT(*) FILTER (WHERE processed = false) as pending_count,
    COUNT(*) FILTER (WHERE processed = true) as resolved_count
FROM dlq_messages
WHERE failed_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE_TRUNC('hour', failed_at), error_type
ORDER BY hour DESC, error_count DESC;

COMMENT ON VIEW v_dlq_stats IS 'Dead Letter Queue statistics for monitoring';

-- ============================================================================
-- 10. REAL-TIME KPIs: Current state metrics
-- ============================================================================
CREATE OR REPLACE VIEW v_realtime_kpis AS
SELECT
    (SELECT COUNT(DISTINCT symbol) FROM trade_aggregates
     WHERE window_start >= NOW() - INTERVAL '5 minutes') as active_symbols_5m,
    (SELECT SUM(trade_count) FROM trade_aggregates
     WHERE window_start >= NOW() - INTERVAL '1 hour') as trades_last_hour,
    (SELECT SUM(total_volume) FROM trade_aggregates
     WHERE window_start >= NOW() - INTERVAL '1 hour') as volume_last_hour,
    (SELECT ROUND(AVG(vwap)::numeric, 4) FROM trade_aggregates
     WHERE window_start >= NOW() - INTERVAL '1 hour') as avg_vwap_last_hour,
    (SELECT MAX(window_start) FROM trade_aggregates) as last_update,
    (SELECT COUNT(*) FROM dlq_messages WHERE processed = false) as pending_dlq_messages;

COMMENT ON VIEW v_realtime_kpis IS 'Real-time KPI metrics for dashboard big numbers';

-- ============================================================================
-- Grant permissions (if needed for specific roles)
-- ============================================================================
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO superset_reader;
-- GRANT SELECT ON ALL VIEWS IN SCHEMA public TO superset_reader;
