-- Superset Chart Queries for Energy Trading Platform
-- Import these into Superset SQL Lab and save as charts

-- ============================================
-- 1. VWAP Trend (Line Chart)
-- ============================================
SELECT
    window_start AS time,
    symbol,
    vwap
FROM trade_aggregates
WHERE window_start > NOW() - INTERVAL '24 hours'
ORDER BY window_start;


-- ============================================
-- 2. Volume by Symbol (Bar Chart)
-- ============================================
SELECT
    symbol,
    SUM(total_volume) AS total_volume,
    SUM(trade_count) AS total_trades
FROM trade_aggregates
WHERE window_start > NOW() - INTERVAL '24 hours'
GROUP BY symbol
ORDER BY total_volume DESC;


-- ============================================
-- 3. Hourly Volume Heatmap (Pivot Table)
-- ============================================
SELECT
    symbol,
    EXTRACT(HOUR FROM window_start) AS hour,
    SUM(total_volume) AS volume
FROM trade_aggregates
WHERE window_start > NOW() - INTERVAL '7 days'
GROUP BY symbol, EXTRACT(HOUR FROM window_start)
ORDER BY symbol, hour;


-- ============================================
-- 4. Price Volatility (High - Low spread)
-- ============================================
SELECT
    window_start AS time,
    symbol,
    max_price - min_price AS price_spread,
    (max_price - min_price) / NULLIF(vwap, 0) * 100 AS spread_pct
FROM trade_aggregates
WHERE window_start > NOW() - INTERVAL '1 hour'
ORDER BY window_start;


-- ============================================
-- 5. Top Symbols by Volume (Pie Chart)
-- ============================================
SELECT
    symbol,
    SUM(total_volume) AS volume
FROM trade_aggregates
WHERE window_start > NOW() - INTERVAL '1 hour'
GROUP BY symbol
ORDER BY volume DESC
LIMIT 10;


-- ============================================
-- 6. VWAP Summary Table
-- ============================================
SELECT
    symbol,
    AVG(vwap) AS avg_vwap,
    MIN(min_price) AS lowest_price,
    MAX(max_price) AS highest_price,
    SUM(total_volume) AS total_volume,
    SUM(trade_count) AS total_trades
FROM trade_aggregates
WHERE window_start > NOW() - INTERVAL '24 hours'
GROUP BY symbol
ORDER BY total_volume DESC;


-- ============================================
-- 7. Rolling 1-Hour VWAP (for Real-Time KPI)
-- ============================================
SELECT
    symbol,
    SUM(vwap * total_volume) / NULLIF(SUM(total_volume), 0) AS rolling_vwap,
    SUM(total_volume) AS volume,
    MAX(window_start) AS last_update
FROM trade_aggregates
WHERE window_start > NOW() - INTERVAL '1 hour'
GROUP BY symbol;


-- ============================================
-- 8. Market Activity Timeline
-- ============================================
SELECT
    date_trunc('minute', window_start) AS minute,
    COUNT(DISTINCT symbol) AS active_symbols,
    SUM(trade_count) AS trades,
    SUM(total_volume) AS volume
FROM trade_aggregates
WHERE window_start > NOW() - INTERVAL '1 hour'
GROUP BY date_trunc('minute', window_start)
ORDER BY minute;
