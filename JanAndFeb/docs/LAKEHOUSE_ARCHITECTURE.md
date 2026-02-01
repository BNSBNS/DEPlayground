# Unified (Lakehouse) Architecture

## Overview

The Lakehouse architecture combines the best of data lakes and data warehouses:
- **Data Lake benefits**: Low-cost storage, schema flexibility, raw data access
- **Data Warehouse benefits**: ACID transactions, schema enforcement, BI tool support

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        UNIFIED LAKEHOUSE ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐     ┌─────────────────────────────────────────────────┐   │
│  │   Kafka     │────▶│                  BRONZE LAYER                    │   │
│  │  (trades)   │     │  Raw events, append-only, minimal transformation │   │
│  └─────────────┘     │  Partitioned by date for efficient queries       │   │
│                      └───────────────────────┬─────────────────────────┘   │
│                                              │                              │
│  ┌─────────────┐                             ▼                              │
│  │ Batch Files │     ┌─────────────────────────────────────────────────┐   │
│  │ (CSV/Pqt)   │────▶│                  SILVER LAYER                    │   │
│  └─────────────┘     │  Validated, deduplicated, schema-enforced        │   │
│                      │  Quality checks, data lineage tracking           │   │
│                      └───────────────────────┬─────────────────────────┘   │
│                                              │                              │
│                                              ▼                              │
│                      ┌─────────────────────────────────────────────────┐   │
│                      │                   GOLD LAYER                     │   │
│                      │  Aggregated (VWAP, LMP), business-ready          │   │
│                      │  Optimized for dashboards and analytics          │   │
│                      └───────────────────────┬─────────────────────────┘   │
│                                              │                              │
│                                              ▼                              │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │  Grafana  │  │ Superset  │  │  PowerBI  │  │   API     │               │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Medallion Architecture (Bronze → Silver → Gold)

### Bronze Layer (Raw)

**Purpose**: Store raw data exactly as received

**Location**: `src/lakehouse/bronze.py`

**Characteristics**:
- Append-only writes
- No transformations
- Preserves original data for debugging
- Partitioned by ingestion date

**Schema**:
```python
BronzeRecord:
  - data: dict           # Original JSON payload
  - _ingested_at: datetime
  - _source: str         # "kafka", "batch", "api"
  - _kafka_offset: int   # For replay capability
  - _file_name: str      # For batch lineage
```

**Usage**:
```python
from src.lakehouse import BronzeLayer

bronze = BronzeLayer(storage_path="./data/lakehouse/bronze/trades")

# From Kafka
bronze.write_from_kafka(message, partition=0, offset=12345)

# From batch file
bronze.write_from_file(records, file_name="trades_2024_01.csv")
```

### Silver Layer (Validated)

**Purpose**: Clean, validate, and deduplicate data

**Location**: `src/lakehouse/silver.py`

**Characteristics**:
- Schema enforcement (Pydantic models)
- Data quality checks
- Deduplication by trade_id
- Invalid records → quarantine

**Transformations**:
1. Parse JSON to typed models
2. Validate against TradeEvent schema
3. Run quality checks (completeness, validity, timeliness)
4. Deduplicate using trade_id
5. Route invalid to quarantine

**Schema**:
```python
SilverRecord:
  - trade_id: UUID
  - symbol: str
  - price: Decimal
  - volume: Decimal
  - side: TradeSide
  - trader_id: str
  - event_timestamp: datetime
  - _bronze_file: str      # Lineage
  - _processed_at: datetime
  - _quality_score: float
```

**Usage**:
```python
from src.lakehouse import SilverLayer

silver = SilverLayer(
    storage_path="./data/lakehouse/silver/trades",
    quarantine_path="./data/lakehouse/quarantine",
    quality_threshold=0.5,
)

# Process Bronze records
stats = silver.process_batch(bronze.read_partition("2024-01-15"))
# {'valid': 9500, 'invalid': 300, 'duplicate': 200, 'total': 10000}
```

### Gold Layer (Aggregated)

**Purpose**: Business-ready aggregations

**Location**: `src/lakehouse/gold.py`

**Characteristics**:
- Pre-computed VWAP, LMP
- Time-windowed aggregates
- Optimized for BI queries
- Both streaming and batch modes

**Schema**:
```python
GoldAggregate:
  - symbol: str
  - window_start: datetime
  - window_end: datetime
  - vwap: Decimal
  - total_volume: Decimal
  - trade_count: int
  - max_price: Decimal
  - min_price: Decimal
  - lmp: Decimal
  - lmp_energy: Decimal
  - lmp_congestion: Decimal
  - lmp_loss: Decimal
  - price_volatility: Decimal
  - avg_trade_size: Decimal
```

**Usage**:
```python
from src.lakehouse import GoldLayer

gold = GoldLayer(
    storage_path="./data/lakehouse/gold/aggregates",
    window_duration_seconds=60,
)

# Streaming mode (from Kafka consumer)
completed = gold.add_trade(symbol, price, volume, timestamp)

# Batch mode (recompute from Silver)
stats = gold.process_silver_batch(silver.read_records())
```

## Technology Stack

### Storage: MinIO (S3-Compatible)

```yaml
minio:
  image: minio/minio
  ports:
    - "9000:9000"  # API
    - "9001:9001"  # Console
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
  command: server /data --console-address ":9001"
```

### Table Format: Delta Lake (Recommended)

For production, use Delta Lake for ACID transactions:

