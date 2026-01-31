-- Question 7: Top 5 symbols by total volume in the last hour
--
-- Identifies the most actively traded symbols by volume.
-- Critical for market monitoring and liquidity assessment.
--
-- Performance Considerations:
-- - Simple GROUP BY with ORDER BY LIMIT is efficient
-- - Uses idx_trade_aggregates_volume partial index
-- - Time filter enables partition pruning
--
-- Scaling Strategy:
-- - For sub-second latency with millions of rows:
--   1. Use hourly materialized view (mv_hourly_aggregates)
--   2. Pre-compute rankings in scheduled job
--   3. Cache results with short TTL
--
-- When moving to OLAP (StarRocks/ClickHouse):
-- - Columnar storage makes this query extremely fast
-- - Consider using Aggregate Key Model for real-time rankings

-- Top 5 symbols by volume in last hour
SELECT
    symbol,
    SUM(total_volume) AS volume_1h,
    SUM(trade_count) AS trades_1h,
    SUM(vwap * total_volume) / NULLIF(SUM(total_volume), 0) AS vwap_1h,
    MAX(max_price) AS high_1h,
    MIN(min_price) AS low_1h,
    COUNT(*) AS active_minutes
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY symbol
ORDER BY volume_1h DESC
LIMIT 5;


-- Extended version with percentage of total market volume
WITH hourly_stats AS (
    SELECT
        symbol,
        SUM(total_volume) AS volume_1h,
        SUM(trade_count) AS trades_1h,
        SUM(vwap * total_volume) / NULLIF(SUM(total_volume), 0) AS vwap_1h
    FROM trade_aggregates
    WHERE window_start >= NOW() - INTERVAL '1 hour'
    GROUP BY symbol
),
total_market AS (
    SELECT SUM(volume_1h) AS total_volume FROM hourly_stats
)
SELECT
    hs.symbol,
    hs.volume_1h,
    hs.trades_1h,
    hs.vwap_1h,
    ROUND((hs.volume_1h / NULLIF(tm.total_volume, 0) * 100)::numeric, 2) AS market_share_pct
FROM hourly_stats hs
CROSS JOIN total_market tm
ORDER BY hs.volume_1h DESC
LIMIT 5;


-- Top symbols with comparison to 24h average
WITH
hourly_volume AS (
    SELECT
        symbol,
        SUM(total_volume) AS volume_1h
    FROM trade_aggregates
    WHERE window_start >= NOW() - INTERVAL '1 hour'
    GROUP BY symbol
),
daily_avg AS (
    SELECT
        symbol,
        SUM(total_volume) / 24 AS avg_hourly_volume
    FROM trade_aggregates
    WHERE window_start >= NOW() - INTERVAL '24 hours'
    GROUP BY symbol
)
SELECT
    hv.symbol,
    hv.volume_1h,
    da.avg_hourly_volume,
    ROUND(
        ((hv.volume_1h - da.avg_hourly_volume) / NULLIF(da.avg_hourly_volume, 0) * 100)::numeric,
        2
    ) AS volume_change_pct,
    CASE
        WHEN hv.volume_1h > da.avg_hourly_volume * 1.5 THEN 'HIGH'
        WHEN hv.volume_1h < da.avg_hourly_volume * 0.5 THEN 'LOW'
        ELSE 'NORMAL'
    END AS activity_level
FROM hourly_volume hv
LEFT JOIN daily_avg da ON hv.symbol = da.symbol
ORDER BY hv.volume_1h DESC
LIMIT 5;


-- Time-series of top symbols (for charting)
SELECT
    symbol,
    date_trunc('hour', window_start) AS hour,
    SUM(total_volume) AS hourly_volume
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '24 hours'
  AND symbol IN (
      SELECT symbol
      FROM trade_aggregates
      WHERE window_start >= NOW() - INTERVAL '1 hour'
      GROUP BY symbol
      ORDER BY SUM(total_volume) DESC
      LIMIT 5
  )
GROUP BY symbol, date_trunc('hour', window_start)
ORDER BY symbol, hour DESC;
