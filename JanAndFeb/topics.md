# Energy Trading Real-Time Analytics Platform - Study Guide

A comprehensive study guide covering Kafka fundamentals, architecture patterns, ingestion services, consumer windowing, and deployment modes.

---

## Table of Contents

0. [Learning Path for Beginners](#learning-path-for-beginners)
1. [Topic 2: Kafka Fundamentals](#topic-2-kafka-fundamentals)
2. [Topic 1: Architecture Deep-Dive](#topic-1-architecture-deep-dive)
3. [Topic 3: Ingestion Service](#topic-3-ingestion-service)
4. [Topic 4: Consumer & Windowing](#topic-4-consumer--windowing)
5. [Topic 5: Docker & Deployment](#topic-5-docker--deployment)
6. [Topic 6: Kafka Message Size & Large Message Handling](#topic-6-kafka-message-size--large-message-handling)
7. [Experimentation Plan](#experimentation-plan)

---

## Learning Path for Beginners

### Philosophy: Input → Process → Output

Every file in this repo follows one pattern. Ask yourself:

> "What does this file **receive**, what does it **do**, and what does it **produce**?"

---

### Layer 0: Run First, Read Later (Day 1-2)

**Goal:** See the system work before understanding it.

```bash
# Start everything
docker-compose -f docker-compose-full.yml --profile local up -d

# Watch data flow (keep this running)
docker-compose -f docker-compose-full.yml logs -f producer consumer
```

**What you'll see:**
```
producer  | Published: STOCK_AAPL @ $175.23
producer  | Published: CRYPTO_BTC @ $43521.00
consumer  | Aggregated window: STOCK_AAPL, VWAP: $175.45, trades: 12
consumer  | Written to DB: STOCK_AAPL
```

**You learned:** Data flows Producer → Kafka → Consumer → Database

---

### Layer 1: The Data (Day 3-4)

**Goal:** Understand what a "trade" looks like.

**One file only:** `src/common/models.py`

```
┌─────────────────────────────────────────────────────────────┐
│                    models.py                                │
│                                                             │
│  TradeEvent (what producer creates)                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ trade_id: UUID          # Unique identifier         │   │
│  │ symbol: str             # "STOCK_AAPL"              │   │
│  │ price: Decimal          # 175.23                    │   │
│  │ volume: Decimal         # 100                       │   │
│  │ side: TradeSide         # BUY or SELL               │   │
│  │ trader_id: str          # "trader_001"              │   │
│  │ event_timestamp: datetime                           │   │
│  └─────────────────────────────────────────────────────┘   │
│                            ↓                                │
│                    (after aggregation)                      │
│                            ↓                                │
│  TradeAggregate (what consumer produces)                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ symbol: str             # "STOCK_AAPL"              │   │
│  │ window_start: datetime  # 10:00:00                  │   │
│  │ window_end: datetime    # 10:01:00                  │   │
│  │ vwap: Decimal           # 175.45 (weighted avg)     │   │
│  │ total_volume: Decimal   # 1500                      │   │
│  │ trade_count: int        # 12                        │   │
│  │ max_price / min_price                               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

Consumer has **2 roles**:
1) To consume TradeEvent from kafka(input),
2) Producing TradeAggregate by computing the windowed aggregation output to database.

**Exercise:** Open `models.py`, find `TradeEvent`, count its fields.

---

### Layer 2: Producer Side (Day 5-7)

**Goal:** Understand how trades are created and sent to Kafka.

**Files (read in order):**

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────┐
│ 1. config.py     │────▶│ 2. kafka_utils.py│────▶│ 3. kafka_    │
│                  │     │                  │     │   producer.py│
│ WHERE to send    │     │ HOW to connect   │     │ WHAT to send │
└──────────────────┘     └──────────────────┘     └──────────────┘
     Lines 85-120             Lines 19-63            Full file
```

**File Linkage Detail:**

| File | Receives | Does | Produces | Imports From |
|------|----------|------|----------|--------------|
| `config.py` | Environment vars | Defines settings | `KafkaSettings` object | - |
| `kafka_utils.py` | `KafkaSettings` | Creates Kafka client | `Producer` instance | `config.py` |
| `kafka_producer.py` | `Producer` + data | Serializes & sends | Messages in Kafka | `kafka_utils.py`, `models.py` |

**Code path to trace:**

```python
# src/common/config.py:37-64
class KafkaSettings:
    bootstrap_servers: str = "localhost:9092"
    topic: str = "trades"
                    │
                    ▼
# kafka_utils.py:19-40
def create_kafka_producer(config: KafkaSettings) -> Producer:
    producer_config = {
        "bootstrap.servers": config.bootstrap_servers,  # ← uses config
        "acks": "all",
        "enable.idempotence": True,
    }
    return Producer(producer_config)
                    │
                    ▼
# kafka_producer.py:45-80
class TradeProducer:
    def __init__(self, config: KafkaSettings):
        self._producer = create_kafka_producer(config)  # ← uses kafka_utils
        self._topic = config.topic

    def publish(self, event: TradeEvent):
        self._producer.produce(
            topic=self._topic,
            key=event.to_kafka_key(),      # ← uses models.py
            value=json.dumps(event.to_kafka_value()),
        )
```

**Exercise:** Add `print(f"Sending to {self._topic}")` in `kafka_producer.py`, rebuild, see your change.

---

### Layer 3: Consumer Side (Day 8-12)

**Goal:** Understand how trades are read, aggregated, and stored.

**Files (read in order):**

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────┐
│ 1. kafka_utils.py│────▶│ 2. windowed_     │────▶│ 3. db_writer │
│    (consumer)    │     │   aggregator.py  │     │    .py       │
│                  │     │                  │     │              │
│ HOW to read      │     │ HOW to aggregate │     │ HOW to store │
└──────────────────┘     └──────────────────┘     └──────────────┘
     Lines 66-111           Lines 150-350          (if exists)
         │                       │
         │                       │
         └───────────┬───────────┘
                     ▼
            ┌──────────────────┐
            │ 4. kafka_        │
            │   consumer.py    │
            │                  │
            │ ORCHESTRATES all │
            └──────────────────┘
```

**File Linkage Detail:**

| File | Receives | Does | Produces | Imports From |
|------|----------|------|----------|--------------|
| `kafka_utils.py` | `KafkaSettings` | Creates consumer | `Consumer` instance | `config.py` |
| `windowed_aggregator.py` | `TradeEvent` | Groups by time window | `TradeAggregate` | `models.py` |
| `kafka_consumer.py` | Kafka messages | Orchestrates flow | DB writes | All above |

**The aggregation flow:**

```
Kafka Message arrives
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│ kafka_consumer.py                                             │
│                                                               │
│   msg = consumer.poll()                                       │
│   trade = TradeEvent.from_kafka_value(msg)  ←─── models.py   │
│                         │                                     │
│                         ▼                                     │
│   ┌─────────────────────────────────────────────────────┐    │
│   │ windowed_aggregator.py                              │    │
│   │                                                     │    │
│   │   Window: 10:00:00 - 10:01:00                      │    │
│   │   ┌─────────────────────────────────────────┐      │    │
│   │   │ Trade 1: AAPL $175.00 x 100            │      │    │
│   │   │ Trade 2: AAPL $176.00 x 200            │      │    │
│   │   │ Trade 3: AAPL $174.00 x 150            │      │    │
│   │   └─────────────────────────────────────────┘      │    │
│   │                     │                               │    │
│   │                     ▼                               │    │
│   │   VWAP = (175×100 + 176×200 + 174×150) / 450      │    │
│   │        = $175.11                                   │    │
│   │                     │                               │    │
│   │                     ▼                               │    │
│   │   Returns: WindowFlushResult(                      │    │
│   │       aggregate=TradeAggregate(...),               │    │
│   │       partition_offsets={0: 1234}                  │    │
│   │   )                                                │    │
│   └─────────────────────────────────────────────────────┘    │
│                         │                                     │
│                         ▼                                     │
│   db_writer.write(aggregate)  ←─── to TimescaleDB            │
│   consumer.commit(offsets)    ←─── safe offset commit        │
└───────────────────────────────────────────────────────────────┘
```

**Key insight:** The `WindowFlushResult` contains BOTH the aggregate AND the Kafka offsets. This ensures we only commit offsets AFTER successful DB write (at-least-once semantics).

---

### Layer 4: Ingestion Service (Day 13-18)

**Goal:** Understand how external data sources connect.

**This layer is more complex. Here's the file dependency graph:**

```
                    ┌─────────────────────┐
                    │    manager.py       │ ← Orchestrator
                    │  (IngestionManager) │
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
            ▼                  ▼                  ▼
    ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
    │ connectors/   │  │ pipeline/     │  │ ports/        │
    │               │  │               │  │               │
    │ base.py       │  │ handlers.py   │  │ publisher_    │
    │ websocket.py  │  │ builder.py    │  │   port.py     │
    │ batch.py      │  │               │  │               │
    └───────┬───────┘  └───────┬───────┘  └───────────────┘
            │                  │
            │                  │
            ▼                  ▼
    ┌───────────────┐  ┌───────────────┐
    │ formats/      │  │ domain/       │
    │               │  │               │
    │ base.py       │  │ models.py     │
    │ (DataAdapter) │  │               │
    └───────────────┘  └───────────────┘
```

**Read order for this layer:**

| Order | File | Purpose | Time |
|-------|------|---------|------|
| 1 | `ports/ingestion_port.py` | Interface definition | 15 min |
| 2 | `connectors/base.py` | Template pattern | 30 min |
| 3 | `connectors/websocket.py` | Real implementation | 20 min |
| 4 | `pipeline/handlers.py` | Chain of responsibility | 45 min |
| 5 | `manager.py` | How it all connects | 30 min |

**The connector → adapter → pipeline → publisher flow:**

```python
# manager.py orchestrates this flow:

# 1. Connector fetches raw data
async for raw_event in connector.stream_events():
    #    │
    #    │  raw_event = {"type": "trade", "data": {"s": "AAPL", "p": 175.23, ...}}
    #    │
    #    ▼
    # 2. Adapter transforms to our model
    events = adapter.safe_transform(raw_event)
    #    │
    #    │  events = [EnrichedTradeEvent(symbol="STOCK_AAPL", price=175.23, ...)]
    #    │
    #    ▼
    # 3. Pipeline validates, enriches, deduplicates
    for event in events:
        processed = await pipeline.process(event)
        #    │
        #    │  Validation → Transformation → Enrichment → Deduplication
        #    │
        #    ▼
        # 4. Publisher sends to Kafka
        if processed:
            await publisher.publish(processed)
```

---

### Layer 5: Resilience Patterns (Day 19-21)

**Goal:** Understand fault tolerance.

**One file only:** `resilience/circuit_breaker.py`

```
Normal Operation (CLOSED)
         │
         │ failure_count >= 5
         ▼
    ┌─────────┐
    │  OPEN   │ ← All requests rejected
    └────┬────┘
         │
         │ 30 seconds pass
         ▼
   ┌───────────┐
   │ HALF_OPEN │ ← Testing recovery
   └─────┬─────┘
         │
    ┌────┴────┐
    │         │
success(3x) failure
    │         │
    ▼         ▼
 CLOSED     OPEN
```

**How it's used:**

```python
# connectors/base.py uses it:
if self._circuit_breaker:
    await self._circuit_breaker.call(self.connect)  # Protected call
else:
    await self.connect()  # Unprotected
```

---

### Complete File Dependency Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PRODUCER SIDE                                  │
│                                                                             │
│  config.py ──────▶ kafka_utils.py ──────▶ kafka_producer.py                │
│      │                   │                       │                          │
│      │                   │                       ▼                          │
│      │                   │               models.py (TradeEvent)             │
│      │                   │                       │                          │
│      │                   ▼                       ▼                          │
│      │            ┌──────────────────────────────────┐                     │
│      │            │           KAFKA                  │                     │
│      │            │         (trades topic)           │                     │
│      │            └──────────────────────────────────┘                     │
│      │                           │                                          │
└──────│───────────────────────────│──────────────────────────────────────────┘
       │                           │
       │                           │
┌──────│───────────────────────────│──────────────────────────────────────────┐
│      │                    CONSUMER SIDE                                     │
│      │                           │                                          │
│      │                           ▼                                          │
│      └──────▶ kafka_utils.py ──────▶ kafka_consumer.py                     │
│                                            │                                │
│                                            ▼                                │
│                               windowed_aggregator.py                        │
│                                            │                                │
│                                            ▼                                │
│                               models.py (TradeAggregate)                    │
│                                            │                                │
│                                            ▼                                │
│                                    TimescaleDB                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            INGESTION SERVICE                                │
│                          (Alternative to Producer)                          │
│                                                                             │
│  External APIs                                                              │
│       │                                                                     │
│       ▼                                                                     │
│  connectors/websocket.py ──▶ formats/base.py ──▶ pipeline/handlers.py     │
│       │                           │                      │                  │
│       │                           │                      │                  │
│       └───────────────────────────┴──────────────────────┘                  │
│                                   │                                         │
│                                   ▼                                         │
│                            manager.py                                       │
│                                   │                                         │
│                                   ▼                                         │
│                          ports/publisher_port.py ──────▶ KAFKA             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Quick Reference: Which Files Talk to Which

| When you're in... | You'll need to understand... |
|-------------------|------------------------------|
| `kafka_producer.py` | `models.py`, `kafka_utils.py`, `config.py` |
| `kafka_consumer.py` | `models.py`, `kafka_utils.py`, `windowed_aggregator.py` |
| `windowed_aggregator.py` | `models.py` only |
| `manager.py` | `connectors/*`, `pipeline/*`, `ports/*` |
| `handlers.py` | `domain/models.py`, `formats/base.py` |
| `websocket.py` | `connectors/base.py`, `resilience/circuit_breaker.py` |

---

### Daily Practice Routine

```
┌─────────────────────────────────────────────────────────────┐
│  15 min: Read ONE file from current layer                  │
│  10 min: Find all its imports (what does it depend on?)    │
│  10 min: Find who imports it (what depends on it?)         │
│  15 min: Add a print() statement, rebuild, verify          │
│   5 min: Write one sentence: "This file converts X to Y"   │
└─────────────────────────────────────────────────────────────┘
```

---

## Topic 2: Kafka Fundamentals

### Overview

Apache Kafka serves as the central nervous system of this platform - a distributed event streaming platform that decouples producers from consumers and provides durability, scalability, and fault tolerance.

### Core Concepts

| Concept | Definition | Code Reference |
|---------|------------|----------------|
| **Topic** | A named stream of records (e.g., `trades`) | `config.py:43` - `topic: str = "trades"` |
| **Partition** | A topic subdivision for parallelism | `kafka_utils.py` - `ensure_topics_exist(num_partitions=6)` |
| **Offset** | Sequential ID for each message in a partition | Consumer tracks in `kafka_consumer.py:89-95` |
| **Consumer Group** | Coordinated consumers sharing partition load | `config.py:52` - `consumer_group: str = "trade-aggregator"` |
| **Replication** | Data copies across brokers for fault tolerance | `config.py:58` - `replication_factor: int = 1` |

### KRaft Mode (No Zookeeper)

This repo uses **KRaft mode** - Kafka's native consensus protocol replacing Zookeeper:

```yaml
# docker-compose-full.yml:14-24
kafka:
  image: confluentinc/cp-kafka:7.5.0
  environment:
    KAFKA_NODE_ID: 1
    KAFKA_PROCESS_ROLES: broker,controller  # Combined mode
    KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:29093
    CLUSTER_ID: 'MkU3OEVBNTcwNTJENDM2Qk'
```

**Benefits of KRaft:**
- Simplified architecture (no separate Zookeeper cluster)
- Faster controller failover
- Better scalability for metadata operations

### Producer Configuration

```python
# kafka_utils.py:19-63
def create_kafka_producer(config: KafkaSettings) -> Producer:
    producer_config = {
        "bootstrap.servers": config.bootstrap_servers,
        "acks": "all",                    # Wait for ALL replicas
        "enable.idempotence": True,       # Prevent duplicates
        "retries": 2147483647,            # Infinite retries
        "max.in.flight.requests.per.connection": 5,  # Ordered delivery
        "compression.type": "lz4",        # Efficient compression
        "linger.ms": 5,                   # Batch small messages
        "batch.size": 16384,              # 16KB batches
    }
    return Producer(producer_config)
```

**Key Settings Explained:**

| Setting | Value | Purpose |
|---------|-------|---------|
| `acks=all` | All replicas acknowledge | Maximum durability |
| `enable.idempotence=true` | Exactly-once semantics | Prevents duplicate writes |
| `compression.type=lz4` | LZ4 compression | Fast compression, good ratio |
| `linger.ms=5` | 5ms wait | Batches messages for efficiency |

### Consumer Configuration

```python
# kafka_utils.py:66-111
def create_kafka_consumer(config: KafkaSettings) -> Consumer:
    consumer_config = {
        "bootstrap.servers": config.bootstrap_servers,
        "group.id": config.consumer_group,
        "auto.offset.reset": "earliest",  # Start from beginning
        "enable.auto.commit": False,      # Manual commits only
        "max.poll.interval.ms": 300000,   # 5 min processing time
        "session.timeout.ms": 45000,      # 45s heartbeat timeout
        "fetch.min.bytes": 1,             # Fetch immediately
        "fetch.max.wait.ms": 500,         # Max wait 500ms
    }
    return Consumer(consumer_config)
```

**Critical Setting:** `enable.auto.commit=False`

This enables **manual offset commits** - essential for at-least-once delivery:

```python
# kafka_consumer.py:263-280
def _safe_commit(self, offsets: list[TopicPartition]) -> None:
    """Commit offsets only AFTER successful processing."""
    try:
        self._consumer.commit(offsets=offsets, asynchronous=False)
        self._pending_commits.clear()
    except KafkaException as e:
        self._logger.error("Commit failed", error=str(e))
```

### Delivery Semantics

| Semantic | Description | This Repo |
|----------|-------------|-----------|
| At-most-once | May lose messages | No |
| At-least-once | May have duplicates | **Yes (base)** |
| Exactly-once | No loss, no duplicates | **Effectively yes** |

**How we achieve effectively exactly-once:**
1. Producer: `enable.idempotence=true` (no duplicate writes)
2. Consumer: Manual commits after processing
3. Consumer: Idempotent writes to TimescaleDB (UPSERT)

```python
# kafka_consumer.py:89-95
# Offset tracking per partition
self._partition_offsets: dict[int, int] = {}  # partition -> last_offset
self._pending_commits: dict[int, int] = {}    # partition -> offset_to_commit
```

---

## Topic 1: Architecture Deep-Dive

### System Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Data Sources  │────▶│  Apache Kafka   │────▶│    Consumer     │
│  (Connectors)   │     │  (Event Store)  │     │  (Aggregator)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                               │
        │                                               ▼
        │                                       ┌─────────────────┐
        │                                       │   TimescaleDB   │
        │                                       │   (Storage)     │
        └───────────────────────────────────────┴─────────────────┘
                                                        │
                                                        ▼
                                                ┌─────────────────┐
                                                │   FastAPI       │
                                                │   (REST API)    │
                                                └─────────────────┘
```

### Lambda vs Kappa Architecture

**This repo uses Kappa/Lakehouse architecture, NOT Lambda.**

| Aspect | Lambda | Kappa (This Repo) |
|--------|--------|-------------------|
| Data Paths | 2 (batch + stream) | 1 (stream only) |
| Complexity | High (dual systems) | Lower |
| Consistency | Eventual (merge views) | Single source of truth |
| Reprocessing | Batch layer rebuild | Replay from Kafka |

**Lambda Architecture (Educational Reference Only):**
```
Speed Layer:  Kafka → Real-time Processing → Serving (low latency)
Batch Layer:  HDFS → Batch Processing → Serving (accuracy)
              ↓
         Query merges both views
```

**Why Lakehouse/Kappa for This Use Case:**
- Single codebase to maintain
- Kafka retention enables reprocessing
- TimescaleDB handles both real-time and historical queries
- Simpler operational model

See: `LAMBDA_ARCHITECTURE.md` for detailed comparison.

### Medallion Architecture (Data Layers)

```
┌──────────────────────────────────────────────────────────────┐
│                    BRONZE (Raw Data)                         │
│  • Raw events from connectors                                │
│  • Schema: Original API format                               │
│  • Code: Connectors in adapters/connectors/                  │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    SILVER (Cleaned Data)                     │
│  • Validated, transformed, deduplicated                      │
│  • Schema: EnrichedTradeEvent                                │
│  • Code: Pipeline handlers in pipeline/handlers.py           │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    GOLD (Aggregated Data)                    │
│  • VWAP, volume aggregations                                 │
│  • Schema: AggregatedWindow                                  │
│  • Code: consumer/windowed_aggregator.py                     │
└──────────────────────────────────────────────────────────────┘
```

### Hexagonal Architecture (Ports & Adapters)

The ingestion service follows **Hexagonal Architecture**:

```
                    ┌─────────────────────────────────┐
                    │         Application Core        │
                    │   (Business Logic / Domain)     │
                    │                                 │
    ┌───────────────┤  IngestionManager              ├───────────────┐
    │               │  EnrichedTradeEvent            │               │
    │               │  Pipeline Handlers             │               │
    │               └─────────────────────────────────┘               │
    │                           │                                     │
    ▼                           │                                     ▼
┌─────────┐                     │                             ┌─────────────┐
│  PORTS  │◄────────────────────┴─────────────────────────────│   PORTS     │
│ (Input) │                                                   │  (Output)   │
└─────────┘                                                   └─────────────┘
    │                                                               │
    ▼                                                               ▼
┌─────────────┐                                           ┌─────────────────┐
│  ADAPTERS   │                                           │    ADAPTERS     │
│ (Connectors)│                                           │  (Publishers)   │
│ - WebSocket │                                           │  - Kafka        │
│ - REST      │                                           │  - Metrics      │
│ - Batch     │                                           │                 │
└─────────────┘                                           └─────────────────┘
```

**Port Interfaces** (`ports/__init__.py:13-95`):

```python
# Input Port - What connectors must implement
class IngestionPort(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def stream_events(self) -> AsyncIterator[dict[str, Any]]: ...

# Output Port - What publishers must implement
class EventPublisherPort(Protocol):
    async def publish(self, event: EnrichedTradeEvent) -> None: ...
    async def publish_batch(self, events: list[EnrichedTradeEvent]) -> None: ...

# Metrics Port - Observability contract
class MetricsPort(Protocol):
    def increment(self, name: str, value: int = 1, tags: dict | None = None) -> None: ...
    def gauge(self, name: str, value: float, tags: dict | None = None) -> None: ...
    def timing(self, name: str, value_ms: float, tags: dict | None = None) -> None: ...
```

**Benefits:**
- Testability: Mock ports for unit testing
- Flexibility: Swap adapters without changing core logic
- Clarity: Clear boundaries between concerns

---

## Topic 3: Ingestion Service

### Component Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         IngestionManager                                │
│                         (manager.py:27-358)                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌──────────┐ │
│  │ Connectors  │───▶│  Adapters   │───▶│  Pipeline   │───▶│Publisher │ │
│  │ (Sources)   │    │ (Transform) │    │ (Handlers)  │    │ (Kafka)  │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └──────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Connectors (Data Sources)

#### BaseConnector Template Method Pattern

```python
# base.py:20-180
class BaseConnector(ABC):
    """Template Method pattern - defines the algorithm skeleton."""

    async def stream_events(self) -> AsyncIterator[dict[str, Any]]:
        """Template method - fixed algorithm."""
        self._running = True
        try:
            async for event in self._fetch_events():  # Hook method
                if not self._running:
                    break
                yield event
        finally:
            self._running = False

    @abstractmethod
    async def _fetch_events(self) -> AsyncIterator[dict[str, Any]]:
        """Hook method - subclasses implement this."""
        ...
```

#### WebSocket Connector

```python
# websocket.py:19-231
class WebSocketConnector(BaseConnector):
    """Real-time WebSocket connections with auto-reconnect."""

    def __init__(
        self,
        name: str,
        url: str,
        subscriptions: list[dict[str, Any]] | None = None,
        heartbeat_interval: int = 30,
        reconnect_delay: int = 5,
        max_reconnect_attempts: int = 10,
        # ... circuit breaker, retry policy, metrics
    ):
        ...

    async def _fetch_events(self) -> AsyncIterator[dict[str, Any]]:
        """Connect, subscribe, and yield messages."""
        while self._running:
            try:
                async with websockets.connect(
                    self._url,
                    ping_interval=self._heartbeat_interval,
                ) as ws:
                    self._connection = ws
                    await self._send_subscriptions()

                    async for message in ws:
                        data = json.loads(message)
                        yield data

            except websockets.ConnectionClosed:
                await self._handle_reconnect()
```

#### Batch Connector

```python
# batch.py:20-369
class BatchConnector(BaseConnector):
    """File-based processing with checkpointing."""

    SUPPORTED_FORMATS = {".csv", ".json", ".parquet", ".pq"}

    def __init__(
        self,
        name: str,
        input_path: Path | str,
        file_pattern: str = "*.csv",
        poll_interval: int = 60,
        batch_size: int = 10000,
        archive_path: Path | str | None = None,
        checkpoint_file: Path | str | None = None,
        # ...
    ):
        ...

    async def _fetch_events(self) -> AsyncIterator[dict[str, Any]]:
        """Monitor directory and process new files."""
        while self._running:
            files = self._get_unprocessed_files()

            for file_path in files:
                async for batch in self._process_file(file_path):
                    yield batch  # Yields: {"_batch": [records], "_file": name, ...}

            await asyncio.sleep(self._poll_interval)
```

### Data Adapters (Format Transformation)

Adapters convert raw API formats to `EnrichedTradeEvent`:

```python
# base.py:12-94
class DataAdapter(ABC):
    """Transform external formats to internal model."""

    @abstractmethod
    def transform(self, raw_data: dict[str, Any]) -> list[EnrichedTradeEvent]:
        """Raw data → EnrichedTradeEvent list."""
        ...

    @abstractmethod
    def can_transform(self, raw_data: dict[str, Any]) -> bool:
        """Check if adapter handles this format."""
        ...

    def safe_transform(self, raw_data: dict[str, Any]) -> list[EnrichedTradeEvent]:
        """Transform with error handling - returns [] on failure."""
        try:
            if self.can_transform(raw_data):
                return self.transform(raw_data)
            return []
        except Exception:
            return []
```

**Integration in IngestionManager** (`manager.py:167-178`):

```python
# Transform using adapter
if source.adapter:
    events = source.adapter.safe_transform(event)
    if events:
        for enriched_event in events:
            await self._publish_event(enriched_event, source)
```

### Pipeline Handlers (Chain of Responsibility)

```python
# handlers.py:31-117
class Handler(ABC):
    """Base handler in Chain of Responsibility."""

    def __init__(self, name: str | None = None):
        self._next: Handler | None = None
        self._name = name or self.__class__.__name__

    def set_next(self, handler: "Handler") -> "Handler":
        """Link to next handler."""
        self._next = handler
        return handler  # Fluent API

    async def handle(self, event: dict | EnrichedTradeEvent) -> EnrichedTradeEvent | None:
        """Process and pass to next handler."""
        result = await self._process(event)

        if result is None:
            self._filtered_count += 1
            return None

        self._processed_count += 1

        if self._next:
            return await self._next.handle(result)

        return result
```

**Handler Types:**

| Handler | Purpose | Code Reference |
|---------|---------|----------------|
| `ValidationHandler` | Validates fields, timestamps | `handlers.py:119-202` |
| `TransformationHandler` | Raw dict → EnrichedTradeEvent | `handlers.py:307-343` |
| `EnrichmentHandler` | Adds metadata, computes keys | `handlers.py:271-305` |
| `DeduplicationHandler` | Filters duplicates by key | `handlers.py:204-269` |
| `FilterHandler` | Symbol/price filters | `handlers.py:345-390` |

**Pipeline Builder** (`builder.py:20-190`):

```python
# Fluent API for building handler chains
pipeline = (
    PipelineBuilder()
    .add_validation(strict=True)
    .add_transformation(adapter=FinnhubAdapter())
    .add_enrichment(source_metadata=metadata)
    .add_deduplication(cache_size=10000)
    .add_filter(symbols=["STOCK_AAPL"])
    .build()
)

# Result: Validation → Transformation → Enrichment → Deduplication → Filter
```

### Resilience Patterns

#### Circuit Breaker

```python
# circuit_breaker.py:44-259
class CircuitBreaker:
    """Prevents cascading failures."""

    # States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing)

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,      # Failures before opening
        recovery_timeout_seconds: int = 30,  # Wait before testing
        half_open_max_calls: int = 3,    # Successes to close
    ):
        ...

    async def call(self, func, *args, **kwargs):
        """Execute through circuit breaker."""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError(self.name, self._get_remaining_timeout())

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise
```

**State Machine:**

```
         failure_threshold reached
    ┌─────────────────────────────────┐
    │                                 ▼
┌───────┐                         ┌───────┐
│CLOSED │                         │ OPEN  │
└───────┘                         └───────┘
    ▲                                 │
    │    half_open_max_calls          │ recovery_timeout elapsed
    │    successes                    │
    │                                 ▼
    │                           ┌───────────┐
    └───────────────────────────│ HALF_OPEN │
              any failure       └───────────┘
              returns to OPEN ────────┘
```

---

## Topic 4: Consumer & Windowing

### TradeConsumer

```python
# kafka_consumer.py:42-627
class TradeConsumer:
    """Consumes trades with offset tracking and backpressure."""

    def __init__(
        self,
        config: KafkaSettings,
        aggregator: WindowedAggregator | None = None,
        dlq_handler: DeadLetterHandler | None = None,
    ):
        self._consumer = create_kafka_consumer(config)
        self._aggregator = aggregator
        self._partition_offsets: dict[int, int] = {}  # Track per partition
        self._pending_commits: dict[int, int] = {}
```

**Consumption Loop** (`kafka_consumer.py:150-220`):

```python
async def consume_loop(self) -> None:
    """Main consumption loop with safe commits."""
    while self._running:
        msg = self._consumer.poll(timeout=1.0)

        if msg is None:
            continue
        if msg.error():
            self._handle_error(msg.error())
            continue

        # Process message
        try:
            event = self._deserialize(msg.value())

            if self._aggregator:
                await self._aggregator.add_event(event)

            # Track offset for commit
            self._pending_commits[msg.partition()] = msg.offset() + 1

        except Exception as e:
            if self._dlq_handler:
                await self._dlq_handler.send(msg, e)

        # Periodic commit
        if should_commit():
            self._safe_commit()
```

**Safe Offset Commits** (`kafka_consumer.py:263-280`):

```python
def _safe_commit(self, offsets: list[TopicPartition] | None = None) -> None:
    """Commit only AFTER successful processing."""
    if offsets is None:
        offsets = [
            TopicPartition(self._topic, p, o)
            for p, o in self._pending_commits.items()
        ]

    try:
        self._consumer.commit(offsets=offsets, asynchronous=False)
        self._pending_commits.clear()
        self._logger.debug("Offsets committed", count=len(offsets))
    except KafkaException as e:
        self._logger.error("Commit failed", error=str(e))
        # Will retry on next cycle - at-least-once semantics
```

### WindowedAggregator

```python
# windowed_aggregator.py:143-525
class WindowedAggregator:
    """Tumbling window aggregation with VWAP calculation."""

    def __init__(
        self,
        window_duration_seconds: int = 60,  # 1-minute windows
        max_windows: int = 100,             # Memory guardrail
        late_event_threshold_seconds: int = 300,  # 5 min late tolerance
    ):
        self._window_duration = window_duration_seconds
        self._windows: dict[str, dict[int, WindowData]] = {}
        # Structure: {symbol: {window_start_timestamp: WindowData}}
```

**VWAP Calculation:**

```
VWAP = Σ(Price × Volume) / Σ(Volume)
```

```python
# windowed_aggregator.py:250-290
@dataclass
class WindowData:
    """Data accumulated within a window."""
    symbol: str
    window_start: datetime
    window_end: datetime

    # Aggregation fields
    total_volume: Decimal = Decimal("0")
    total_value: Decimal = Decimal("0")  # Σ(price * volume)
    trade_count: int = 0
    high_price: Decimal | None = None
    low_price: Decimal | None = None

    def add_trade(self, price: Decimal, volume: Decimal) -> None:
        """Add a trade to the window."""
        self.total_volume += volume
        self.total_value += price * volume
        self.trade_count += 1

        if self.high_price is None or price > self.high_price:
            self.high_price = price
        if self.low_price is None or price < self.low_price:
            self.low_price = price

    @property
    def vwap(self) -> Decimal | None:
        """Volume-Weighted Average Price."""
        if self.total_volume > 0:
            return self.total_value / self.total_volume
        return None
```

**Window Lifecycle:**

```
Event arrives (timestamp: 14:32:45)
            │
            ▼
    ┌───────────────────┐
    │ Calculate window  │  window_start = 14:32:00
    │ boundaries        │  window_end   = 14:33:00
    └───────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Window exists?    │──No──▶ Create new WindowData
    └───────────────────┘
            │ Yes
            ▼
    ┌───────────────────┐
    │ Add trade to      │
    │ window            │
    └───────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Check for closed  │  Any window where now > window_end?
    │ windows           │
    └───────────────────┘
            │ Yes
            ▼
    ┌───────────────────┐
    │ Emit aggregated   │  Returns AggregatedWindow
    │ result            │  with VWAP, high, low, count
    └───────────────────┘
```

**Memory Management** (`windowed_aggregator.py:380-410`):

```python
def _enforce_memory_limits(self) -> None:
    """Prevent unbounded memory growth."""
    for symbol, windows in self._windows.items():
        if len(windows) > self._max_windows:
            # Remove oldest windows
            sorted_keys = sorted(windows.keys())
            for key in sorted_keys[:-self._max_windows]:
                del windows[key]
                self._metrics.increment("windows_evicted", tags={"symbol": symbol})
```

**Late Event Handling:**

```python
# windowed_aggregator.py:320-350
def _is_late_event(self, event_time: datetime) -> bool:
    """Check if event is too late for its window."""
    window_end = self._get_window_end(event_time)
    now = datetime.now(UTC)

    # If window already closed and outside threshold
    if now > window_end:
        lateness = (now - window_end).total_seconds()
        if lateness > self._late_event_threshold:
            return True
    return False
```

---

## Topic 5: Docker & Deployment

### Four Ingestion Modes

```python
# config.py:15-28
class IngestionMode(str, Enum):
    """Operational modes for the ingestion service."""
    LOCAL = "local"       # Synthetic data only
    REALTIME = "realtime" # External APIs only
    BATCH = "batch"       # File processing only
    HYBRID = "hybrid"     # APIs + files
```

### Docker Compose Profiles

```yaml
# docker-compose-full.yml structure
services:
  kafka:           # Always runs
  timescaledb:     # Always runs
  producer:        # profiles: [local, hybrid]
  ingestion:       # profiles: [realtime, hybrid]
  batch-processor: # profiles: [batch, hybrid]
  consumer:        # Always runs
  api:             # Always runs
```

### Mode 1: LOCAL (Synthetic Data)

**Purpose:** Development and testing without external dependencies

```bash
docker-compose -f docker-compose-full.yml --profile local up -d
```

**Data Flow:**
```
┌──────────────┐     ┌─────────┐     ┌──────────┐     ┌───────────┐
│   Producer   │────▶│  Kafka  │────▶│ Consumer │────▶│TimescaleDB│
│ (Synthetic)  │     │         │     │          │     │           │
└──────────────┘     └─────────┘     └──────────┘     └───────────┘
```

**What runs:**
- `kafka` - Message broker
- `timescaledb` - Time-series database
- `producer` - Generates synthetic trade data
- `consumer` - Processes and aggregates
- `api` - REST endpoints

**Producer Configuration:**
```yaml
# docker-compose-full.yml:60-75
producer:
  profiles: ["local"]
  environment:
    SYMBOLS: "STOCK_AAPL,STOCK_GOOGL,CRYPTO_BTC,CRYPTO_ETH"
    EVENTS_PER_SECOND: 10
    BURST_ENABLED: true
    BURST_MULTIPLIER: 5
```

### Mode 2: REALTIME (External APIs)

**Purpose:** Live market data from Finnhub/Polygon WebSocket APIs

```bash
# Requires API keys
export FINNHUB_API_KEY=your_key
export POLYGON_API_KEY=your_key

docker-compose -f docker-compose-full.yml --profile realtime up -d
```

**Data Flow:**
```
┌─────────────┐     ┌───────────┐     ┌─────────┐     ┌──────────┐
│  Finnhub    │────▶│ Ingestion │────▶│  Kafka  │────▶│ Consumer │
│  Polygon    │     │  Service  │     │         │     │          │
│ (WebSocket) │     │           │     │         │     │          │
└─────────────┘     └───────────┘     └─────────┘     └──────────┘
```

**Ingestion Service Configuration:**
```yaml
# docker-compose-full.yml:80-100
ingestion:
  profiles: ["realtime", "hybrid"]
  environment:
    INGESTION_MODE: realtime
    FINNHUB_API_KEY: ${FINNHUB_API_KEY}
    POLYGON_API_KEY: ${POLYGON_API_KEY}
    FINNHUB_SYMBOLS: "AAPL,GOOGL,MSFT"
    POLYGON_SYMBOLS: "X:BTCUSD,X:ETHUSD"
```

### Mode 3: BATCH (File Processing)

**Purpose:** Historical data imports, daily/hourly batch files

```bash
docker-compose -f docker-compose-full.yml --profile batch up -d
```

**Data Flow:**
```
┌─────────────┐     ┌───────────┐     ┌─────────┐     ┌──────────┐
│   CSV/JSON  │────▶│   Batch   │────▶│  Kafka  │────▶│ Consumer │
│   Parquet   │     │ Processor │     │         │     │          │
│   Files     │     │           │     │         │     │          │
└─────────────┘     └───────────┘     └─────────┘     └──────────┘
```

**Batch Processor Configuration:**
```yaml
# docker-compose-full.yml:105-125
batch-processor:
  profiles: ["batch", "hybrid"]
  environment:
    INGESTION_MODE: batch
    BATCH_INPUT_PATH: /data/input
    BATCH_FILE_PATTERN: "*.csv"
    BATCH_POLL_INTERVAL: 60
    BATCH_SIZE: 10000
  volumes:
    - ./data/batch:/data/input
```

### Mode 4: HYBRID (APIs + Files)

**Purpose:** Production - combines real-time and batch processing

```bash
export FINNHUB_API_KEY=your_key
docker-compose -f docker-compose-full.yml --profile hybrid up -d
```

**Data Flow:**
```
┌─────────────┐
│  Finnhub    │────┐
│  (WebSocket)│    │     ┌───────────┐     ┌─────────┐     ┌──────────┐
└─────────────┘    ├────▶│ Ingestion │────▶│  Kafka  │────▶│ Consumer │
┌─────────────┐    │     │  Service  │     │         │     │          │
│ Batch Files │────┘     └───────────┘     └─────────┘     └──────────┘
└─────────────┘
```

### Service Dependencies

```yaml
# docker-compose-full.yml - depends_on with health checks
services:
  consumer:
    depends_on:
      kafka:
        condition: service_healthy
      timescaledb:
        condition: service_healthy

  kafka:
    healthcheck:
      test: ["CMD", "kafka-broker-api-versions", "--bootstrap-server", "localhost:9092"]
      interval: 10s
      timeout: 10s
      retries: 5
```

### Monitoring Stack

```yaml
# docker-compose-full.yml:130-180
prometheus:
  image: prom/prometheus
  ports: ["9090:9090"]
  volumes:
    - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

grafana:
  image: grafana/grafana
  ports: ["3000:3000"]
  volumes:
    - ./monitoring/dashboards:/var/lib/grafana/dashboards
```

---

## Topic 6: Kafka Message Size & Large Message Handling

### The Problem

Kafka has a default message size limit of **1MB** (`message.max.bytes`). When a serialized message exceeds this, the broker rejects the produce request entirely.

**Key files:**
- `src/common/kafka_utils.py` → `serialize_message()` with size validation
- `scripts/chaos/streaming/issues.py` → `OversizedMessageIssue` chaos test

### When Does This Happen in Production?

| Scenario | How It Happens | Typical Size |
|----------|---------------|--------------|
| Batch as single message | Developer serializes array of 10K events as one msg | 3-5MB |
| Order book snapshot | Full market depth (1000 levels x 2 sides) | 500KB-2MB |
| Embedded documents | Base64-encoded PDF/image in event payload | 5-50MB |
| Unbounded arrays | Historical price series, audit trails | Variable |
| Log aggregation | Full stack trace + request context | 100KB-1MB |

**This repo's messages are ~300 bytes each. The risk is NOT individual trades - it's accidentally batching them.**

### Where Validation Should Happen

```
Producer                    Kafka Broker              Consumer
─────────────────────────────────────────────────────────────
serialize_message()  ─────▶  message.max.bytes  ─────▶  deserialize
  ↓                           ↓
  MessageTooLargeError        Broker rejects
  (CAUGHT EARLY)              (CAUGHT LATE - harder to debug)
```

**Best practice:** Validate at the producer boundary (before Kafka sees it).

This repo validates in `serialize_message()`:

```python
# src/common/kafka_utils.py
def serialize_message(data: dict, max_bytes: int = 1_048_576) -> bytes:
    serialized = json.dumps(data, default=str).encode("utf-8")
    if len(serialized) > max_bytes:
        raise MessageTooLargeError(len(serialized), max_bytes)
    return serialized
```

### Industry Solutions (When Messages ARE Large)

**1. Claim Check Pattern** - Store large payload externally, send reference.
- Use case: Regulatory documents, market snapshots
- Trade-off: Adds external dependency (S3/blob storage), +50-200ms latency
- When: Message is inherently large and cannot be split

**2. Chunking** - Split into sequenced smaller messages.
- Use case: Large structured data that can be reassembled
- Trade-off: Reassembly complexity, ordering guarantees needed, timeout handling
- When: Data must stay in Kafka (replay, audit requirements)

**3. Schema Optimization** - Use Avro/Protobuf instead of JSON.
- JSON `TradeEvent`: ~300 bytes → Avro: ~150 bytes → Protobuf: ~100 bytes
- Trade-off: Schema registry dependency, learning curve
- When: High volume where every byte matters

**4. Compression** (already enabled in this repo)
- `"compression.type": "lz4"` in `kafka_utils.py`
- 40-60% reduction for JSON, transparent to application code

**5. Increase Broker Limits** (last resort)
- `message.max.bytes=5242880` on broker
- Increases memory pressure, replication lag, consumer processing time
- When: You've exhausted other options and messages are legitimately large

### Chaos Test

The `OversizedMessageIssue` tests three variants:

```python
# scripts/chaos/streaming/issues.py
class OversizedMessageIssue(StreamingIssue):
    # Variants:
    # "batch_array"  → 5000 trades as single message array (~1.5MB)
    # "large_payload" → Single trade with padded metadata field
    # "nested_depth"  → 500 levels of nested JSON
```

Run it:
```bash
python scripts/chaos/run_chaos_tests.py --streaming
```

### DLQ Handling for Oversized Messages

When `serialize_message()` raises `MessageTooLargeError`:
1. The producer catches the exception
2. The original data is logged (truncated) for debugging
3. The error is recorded in metrics
4. The message does NOT reach Kafka (rejected at producer boundary)

If validation is bypassed and Kafka rejects it:
1. The `_delivery_callback` (via `DeliveryCallbackMixin`) fires with error
2. `_delivery_errors` counter increments
3. The message is lost unless the producer has retry/DLQ logic

---

## Experimentation Plan

### Prerequisites

1. **Docker & Docker Compose** installed
2. **API Keys** (for REALTIME/HYBRID modes):
   - Finnhub: https://finnhub.io/ (free tier available)
   - Polygon: https://polygon.io/ (free tier available)

### Experiment 1: LOCAL Mode

**Goal:** Understand basic data flow with synthetic data

```bash
# Start
cd JanAndFeb
docker-compose -f docker-compose-full.yml --profile local up -d

# Verify services
docker-compose -f docker-compose-full.yml ps

# Watch logs
docker-compose -f docker-compose-full.yml logs -f producer
docker-compose -f docker-compose-full.yml logs -f consumer

# Check Kafka topics
docker exec -it kafka kafka-topics --bootstrap-server localhost:9092 --list
docker exec -it kafka kafka-console-consumer --bootstrap-server localhost:9092 \
    --topic trades --from-beginning --max-messages 5

# Query API
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/trades/recent?limit=10

# Cleanup
docker-compose -f docker-compose-full.yml --profile local down
```

### Experiment 2: REALTIME Mode

**Goal:** Connect to live market data APIs

```bash
# Set API keys
export FINNHUB_API_KEY=your_finnhub_key
export POLYGON_API_KEY=your_polygon_key  # Optional

# Start
docker-compose -f docker-compose-full.yml --profile realtime up -d

# Watch ingestion logs for WebSocket connections
docker-compose -f docker-compose-full.yml logs -f ingestion

# Expected logs:
# "WebSocket connected to wss://ws.finnhub.io"
# "Subscribed to AAPL"
# "Event received: {type: trade, ...}"

# Monitor circuit breaker state
curl http://localhost:8000/api/v1/health/detailed

# Cleanup
docker-compose -f docker-compose-full.yml --profile realtime down
```

### Experiment 3: BATCH Mode

**Goal:** Process historical data files

```bash
# Create test data directory
mkdir -p data/batch

# Create sample CSV
cat > data/batch/trades_2024.csv << 'EOF'
symbol,price,volume,timestamp
AAPL,175.50,1000,2024-01-15T10:30:00Z
GOOGL,140.25,500,2024-01-15T10:30:01Z
MSFT,380.00,750,2024-01-15T10:30:02Z
EOF

# Start batch processor
docker-compose -f docker-compose-full.yml --profile batch up -d

# Watch batch processing
docker-compose -f docker-compose-full.yml logs -f batch-processor

# Expected logs:
# "Found unprocessed files: 1"
# "Processing file: trades_2024.csv"
# "File processed: trades_2024.csv, rows: 3"

# Check checkpoint (processed files list)
cat data/batch/.checkpoint

# Cleanup
docker-compose -f docker-compose-full.yml --profile batch down
```

### Experiment 4: HYBRID Mode

**Goal:** Combine real-time and batch processing

```bash
export FINNHUB_API_KEY=your_key

# Start all services
docker-compose -f docker-compose-full.yml --profile hybrid up -d

# Monitor both data paths
docker-compose -f docker-compose-full.yml logs -f ingestion batch-processor

# Add batch file while real-time is running
cp historical_data.csv data/batch/

# Verify both sources in consumer
docker-compose -f docker-compose-full.yml logs -f consumer | grep "source"

# Expected: Events from both "finnhub" and "batch" sources

# Cleanup
docker-compose -f docker-compose-full.yml --profile hybrid down -v
```

### Verification Checklist

| Check | Command | Expected |
|-------|---------|----------|
| Kafka running | `docker exec kafka kafka-topics --list` | Topics listed |
| Producer active | `docker logs producer \| tail` | "Published event" messages |
| Consumer processing | `docker logs consumer \| tail` | "Aggregated window" messages |
| TimescaleDB storing | `docker exec timescaledb psql -c "SELECT count(*) FROM trades"` | Row count > 0 |
| API responding | `curl localhost:8000/health` | `{"status": "healthy"}` |

---

## Quick Reference

### Key Files

| Component | File | Lines |
|-----------|------|-------|
| Kafka Config | `config.py` | 85-120 |
| Producer | `kafka_producer.py` | 1-150 |
| Consumer | `kafka_consumer.py` | 38-528 |
| Aggregator | `windowed_aggregator.py` | 150-473 |
| Manager | `manager.py` | 27-358 |
| Connectors | `adapters/connectors/` | - |
| Handlers | `pipeline/handlers.py` | 31-390 |
| Circuit Breaker | `resilience/circuit_breaker.py` | 44-259 |
| Docker | `docker-compose-full.yml` | 1-200 |

### Design Patterns Used

| Pattern | Implementation | Purpose |
|---------|----------------|---------|
| Hexagonal Architecture | Ports & Adapters | Testability, flexibility |
| Chain of Responsibility | Pipeline handlers | Processing stages |
| Template Method | BaseConnector | Connector lifecycle |
| Circuit Breaker | CircuitBreaker class | Fault tolerance |
| Builder | PipelineBuilder | Fluent configuration |

### Delivery Guarantees

| Stage | Guarantee | Mechanism |
|-------|-----------|-----------|
| Producer → Kafka | No duplicates | `enable.idempotence=true` |
| Kafka → Consumer | At-least-once | Manual offset commits |
| Consumer → DB | Idempotent | UPSERT operations |
| **End-to-End** | **Effectively exactly-once** | Combined mechanisms |
