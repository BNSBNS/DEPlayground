-- ============================================================================
-- Energy Trading Platform - Sample SQL Lab Queries
-- ============================================================================
-- Copy these queries into Superset SQL Lab to explore your data
-- ============================================================================


-- ============================================================================
-- 1. REAL-TIME OVERVIEW: Current trading activity
-- ============================================================================
-- Shows trading summary for the last hour, sorted by volume
SELECT
    symbol,
    COUNT(*) as windows,
    SUM(trade_count) as total_trades,
    ROUND(SUM(total_volume)::numeric, 2) as total_volume,
    ROUND(AVG(vwap)::numeric, 4) as avg_vwap,
    ROUND(MIN(min_price)::numeric, 4) as low,
    ROUND(MAX(max_price)::numeric, 4) as high
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY symbol
ORDER BY total_volume DESC;


-- ============================================================================
-- 2. VWAP TREND: Price movement over the last 6 hours
-- ============================================================================
-- Shows how VWAP has changed over time for each symbol
SELECT
    symbol,
    DATE_TRUNC('hour', window_start) as hour,
    ROUND(AVG(vwap)::numeric, 4) as hourly_vwap,
    SUM(total_volume) as hourly_volume,
    SUM(trade_count) as hourly_trades
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '6 hours'
GROUP BY symbol, DATE_TRUNC('hour', window_start)
ORDER BY symbol, hour;


-- ============================================================================
-- 3. PRICE VOLATILITY: Symbols with highest price spread
-- ============================================================================
-- Identifies most volatile symbols based on price range
SELECT
    symbol,
    ROUND(MIN(min_price)::numeric, 4) as period_low,
    ROUND(MAX(max_price)::numeric, 4) as period_high,
    ROUND((MAX(max_price) - MIN(min_price))::numeric, 4) as spread,
    ROUND(((MAX(max_price) - MIN(min_price)) / NULLIF(AVG(vwap), 0) * 100)::numeric, 2) as spread_pct
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '24 hours'
GROUP BY symbol
HAVING AVG(vwap) > 0
ORDER BY spread_pct DESC;


-- ============================================================================
-- 4. TRADING ACTIVITY HEATMAP DATA: Volume by hour of day
-- ============================================================================
-- Use this for creating heatmap visualizations
SELECT
    symbol,
    EXTRACT(HOUR FROM window_start) as hour_of_day,
    SUM(total_volume) as volume,
    SUM(trade_count) as trades,
    COUNT(*) as data_points
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '7 days'
GROUP BY symbol, EXTRACT(HOUR FROM window_start)
ORDER BY symbol, hour_of_day;


-- ============================================================================
-- 5. TOP PERFORMERS: Best price movers in last 24h
-- ============================================================================
-- Compares opening and closing prices to find winners
WITH price_changes AS (
    SELECT
        symbol,
        FIRST_VALUE(vwap) OVER (PARTITION BY symbol ORDER BY window_start) as open_price,
        LAST_VALUE(vwap) OVER (PARTITION BY symbol ORDER BY window_start
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) as close_price,
        SUM(total_volume) OVER (PARTITION BY symbol) as total_vol
    FROM trade_aggregates
    WHERE window_start >= NOW() - INTERVAL '24 hours'
)
SELECT DISTINCT
    symbol,
    ROUND(open_price::numeric, 4) as open_price,
    ROUND(close_price::numeric, 4) as close_price,
    ROUND((close_price - open_price)::numeric, 4) as change,
    ROUND(((close_price - open_price) / NULLIF(open_price, 0) * 100)::numeric, 2) as change_pct,
    ROUND(total_vol::numeric, 2) as volume
FROM price_changes
WHERE open_price > 0
ORDER BY change_pct DESC;


-- ============================================================================
-- 6. LMP COMPONENT BREAKDOWN (if LMP data available)
-- ============================================================================
-- Analyzes Location Marginal Pricing components
SELECT
    symbol,
    DATE_TRUNC('hour', window_start) as hour,
    ROUND(AVG(lmp)::numeric, 4) as avg_lmp,
    ROUND(AVG(lmp_energy)::numeric, 4) as avg_energy,
    ROUND(AVG(lmp_congestion)::numeric, 4) as avg_congestion,
    ROUND(AVG(lmp_loss)::numeric, 4) as avg_loss,
    -- Percentages
    ROUND(AVG(lmp_energy / NULLIF(lmp, 0) * 100)::numeric, 1) as energy_pct,
    ROUND(AVG(lmp_congestion / NULLIF(lmp, 0) * 100)::numeric, 1) as congestion_pct
FROM trade_aggregates
WHERE lmp IS NOT NULL
  AND window_start >= NOW() - INTERVAL '24 hours'
GROUP BY symbol, DATE_TRUNC('hour', window_start)
ORDER BY symbol, hour;


