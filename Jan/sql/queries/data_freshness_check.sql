-- Q3: Data Freshness Check Query
-- Validates that streaming data is up-to-date
--
-- SLO: 99% of trades reflected in dashboard within 5 seconds
--
-- Usage: Run periodically or on-demand to validate freshness

-- Check 1: Latest window per symbol with staleness
SELECT
    symbol,
    MAX(window_start) as latest_window,
    MAX(updated_at) as last_update,
    NOW() - MAX(window_start) as window_staleness,
    NOW() - MAX(updated_at) as update_staleness,
    CASE
        WHEN NOW() - MAX(window_start) < INTERVAL '2 minutes' THEN 'FRESH'
        WHEN NOW() - MAX(window_start) < INTERVAL '5 minutes' THEN 'WARNING'
        ELSE 'STALE'
    END as status
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '1 hour'
GROUP BY symbol
ORDER BY window_staleness DESC;

-- Check 2: Overall freshness summary
SELECT
    COUNT(DISTINCT symbol) as symbols_active,
    MAX(NOW() - window_start) as max_staleness,
    MIN(NOW() - window_start) as min_staleness,
    AVG(NOW() - window_start) as avg_staleness,
    CASE
        WHEN MAX(NOW() - window_start) < INTERVAL '2 minutes' THEN 'HEALTHY'
        WHEN MAX(NOW() - window_start) < INTERVAL '5 minutes' THEN 'DEGRADED'
        ELSE 'UNHEALTHY'
    END as system_status
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '1 hour';

-- Check 3: Missing windows (gaps in data)
-- Expects continuous 1-minute windows during trading hours
WITH expected_windows AS (
    SELECT generate_series(
        date_trunc('minute', NOW() - INTERVAL '60 minutes'),
        date_trunc('minute', NOW() - INTERVAL '1 minute'),
        INTERVAL '1 minute'
    ) as expected_window
),
symbols AS (
    SELECT DISTINCT symbol FROM trade_aggregates
    WHERE window_start >= NOW() - INTERVAL '1 hour'
)
SELECT
    s.symbol,
    e.expected_window,
    CASE WHEN ta.window_start IS NULL THEN 'MISSING' ELSE 'OK' END as status
FROM expected_windows e
CROSS JOIN symbols s
LEFT JOIN trade_aggregates ta
    ON ta.symbol = s.symbol
    AND ta.window_start = e.expected_window
WHERE ta.window_start IS NULL
ORDER BY s.symbol, e.expected_window;

-- Check 4: Data freshness by hour (for historical analysis)
SELECT
    date_trunc('hour', window_start) as hour,
    COUNT(*) as aggregate_count,
    COUNT(DISTINCT symbol) as symbols,
    AVG(trade_count) as avg_trades_per_window,
    MAX(updated_at - window_start) as max_processing_delay
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '24 hours'
GROUP BY date_trunc('hour', window_start)
ORDER BY hour DESC;
