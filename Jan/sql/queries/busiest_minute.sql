-- Question 7: Busiest trading minute per symbol (highest trade count)
--
-- Finds the minute with the highest number of trades for each symbol.
-- Useful for identifying periods of high market activity/volatility.
--
-- Performance Considerations:
-- - Uses window function RANK() for efficient top-N per group
-- - Index on (symbol, window_start) supports the partition/order
-- - Filter by time range to limit scan scope
--
-- Scaling Strategy:
-- - Add time filter to limit scan to relevant period
-- - For real-time dashboards, maintain a separate "top minutes" table
--   updated incrementally as new aggregates arrive
-- - OLAP engines handle this query pattern very efficiently

-- Busiest minute per symbol in the last 24 hours
WITH ranked_minutes AS (
    SELECT
        symbol,
        window_start,
        trade_count,
        total_volume,
        vwap,
        max_price,
        min_price,
        RANK() OVER (
            PARTITION BY symbol
            ORDER BY trade_count DESC, total_volume DESC
        ) AS activity_rank
    FROM trade_aggregates
    WHERE window_start >= NOW() - INTERVAL '24 hours'
)
SELECT
    symbol,
    window_start AS busiest_minute,
    trade_count,
    total_volume,
    vwap,
    max_price,
    min_price
FROM ranked_minutes
WHERE activity_rank = 1
ORDER BY trade_count DESC;


-- Top 5 busiest minutes per symbol (for analysis)
WITH ranked_minutes AS (
    SELECT
        symbol,
        window_start,
        trade_count,
        total_volume,
        vwap,
        RANK() OVER (
            PARTITION BY symbol
            ORDER BY trade_count DESC
        ) AS activity_rank
    FROM trade_aggregates
    WHERE window_start >= NOW() - INTERVAL '24 hours'
)
SELECT
    symbol,
    window_start AS minute,
    trade_count,
    total_volume,
    vwap,
    activity_rank
FROM ranked_minutes
WHERE activity_rank <= 5
ORDER BY symbol, activity_rank;


-- Busiest minute overall (across all symbols)
SELECT
    symbol,
    window_start AS busiest_minute,
    trade_count,
    total_volume,
    vwap
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '24 hours'
ORDER BY trade_count DESC
LIMIT 10;


-- Hourly breakdown of peak activity
SELECT
    symbol,
    date_trunc('hour', window_start) AS hour,
    MAX(trade_count) AS peak_trades_per_minute,
    SUM(trade_count) AS total_trades,
    AVG(trade_count)::numeric(10,2) AS avg_trades_per_minute
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '24 hours'
GROUP BY symbol, date_trunc('hour', window_start)
ORDER BY symbol, hour DESC;