```python
# With delta-rs (Python native Delta Lake)
from deltalake import DeltaTable, write_deltalake

# Write to Delta table
write_deltalake(
    "s3://bucket/silver/trades",
    df,
    mode="append",
    partition_by=["date"],
)

# Read with time travel
dt = DeltaTable("s3://bucket/silver/trades")
df = dt.to_pandas(version=5)  # Read version 5
```

### Processing: DuckDB (Local) / Spark (Production)

**DuckDB for local development**:
```python
import duckdb

conn = duckdb.connect()

# Query directly from Parquet/S3
result = conn.execute("""
    SELECT symbol, SUM(volume)
    FROM read_parquet('s3://bucket/silver/trades/**/*.parquet')
    WHERE event_timestamp >= '2024-01-01'
    GROUP BY symbol
""").fetchdf()
```

**Spark for production scale**:
```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .config("spark.jars.packages", "io.delta:delta-spark_2.12:3.0.0") \
    .getOrCreate()

# Read Delta table
df = spark.read.format("delta").load("s3://bucket/silver/trades")

# Streaming from Delta
stream = spark.readStream.format("delta").load("s3://bucket/silver/trades")
```

## Docker Compose for Lakehouse

```yaml
# docker-compose-lakehouse.yml
version: "3.8"

services:
  minio:
    image: minio/minio
    container_name: minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin123}
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

  minio-init:
    image: minio/mc
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set myminio http://minio:9000 minioadmin minioadmin123;
      mc mb myminio/data-lake --ignore-existing;
      mc mb myminio/data-lake/bronze --ignore-existing;
      mc mb myminio/data-lake/silver --ignore-existing;
      mc mb myminio/data-lake/gold --ignore-existing;
      "

volumes:
  minio_data:
```

## Benefits for Energy Trading

### 1. ACID Transactions
```python
# Concurrent writes are safe
with DeltaTable.transaction("s3://bucket/gold/aggregates") as tx:
    tx.update(
        predicate="symbol = 'POWER_DE'",
        set={"lmp": new_lmp}
    )
```

### 2. Time Travel (Audit Trail)
```python
# Query historical versions for REMIT compliance
dt = DeltaTable("s3://bucket/silver/trades")

# What did the data look like yesterday?
yesterday = dt.to_pandas(version=100)

# Restore to previous version if needed
dt.restore(version=99)
```

### 3. Schema Evolution
```python
# Add LMP columns without breaking existing queries
dt = DeltaTable("s3://bucket/gold/aggregates")
dt.alter_table().add_column("lmp_congestion", "DECIMAL(18,8)").execute()
```

### 4. Unified Batch + Streaming
```python
# Same Gold layer handles both
gold = GoldLayer(storage_path="s3://bucket/gold/aggregates")

# Streaming mode
gold.add_trade(symbol, price, volume, timestamp)

# Batch recomputation
gold.process_silver_batch(silver.read_records())
```

## Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────┐   │
│  │ Finnhub  │ │DexPaprika│ │ ENTSO-E  │ │ Batch Files (CSV) │   │
│  │ (WebSocket)│ │  (SSE)   │ │(Polling) │ │                   │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────────┬─────────┘   │
└───────┼────────────┼────────────┼─────────────────┼─────────────┘
        │            │            │                 │
        └────────────┴────────────┴─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │     KAFKA       │
                    │   (trades)      │
                    └────────┬────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────┐
        │              BRONZE LAYER                   │
        │  s3://data-lake/bronze/trades/             │
        │  - Raw JSON events                         │
        │  - Partitioned by date                     │
        │  - Append-only                             │
        └────────────────────┬───────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────┐
        │              SILVER LAYER                   │
        │  s3://data-lake/silver/trades/             │
        │  - Validated records                       │
        │  - Deduplicated                            │
        │  - Quality score attached                  │
        └────────────────────┬───────────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────┐
        │               GOLD LAYER                    │
        │  s3://data-lake/gold/aggregates/           │
        │  - VWAP per minute                         │
        │  - LMP with components                     │
        │  - BI-ready format                         │
        └────────────────────┬───────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
    ┌─────────┐        ┌─────────┐        ┌─────────┐
    │ Grafana │        │Superset │        │ PowerBI │
    └─────────┘        └─────────┘        └─────────┘
```

## Migration Path from Current Architecture

### Phase 1: Add Bronze Layer (Week 1)
1. Deploy MinIO
2. Add Bronze writer to Kafka consumer
3. Continue writing to TimescaleDB (dual write)

### Phase 2: Add Silver Layer (Week 2)
1. Implement Silver processing
2. Add quality checks
3. Set up quarantine

### Phase 3: Add Gold Layer (Week 3)
1. Port aggregation logic to Gold layer
2. Add LMP calculation
3. Test dual-write consistency

### Phase 4: Cutover (Week 4)
1. Update API to read from Gold
2. Remove TimescaleDB dependency (optional)
3. Set up Delta Lake for ACID

## Related Documentation

- [src/lakehouse/bronze.py](../src/lakehouse/bronze.py) - Bronze implementation
- [src/lakehouse/silver.py](../src/lakehouse/silver.py) - Silver implementation
- [src/lakehouse/gold.py](../src/lakehouse/gold.py) - Gold implementation
- [LAMBDA_ARCHITECTURE.md](./LAMBDA_ARCHITECTURE.md) - Lambda comparison
- [ADVANCED_ARCHITECTURE.md](./ADVANCED_ARCHITECTURE.md) - Persistent state, OpenTelemetry
