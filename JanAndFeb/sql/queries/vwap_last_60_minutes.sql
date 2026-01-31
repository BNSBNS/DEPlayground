-- Question 7: VWAP per symbol over the last 60 minutes
--
-- Calculates Volume Weighted Average Price for each symbol
-- over the most recent 60 minutes of data.
--
-- Performance Considerations:
-- - Uses index: idx_trade_aggregates_symbol_time (symbol, window_start DESC)
-- - Time filter enables partition pruning on window_start
-- - Aggregation is efficient due to pre-computed minute-level VWAP
--
-- Scaling Strategy:
-- - As data grows, partition pruning limits scan to recent partitions
-- - For very high query volume, use mv_hourly_aggregates materialized view
-- - Consider adding result caching at application level

SELECT
    symbol,
    -- Weighted average of minute VWAPs (weighted by their volumes)
    SUM(vwap * total_volume) / NULLIF(SUM(total_volume), 0) AS vwap_60min,
    SUM(total_volume) AS total_volume_60min,
    SUM(trade_count) AS total_trades_60min,
    MAX(max_price) AS high_60min,
    MIN(min_price) AS low_60min,
    COUNT(*) AS minutes_with_activity
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '60 minutes'
GROUP BY symbol
ORDER BY total_volume_60min DESC;


-- Alternative query using a specific time range (for testing/backtesting)
-- Replace the timestamp parameters as needed

-- SELECT
--     symbol,
--     SUM(vwap * total_volume) / NULLIF(SUM(total_volume), 0) AS vwap_60min,
--     SUM(total_volume) AS total_volume_60min,
--     SUM(trade_count) AS total_trades_60min
-- FROM trade_aggregates
-- WHERE window_start >= '2026-01-17 09:00:00+00'
--   AND window_start < '2026-01-17 10:00:00+00'
-- GROUP BY symbol
-- ORDER BY total_volume_60min DESC;


-- EXPLAIN ANALYZE version for performance tuning:
-- EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
-- SELECT symbol, SUM(vwap * total_volume) / NULLIF(SUM(total_volume), 0) AS vwap_60min
-- FROM trade_aggregates
-- WHERE window_start >= NOW() - INTERVAL '60 minutes'
-- GROUP BY symbol;
