# CDC, SCD, and Data Caching Strategy

## Q4: Change Data Capture (CDC) and Slowly Changing Dimensions (SCD)

---

## Table of Contents

1. [CDC Relevance](#1-cdc-relevance)
2. [SCD Relevance](#2-scd-relevance)
3. [Data Caching Strategy](#3-data-caching-strategy)
4. [Implementation Examples](#4-implementation-examples)

---

## 1. CDC Relevance

### What is CDC?

Change Data Capture tracks and captures changes in a database, enabling:
- Real-time data replication
- Event sourcing from database changes
- Sync between systems

### Is CDC Relevant Here?

**Partially.** Our architecture already uses event streaming (Kafka), which is conceptually similar to CDC.

| Aspect | Traditional CDC | Our Architecture |
|--------|-----------------|------------------|
| Source | Database changes | Trade events from API |
| Transport | CDC tool (Debezium) | Kafka producer |
| Consumer | Downstream DB | Streaming consumer |
| Use case | DB replication | Real-time analytics |

### Where CDC Could Apply

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ PostgreSQL  │─────▶│  Debezium   │─────▶│    Kafka    │
│ (changes)   │ CDC  │             │      │             │
└─────────────┘      └─────────────┘      └─────────────┘
                                                │
                                                ▼
                                         ┌─────────────┐
                                         │ Data Lake   │
                                         │ (S3/Parquet)│
                                         └─────────────┘
```

**Use Cases for CDC in This Project:**

1. **Audit Trail**: Capture all changes to `trade_aggregates` for compliance
2. **Data Lake Sync**: Replicate PostgreSQL to S3 for analytics
3. **Cross-region Replication**: Sync to disaster recovery site

### CDC Implementation (If Needed)

```yaml
# docker-compose.yml addition for Debezium CDC
debezium:
  image: debezium/connect:2.4
  environment:
    BOOTSTRAP_SERVERS: kafka:9092
    GROUP_ID: debezium-postgres
    CONFIG_STORAGE_TOPIC: debezium-configs
    OFFSET_STORAGE_TOPIC: debezium-offsets

# Connector configuration
# POST to http://debezium:8083/connectors
{
  "name": "postgres-cdc",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres",
    "database.port": "5432",
    "database.user": "trading",
    "database.password": "trading",
    "database.dbname": "trades",
    "table.include.list": "public.trade_aggregates",
    "topic.prefix": "cdc"
  }
}
```

---

## 2. SCD Relevance

### What is SCD?

Slowly Changing Dimensions track historical changes to dimension data over time.

| Type | Description | Example |
|------|-------------|---------|
| **SCD Type 1** | Overwrite (no history) | Current price only |
| **SCD Type 2** | Add new row (full history) | All price changes |
| **SCD Type 3** | Add column (limited history) | Current + previous price |

### Is SCD Relevant Here?

**Partially relevant** for reference data, **not for aggregates**.

| Data Type | SCD Relevance | Our Approach |
|-----------|---------------|--------------|
| Trade aggregates | No | Immutable windows (1 row per window) |
| Symbol metadata | Yes (Type 2) | Would track name/exchange changes |
| Trader info | Yes (Type 2) | Would track permission changes |

### Current Implementation

Our `trade_aggregates` table is **not SCD** - it's event-driven:

```sql
-- Each (symbol, window_start) is unique and immutable after window closes
-- This is NOT SCD - it's time-series data
INSERT INTO trade_aggregates (symbol, window_start, vwap, ...)
ON CONFLICT (symbol, window_start) DO UPDATE SET ...
```

### SCD Type 2 Implementation (For Reference Data)

```sql
-- Q4: SCD Type 2 for symbol reference data (if needed)
CREATE TABLE symbol_dimension (
    symbol_key SERIAL PRIMARY KEY,       -- Surrogate key
    symbol VARCHAR(20) NOT NULL,          -- Business key
    symbol_name VARCHAR(100),
    exchange VARCHAR(50),
    currency VARCHAR(3),

    -- SCD Type 2 columns
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to TIMESTAMPTZ,                 -- NULL = current
    is_current BOOLEAN NOT NULL DEFAULT TRUE,

    CONSTRAINT unique_current_symbol UNIQUE (symbol, is_current)
        WHERE is_current = TRUE
);

-- Insert new version when data changes
-- 1. Close current record
UPDATE symbol_dimension
SET valid_to = NOW(), is_current = FALSE
WHERE symbol = 'POWER_DE' AND is_current = TRUE;

-- 2. Insert new record
INSERT INTO symbol_dimension (symbol, symbol_name, exchange, currency)
VALUES ('POWER_DE', 'German Power (updated)', 'EPEX', 'EUR');
```

---

## 3. Data Caching Strategy

### Is Caching Relevant Here?

**Yes, for query optimization.** Not for stream processing.

| Layer | Caching Strategy | Tool |
|-------|------------------|------|
| Application | In-memory cache | Python dict / Redis |
| Database | Materialized views | PostgreSQL |
| API | Response cache | Redis / CDN |

### Current Implementation

We already use **materialized views** as a form of caching:

```sql
-- From sql/schema/002_create_indexes.sql
CREATE MATERIALIZED VIEW mv_hourly_aggregates AS
SELECT
    symbol,
    date_trunc('hour', window_start) AS hour_start,
    SUM(vwap * total_volume) / NULLIF(SUM(total_volume), 0) AS hourly_vwap,
    ...
FROM trade_aggregates
WHERE window_start >= NOW() - INTERVAL '7 days'
GROUP BY symbol, date_trunc('hour', window_start);

-- Refresh periodically (e.g., every 5 minutes via cron)
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_hourly_aggregates;
```

### Redis Caching (If Needed)

```python
# Q7: Redis caching for API responses
import redis
import json
from datetime import timedelta

class TradingCache:
    """Redis-based cache for trading queries."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
        self.default_ttl = timedelta(seconds=30)

    def get_vwap(self, symbol: str) -> dict | None:
        """Get cached VWAP for symbol."""
        key = f"vwap:{symbol}"
        data = self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    def set_vwap(self, symbol: str, vwap_data: dict) -> None:
        """Cache VWAP for symbol."""
        key = f"vwap:{symbol}"
        self.redis.setex(
            key,
            self.default_ttl,
            json.dumps(vwap_data)
        )

    def invalidate_symbol(self, symbol: str) -> None:
        """Invalidate cache for symbol."""
        pattern = f"*:{symbol}"
        for key in self.redis.scan_iter(pattern):
            self.redis.delete(key)


# Usage in consumer
class CachingConsumer:
    def __init__(self):
        self.cache = TradingCache()

    def on_aggregate_written(self, aggregate):
        """Update cache when new aggregate is written."""
        self.cache.set_vwap(aggregate.symbol, {
            'vwap': str(aggregate.vwap),
            'volume': str(aggregate.total_volume),
            'window_start': aggregate.window_start.isoformat(),
        })
```

### Caching Strategy Comparison

| Strategy | Latency | Freshness | Complexity | Use Case |
|----------|---------|-----------|------------|----------|
| No cache | High | Real-time | Simple | Low traffic |
| Materialized View | Medium | 5-15 min | Medium | Dashboards |
| Redis TTL | Low | 30-60s | Medium | API responses |
| Write-through | Low | Real-time | High | Critical paths |

### When NOT to Cache

- **Stream processing**: Don't cache intermediate state (use in-memory windows)
- **Financial accuracy**: Critical calculations should query source
- **Low-volume queries**: Caching adds complexity without benefit

---

## 4. Implementation Examples

### CDC with Debezium (Reference)

```python
# Consume CDC events from Debezium
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'cdc.public.trade_aggregates',
    bootstrap_servers=['localhost:9092'],
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

for message in consumer:
    cdc_event = message.value
    operation = cdc_event['op']  # 'c'=create, 'u'=update, 'd'=delete

    if operation == 'c':
        # New aggregate created
        after = cdc_event['after']
        sync_to_data_lake(after)
    elif operation == 'u':
        # Aggregate updated (late event)
        after = cdc_event['after']
        update_in_data_lake(after)
```

### SCD Type 2 Lookup

```python
# Query current symbol metadata
def get_current_symbol(symbol: str) -> dict:
    sql = """
        SELECT * FROM symbol_dimension
        WHERE symbol = %(symbol)s AND is_current = TRUE
    """
    return db.execute(sql, {'symbol': symbol}).fetchone()

# Query historical symbol at specific time
def get_symbol_at_time(symbol: str, as_of: datetime) -> dict:
    sql = """
        SELECT * FROM symbol_dimension
        WHERE symbol = %(symbol)s
          AND valid_from <= %(as_of)s
          AND (valid_to IS NULL OR valid_to > %(as_of)s)
    """
    return db.execute(sql, {'symbol': symbol, 'as_of': as_of}).fetchone()
```

---

## Summary

| Concept | Relevant? | Current Implementation |
|---------|-----------|----------------------|
| CDC | Partially | Use Kafka directly; CDC for DB→Lake sync |
| SCD | Partially | Not needed for aggregates; useful for reference data |
| Caching | Yes | Materialized views; Redis optional for API |

### Recommendations

1. **CDC**: Add Debezium only if you need DB→Data Lake replication
2. **SCD**: Implement Type 2 only for dimension tables (symbols, traders)
3. **Caching**: Materialized views are sufficient; add Redis for high-traffic API
