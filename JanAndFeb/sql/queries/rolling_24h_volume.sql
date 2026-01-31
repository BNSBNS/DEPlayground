-- Question 7: Rolling 24-hour traded volume per symbol
--
-- Calculates the cumulative traded volume over the last 24 hours
-- for each symbol, useful for liquidity assessment.
--
-- Performance Considerations:
-- - Uses BRIN index on window_start for efficient time filtering
-- - Partition pruning reduces scan to ~1-2 partitions (daily)
-- - Simple aggregation (SUM) is efficient even on large datasets
--
-- Scaling Strategy:
-- - For dashboards with sub-second latency requirements:
--   1. Use mv_daily_summary materialized view
--   2. Or pre-compute 24h rolling aggregates in a separate table
--   3. Or cache results at application level with 1-minute TTL
--
-- When moving to OLAP (StarRocks/ClickHouse):
-- - Same query works but executes much faster on columnar storage
-- - Consider using Aggregate Key Model for real-time pre-aggregation

SELECT
    symbol,
    SUM(total_volume) AS volume_24h,
    SUM(trade_count) AS trades_24h,
    -- VWAP over 24 hours
    SUM(vwap * total_volume) / NULLIF(SUM(total_volume), 0) AS vwap_24h,
    -- Price range
    MAX(max_price) AS high_24h,
    MIN(min_price) AS low_24h,
    -- Activity metrics
    COUNT(*) AS active_minutes,
    ROUND(COUNT(*)::numeric / (24 * 60) * 100, 2) AS activity_pct
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '24 hours'
GROUP BY symbol
ORDER BY volume_24h DESC;


-- Time-series version: Rolling 24h volume at each hour
-- Useful for trend analysis

SELECT
    symbol,
    date_trunc('hour', window_start) AS hour,
    SUM(total_volume) OVER (
        PARTITION BY symbol
        ORDER BY date_trunc('hour', window_start)
        RANGE BETWEEN INTERVAL '24 hours' PRECEDING AND CURRENT ROW
    ) AS rolling_24h_volume
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '48 hours'  -- Extra buffer for window
GROUP BY symbol, date_trunc('hour', window_start), total_volume
ORDER BY symbol, hour DESC;


-- Optimized version using hourly materialized view
-- (Significantly faster for large datasets)

-- SELECT
--     symbol,
--     SUM(hourly_volume) AS volume_24h,
--     SUM(hourly_trade_count) AS trades_24h,
--     SUM(hourly_vwap * hourly_volume) / NULLIF(SUM(hourly_volume), 0) AS vwap_24h
-- FROM mv_hourly_aggregates
-- WHERE hour_start >= NOW() - INTERVAL '24 hours'
-- GROUP BY symbol
-- ORDER BY volume_24h DESC;
