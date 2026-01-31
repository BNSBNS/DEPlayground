# End-to-End Architecture

## Question 1: System Design & Architecture

This document describes the architecture of the Energy Trading Platform, a real-time analytics system that ingests energy trade events and produces trader-facing metrics with sub-second latency.

---

## Architecture Diagram

```
                                    ENERGY TRADING PLATFORM
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                 │
    │   ┌──────────────┐                                                              │
    │   │  External    │                                                              │
    │   │  APIs        │                                                              │
    │   │ (EPEX, Nord  │                                                              │
    │   │  Pool, etc.) │                                                              │
    │   └──────┬───────┘                                                              │
    │          │                                                                      │
    │          ▼                                                                      │
    │   ┌──────────────┐     ┌─────────────────────────────────────────────────┐     │
    │   │   Trade      │     │                  KAFKA CLUSTER                  │     │
    │   │   Producer   │────▶│  ┌─────────────┐  ┌─────────────┐               │     │
    │   │  (Python K8s │     │  │   trades    │  │ trades-dlq  │               │     │
    │   │   Pod)       │     │  │  (6 parts)  │  │  (3 parts)  │               │     │
    │   └──────────────┘     │  └─────────────┘  └─────────────┘               │     │
    │                        │         │                 ▲                      │     │
    │                        │         │                 │ (malformed           │     │
    │                        │         │                 │  messages)           │     │
    │                        └─────────┼─────────────────┼─────────────────────┘     │
    │                                  │                 │                            │
    │                                  ▼                 │                            │
    │                        ┌─────────────────┐         │                            │
    │                        │    Streaming    │─────────┘                            │
    │                        │    Consumer     │                                      │
    │                        │  (Python K8s   │                                      │
    │                        │   Pods x 2-6)  │                                      │
    │                        │                │                                      │
    │                        │ ┌────────────┐ │                                      │
    │                        │ │  Windowed  │ │                                      │
    │                        │ │ Aggregator │ │                                      │
    │                        │ │ (1-min)    │ │                                      │
    │                        │ └────────────┘ │                                      │
    │                        └───────┬────────┘                                      │
    │                                │                                               │
    │          ┌─────────────────────┼─────────────────────┐                        │
    │          │                     │                     │                        │
    │          ▼                     ▼                     ▼                        │
    │   ┌─────────────┐      ┌─────────────┐       ┌─────────────┐                 │
    │   │ PostgreSQL  │      │  StarRocks  │       │   S3 Data   │                 │
    │   │   (OLTP)    │      │   (OLAP)    │       │    Lake     │                 │
    │   │             │      │             │       │  (Parquet)  │                 │
    │   │ • Minute    │      │ • Dashboard │       │             │                 │
    │   │   aggregates│      │   queries   │       │ • Raw logs  │                 │
    │   │ • Recent    │      │ • Sub-sec   │       │ • Backtest  │                 │
    │   │   data      │      │   latency   │       │   data      │                 │
    │   └─────────────┘      └─────────────┘       └─────────────┘                 │
    │        HOT                  HOT                   COLD                        │
    │       PATH                 PATH                  PATH                         │
    │                                                                               │
    └───────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Deep Dive

### A. Ingestion Layer (Trade Producer)

**Component:** Python service running as Kubernetes pods

**Function:**
- Connect to external APIs (EPEX, Nord Pool, simulated in this implementation)
- Normalize incoming data to a strict schema (Pydantic models)
- Publish to Kafka with symbol as message key

**Key Design Decision:** Data is never written directly from an API to a database. If a database is unavailable, market ticks must not be lost. Kafka serves as a durable, persistent buffer.

**Configuration:**
```python
# Producer settings for trading-grade durability
acks = "all"  # Wait for all replicas
enable.idempotence = True  # Exactly-once producer semantics
```

### B. Message Bus (Kafka)

**Configuration:**
- `acks=all`: All replicas must acknowledge
- Replication factor: 3 (production) / 1 (development)
- Partitions: 6 (allows up to 6 parallel consumers)
- Retention: 7 days

**Topics:**
| Topic | Partitions | Purpose |
|-------|------------|---------|
| `trades` | 6 | Main trade events |
| `trades-dlq` | 3 | Dead Letter Queue for failed messages |

**Rationale:** In trading systems, durability is more important than throughput. Price updates cannot be sent on a fire-and-forget basis.

### C. Stream Processing (Consumer)

**Component:** Python consumers running as Kubernetes pods (consumer group)

**Logic:**
- 1-minute tumbling windows based on event time
- VWAP (Volume Weighted Average Price) calculation
- Max/min price, total volume, trade count per window

**State Management:**
- In-memory window state (simple, fast)
- State recovery via replay from last committed offset
- Idempotent writes ensure correctness after replay

**Scaling:**
- Multiple consumers form a Kafka consumer group
- Each consumer handles a subset of partitions
- HPA scales based on consumer lag metric

### D. Storage Strategy

#### Hot Storage (PostgreSQL - OLTP)

**Use Cases:**
- Minute-level aggregates for recent data
- Transactional writes with ACID guarantees
- Complex joins and updates

**Optimizations:**
- Time-based partitioning (monthly)
- BRIN indexes for time-series queries
- Materialized views for common aggregations

**When PostgreSQL Works:**
- Moderate query volumes
- Complex analytical queries with joins
- Recent data (last 7-30 days)

#### Hot Storage (StarRocks - OLAP) [Future]

**Use Cases:**
- Dashboard queries aggregating millions of rows
- Sub-second latency requirements
- Read-heavy workloads

**When to Move to OLAP:**
- Query latency exceeds 1 second on PostgreSQL
- Data volume exceeds billions of rows
- Need real-time pre-aggregation

#### Cold Storage (S3 Data Lake) [Future]

**Use Cases:**
- Raw event logs for audit and replay
- Historical data for backtesting
- Long-term retention (years)

**Format:** Parquet (columnar, compressed)

**Implementation:** Kafka Connect S3 Sink

---

## Why Kafka Instead of Direct Database Writes

1. **Decoupling:** Producer and consumer can evolve independently
2. **Durability:** Messages persist even if database is unavailable
3. **Scalability:** Add consumers without changing producer
4. **Replay:** Reprocess historical data by resetting offsets
5. **Backpressure:** Kafka absorbs spikes, database writes smoothly

---

## Scalability

### Horizontal Scaling

| Component | Scaling Strategy |
|-----------|------------------|
| Producer | Single instance (sufficient for most use cases) |
| Kafka | Add partitions, add brokers |
| Consumer | Add replicas (up to partition count) |
| PostgreSQL | Read replicas, partitioning, or move to OLAP |

### Consumer Scaling with HPA

```yaml
metrics:
- type: External
  external:
    metric:
      name: kafka_consumergroup_lag
    target:
      type: AverageValue
      averageValue: "1000"  # Scale up when lag > 1000
