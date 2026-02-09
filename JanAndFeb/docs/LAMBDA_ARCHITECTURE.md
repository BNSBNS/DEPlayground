# Lambda Architecture (Reference Documentation)

> **Note**: This platform uses the **Unified (Lakehouse)** architecture as the primary implementation.
> This document describes Lambda architecture for educational reference and comparison.

## Overview

Lambda Architecture is a data processing pattern designed to handle both real-time and batch processing by maintaining three layers:

```
                         ┌─────────────────────────────────────────────┐
                         │              BATCH LAYER                     │
                    ┌───▶│  Raw Data → Batch Processing → Batch Views  │──┐
                    │    │  (High latency, complete data)              │  │
                    │    └─────────────────────────────────────────────┘  │
                    │                                                     │
┌──────────┐    ┌───┴───┐                                                 ▼
│  Data    │───▶│Master │                                          ┌───────────┐
│  Source  │    │Dataset│                                          │  SERVING  │
└──────────┘    └───┬───┘                                          │   LAYER   │
                    │                                              │           │
                    │    ┌─────────────────────────────────────┐   │ (Merge)   │
                    └───▶│         SPEED LAYER                 │───▶│           │
                         │  Real-time Processing → Speed Views │   └───────────┘
                         │  (Low latency, incremental data)    │
                         └─────────────────────────────────────┘
```

## Three Layers Explained

### 1. Batch Layer

**Purpose**: Process ALL historical data to produce accurate, complete views.

**Characteristics**:
- High latency (hours to days)
- Processes complete dataset
- Produces "batch views"
- Handles late-arriving data through recomputation
- Idempotent operations

**For Energy Trading Platform**:
```python
# Batch job example using DuckDB
def compute_daily_vwap_batch(date: str):
    conn = duckdb.connect()

    # Read all raw events from S3/MinIO
    result = conn.execute("""
        SELECT
            symbol,
            DATE_TRUNC('minute', event_timestamp) as window_start,
            SUM(price * volume) / SUM(volume) as vwap,
            SUM(volume) as total_volume,
            COUNT(*) as trade_count
        FROM read_parquet('s3://data-lake/raw/trades/date=?/*.parquet')
        GROUP BY symbol, DATE_TRUNC('minute', event_timestamp)
    """, [date])

    # Write batch views
    result.write_parquet(f's3://data-lake/batch-views/vwap/date={date}/')
```

### 2. Speed Layer

**Purpose**: Provide real-time views using only recent data.

**Characteristics**:
- Low latency (seconds to minutes)
- Processes only recent/incremental data
- Produces "speed views" (real-time)
- Eventually overwritten by batch views
- Approximate but fast

**For Energy Trading Platform**:
```python
# This is what our current consumer does
class StreamingConsumer:
    def process_event(self, event):
        # Real-time windowed aggregation
        aggregates = self.aggregator.add_trade(event)

        # Write to speed views (PostgreSQL/TimescaleDB)
        for agg in aggregates:
            self.db.upsert(agg)
```

### 3. Serving Layer

**Purpose**: Merge batch and speed views for queries.

**Characteristics**:
- Serves queries from both layers
- Batch views provide historical accuracy
- Speed views provide recent data
- Merge point determines cutoff

**For Energy Trading Platform**:
```python
class ServingLayer:
    def get_vwap(self, symbol: str, start: datetime, end: datetime):
        # Batch views are accurate up to T-1 hour
        batch_cutoff = datetime.now() - timedelta(hours=1)

        # Get historical from batch views
        batch_data = self.batch_store.query(
            symbol, start, min(end, batch_cutoff)
        )

        # Get recent from speed views
        speed_data = self.speed_store.query(
            symbol, max(start, batch_cutoff), end
        )

        # Merge (speed takes precedence for overlap)
        return self._merge_views(batch_data, speed_data)
```

## Implementation Components

### Required Services

```yaml
# docker-compose-lambda.yml
services:
  # Master Dataset Storage
  minio:
    image: minio/minio
    ports:
      - "9000:9000"
      - "9001:9001"
    command: server /data --console-address ":9001"

  # Kafka Connect for S3 Sink
  kafka-connect:
    image: confluentinc/cp-kafka-connect:7.5.0
    depends_on:
      - kafka
      - minio
    environment:
      CONNECT_BOOTSTRAP_SERVERS: kafka:29092
      CONNECT_GROUP_ID: kafka-connect

  # Batch Processing (Spark)
  spark-master:
    image: bitnami/spark:3.5
    environment:
      SPARK_MODE: master

  # Speed Layer (existing)
  consumer:
    # ... existing streaming consumer

  # Serving Layer
  api:
    # ... existing API with merge logic
```

### Kafka Connect S3 Sink

```json
{
  "name": "s3-sink-trades",
  "config": {
    "connector.class": "io.confluent.connect.s3.S3SinkConnector",
    "topics": "trades",
    "s3.bucket.name": "data-lake",
    "s3.region": "us-east-1",
    "flush.size": "10000",
    "rotate.interval.ms": "3600000",
    "format.class": "io.confluent.connect.s3.format.parquet.ParquetFormat",
    "partitioner.class": "io.confluent.connect.storage.partitioner.TimeBasedPartitioner",
    "partition.duration.ms": "3600000",
    "path.format": "'raw/trades/'year'='YYYY/'month'='MM/'day'='dd/'hour'='HH",
    "timestamp.extractor": "Record"
  }
}
```

### Batch Job (Airflow DAG)

```python
# airflow/dags/daily_batch_aggregates.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'energy-trading',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'daily_batch_aggregates',
    default_args=default_args,
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
) as dag:

    compute_vwap = PythonOperator(
        task_id='compute_vwap_aggregates',
        python_callable=compute_daily_vwap_batch,
        op_kwargs={'date': '{{ ds }}'},
    )

    compute_lmp = PythonOperator(
        task_id='compute_lmp_aggregates',
        python_callable=compute_daily_lmp_batch,
        op_kwargs={'date': '{{ ds }}'},
    )

    compute_vwap >> compute_lmp
```

## Lambda vs Unified (Lakehouse) Comparison

| Aspect | Lambda | Unified (Lakehouse) |
|--------|--------|---------------------|
| **Codebases** | Two (batch + streaming) | One |
| **Consistency** | Eventual (batch overwrites) | ACID transactions |
| **Complexity** | Higher (two systems) | Lower |
| **Late Data** | Batch recomputation | Upserts with time travel |
| **Debugging** | Harder (two paths) | Easier (single path) |
| **Reprocessing** | Separate batch job | Same code, different mode |
| **Technology** | Spark batch + Kafka Streams | Delta Lake/Iceberg |

## Why We Chose Unified (Lakehouse) Instead

1. **Single Codebase**: One processing logic for both batch and streaming
2. **ACID Transactions**: No eventual consistency issues
3. **Time Travel**: Can query historical versions for debugging
4. **Schema Evolution**: Easier to evolve data models
5. **Better for Learning**: Less operational complexity
6. **Energy Market Fit**: Better audit trail for REMIT/MiFID II compliance

## When Lambda Makes Sense

- Existing Spark/Hadoop infrastructure
- Very high volume (PB scale)
- Need for sub-second latency (speed layer only)
- Legacy systems that can't be migrated
- Team expertise in Spark ecosystem

## Implementation References

For Lambda architecture examples:
- [Apache Beam](https://beam.apache.org/) - Unified batch/streaming API
- [Spark Structured Streaming](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html)
- [Nathan Marz's Big Data](http://nathanmarz.com/blog/how-to-beat-the-cap-theorem.html) - Original Lambda paper