-- ============================================================================
-- 7. CONGESTION EVENTS: High congestion pricing periods
-- ============================================================================
-- Finds times when congestion component was significant
SELECT
    symbol,
    window_start,
    ROUND(lmp::numeric, 4) as lmp,
    ROUND(lmp_congestion::numeric, 4) as congestion,
    ROUND((lmp_congestion / NULLIF(lmp, 0) * 100)::numeric, 1) as congestion_pct,
    total_volume
FROM trade_aggregates
WHERE lmp IS NOT NULL
  AND lmp_congestion > 0
  AND (lmp_congestion / NULLIF(lmp, 0)) > 0.1  -- Congestion > 10% of total
ORDER BY congestion_pct DESC
LIMIT 50;


-- ============================================================================
-- 8. DATA QUALITY CHECK: Missing or sparse data
-- ============================================================================
-- Identifies symbols with gaps in data
WITH time_series AS (
    SELECT generate_series(
        NOW() - INTERVAL '24 hours',
        NOW(),
        INTERVAL '1 minute'
    ) as expected_time
),
coverage AS (
    SELECT
        symbol,
        COUNT(DISTINCT DATE_TRUNC('minute', window_start)) as actual_windows,
        1440 as expected_windows,  -- 24 hours * 60 minutes
        MIN(window_start) as first_seen,
        MAX(window_start) as last_seen
    FROM trade_aggregates
    WHERE window_start >= NOW() - INTERVAL '24 hours'
    GROUP BY symbol
)
SELECT
    symbol,
    actual_windows,
    expected_windows,
    ROUND((actual_windows::float / expected_windows * 100)::numeric, 1) as coverage_pct,
    first_seen,
    last_seen,
    NOW() - last_seen as time_since_last_trade
FROM coverage
ORDER BY coverage_pct ASC;


-- ============================================================================
-- 9. DLQ ANALYSIS: Failed message patterns
-- ============================================================================
-- Analyzes dead letter queue for error patterns
SELECT
    DATE_TRUNC('hour', failed_at) as hour,
    error_type,
    COUNT(*) as error_count,
    COUNT(*) FILTER (WHERE processed = false) as unresolved,
    MIN(failed_at) as first_error,
    MAX(failed_at) as last_error
FROM dlq_messages
WHERE failed_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE_TRUNC('hour', failed_at), error_type
ORDER BY hour DESC, error_count DESC;


-- ============================================================================
-- 10. REAL-TIME KPI DASHBOARD
-- ============================================================================
-- Single row with all key metrics
SELECT
    -- Activity metrics
    (SELECT COUNT(DISTINCT symbol) FROM trade_aggregates
     WHERE window_start >= NOW() - INTERVAL '5 minutes') as active_symbols_5min,

    -- Volume metrics (last hour)
    (SELECT SUM(trade_count) FROM trade_aggregates
     WHERE window_start >= NOW() - INTERVAL '1 hour') as trades_last_hour,

    (SELECT ROUND(SUM(total_volume)::numeric, 2) FROM trade_aggregates
     WHERE window_start >= NOW() - INTERVAL '1 hour') as volume_last_hour,

    -- Price metrics
    (SELECT ROUND(AVG(vwap)::numeric, 4) FROM trade_aggregates
     WHERE window_start >= NOW() - INTERVAL '1 hour') as avg_vwap_last_hour,

    -- System health
    (SELECT MAX(window_start) FROM trade_aggregates) as last_update,

    (SELECT COUNT(*) FROM dlq_messages WHERE processed = false) as pending_dlq,

    -- Total all-time
    (SELECT COUNT(*) FROM trade_aggregates) as total_windows_all_time;


-- ============================================================================
-- 11. MINUTE-BY-MINUTE DETAIL: Drill-down for specific symbol
-- ============================================================================
-- Replace 'YOUR_SYMBOL' with the symbol you want to analyze
SELECT
    window_start,
    window_end,
    vwap,
    total_volume,
    trade_count,
    min_price,
    max_price,
    max_price - min_price as spread,
    lmp,
    lmp_energy,
    lmp_congestion,
    lmp_loss
FROM trade_aggregates
WHERE symbol = 'YOUR_SYMBOL'  -- Change this!
  AND window_start >= NOW() - INTERVAL '1 hour'
ORDER BY window_start DESC;


-- ============================================================================
-- 12. SYMBOL COMPARISON: Side-by-side metrics
-- ============================================================================
-- Compare key metrics across multiple symbols
SELECT
    symbol,
    ROUND(AVG(vwap)::numeric, 4) as avg_vwap,
    ROUND(STDDEV(vwap)::numeric, 4) as vwap_stddev,
    ROUND(SUM(total_volume)::numeric, 2) as total_volume,
    SUM(trade_count) as total_trades,
    ROUND(AVG(trade_count)::numeric, 1) as avg_trades_per_window,
    ROUND(MIN(min_price)::numeric, 4) as period_low,
    ROUND(MAX(max_price)::numeric, 4) as period_high
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '24 hours'
GROUP BY symbol
ORDER BY total_volume DESC
LIMIT 20;