```

---

## Latency and Backpressure Handling

### Latency Optimization

| Layer | Target | Strategy |
|-------|--------|----------|
| Producer → Kafka | < 10ms | Batching with 5ms linger |
| Kafka → Consumer | < 50ms | Fast polling, minimal fetch delay |
| Consumer → DB | < 100ms | Batch writes, connection pooling |
| **End-to-end** | < 1s | Event time windows, not processing time |

### Backpressure Handling

1. **Kafka Buffer:** Absorbs producer spikes
2. **Consumer Lag:** Monitored, triggers HPA scaling
3. **Database Backpressure:** Connection pool limits, exponential backoff
4. **Alert:** Lag > 10,000 messages for > 5 minutes

---

## Correctness Across Restarts and Failures

### At-Least-Once + Idempotency = Exactly-Once Effect

1. **Consumer commits offset only after successful DB write**
2. **Database uses `INSERT ... ON CONFLICT DO UPDATE`**
3. **On restart, consumer replays from last committed offset**
4. **Duplicate writes are handled by upsert (no data corruption)**

### State Recovery

```
Crash → Restart → Resume from last offset → Replay → Idempotent writes → Correct state
```

---

## OLTP vs OLAP Boundary

| Characteristic | PostgreSQL (OLTP) | StarRocks (OLAP) |
|---------------|-------------------|------------------|
| **Data Age** | Last 7-30 days | All historical |
| **Query Pattern** | Point lookups, joins | Aggregations, scans |
| **Latency** | 10-100ms (small data) | 10-100ms (large data) |
| **Write Pattern** | Streaming upserts | Batch/streaming |
| **Scaling** | Vertical + partitions | Horizontal |

**Transition Trigger:** When PostgreSQL query latency exceeds SLO (e.g., > 500ms P99)

---

## Historical Data Flow to Cold Storage

```
Kafka (trades topic)
       │
       ├──► Consumer (aggregates → PostgreSQL)
       │
       └──► Kafka Connect S3 Sink ──► S3 (Parquet)
                                           │
                                           ▼
                                    Quantitative Analysts
                                    (Backtesting, ML)
```

**Implementation:** Kafka Connect with S3 Sink Connector
- Format: Parquet (columnar, compressed)
- Partitioning: By date (year/month/day)
- Retention: Indefinite (cost-effective on S3)
