# Architecture Diagrams (Verified)

> **View these diagrams:** Install VS Code extension "Markdown Preview Mermaid Support", then press `Ctrl+Shift+V` to preview.
>
> Or paste into: https://mermaid.live/

---

## File-to-Diagram Mapping

| File | Location | Contains | Diagrams |
|------|----------|----------|----------|
| `models.py` (common) | `src/common/models.py` | `TradeSide`, `SourceType`, `TradeEvent`, `TradeAggregate` | #10, #6 |
| `models.py` (domain) | `src/ingestion/domain/models.py` | `RawEvent`, `EnrichedTradeEvent`, `SourceMetadata` | #10, #2 |
| `manager.py` | `src/ingestion/manager.py` | #3, #2 |
| `base.py` (connector) | `src/ingestion/adapters/connectors/base.py` | #3, #9 |
| `websocket.py` | `src/ingestion/adapters/connectors/websocket.py` | #3 |
| `batch.py` | `src/ingestion/adapters/connectors/batch.py` | #3 |
| `base.py` (adapter) | `src/ingestion/adapters/formats/base.py` | #3, #2 |
| `handlers.py` | `src/ingestion/pipeline/handlers.py` | #4 |
| `builder.py` | `src/ingestion/pipeline/builder.py` | #4 |
| `circuit_breaker.py` | `src/ingestion/resilience/circuit_breaker.py` | #5 |
| `ingestion_port.py` | `src/ingestion/ports/ingestion_port.py` | #9 |
| `publisher_port.py` | `src/ingestion/ports/publisher_port.py` | #9 |
| `metrics_port.py` | `src/ingestion/ports/metrics_port.py` | #9 |
| `windowed_aggregator.py` | `src/consumer/windowed_aggregator.py` | #6 |
| `kafka_consumer.py` | `src/consumer/kafka_consumer.py` | #6, #7 |
| `kafka_utils.py` | `src/common/kafka_utils.py` | `DeliveryCallbackMixin` | #7, #11 |
| `kafka_producer.py` | `src/producer/kafka_producer.py` | #7 |
| `docker-compose-full.yml` | `docker-compose-full.yml` | #1, #8 |
| `config.py` | `src/config.py` | #8 |

---

## 1. System Overview (C4 Context Level)

**Files:** `docker-compose-full.yml`

```mermaid
flowchart TB
    subgraph External["External Data Sources"]
        FH[Finnhub API]
        PG[Polygon API]
        FILES[CSV/JSON/Parquet Files]
    end

    subgraph Platform["Energy Trading Platform"]
        ING[Ingestion Service]
        KAFKA[(Apache Kafka<br/>KRaft Mode)]
        CONS[Consumer Service]
        DB[(TimescaleDB)]
        API[REST API]
    end

    subgraph Clients["Clients"]
        DASH[Dashboard]
        ANALYST[Analysts]
    end

    FH -->|WebSocket| ING
    PG -->|WebSocket| ING
    FILES -->|File Watch| ING
    ING -->|Publish| KAFKA
    KAFKA -->|Subscribe| CONS
    CONS -->|Upsert| DB
    DB --> API
    API --> DASH
    API --> ANALYST
```

---

## 2. Data Flow (Sequence)

**Files:** `manager.py`, `base.py`, `handlers.py`, `models.py`

```mermaid
sequenceDiagram
    participant Source as Data Source
    participant Conn as BaseConnector
    participant Adapter as DataAdapter
    participant Pipeline as Pipeline<br/>(handlers.py)
    participant Pub as EventPublisherPort
    participant Kafka as Kafka

    Source->>Conn: Raw dict
    Conn->>Adapter: safe_transform(raw_data)
    Adapter->>Adapter: transform() → list[EnrichedTradeEvent]
    Adapter->>Pipeline: EnrichedTradeEvent

    Note over Pipeline: ValidationHandler<br/>→ TransformationHandler<br/>→ EnrichmentHandler<br/>→ DeduplicationHandler

    Pipeline->>Pub: publish(EnrichedTradeEvent)
    Pub->>Kafka: produce(topic, key, value)
```

---

## 3. Ingestion Service Components

**Files:** `manager.py:27-376`, `base.py:22-261`, `websocket.py`, `batch.py`, `base.py` (formats)

```mermaid
classDiagram
    class IngestionManager {
        -_publisher: EventPublisherPort
        -_metrics: MetricsPort | None
        -_dlq_publisher: EventPublisherPort | None
        -_connectors: list~tuple~
        -_tasks: list~Task~
        -_running: bool
        -_shutdown_event: Event
        -_total_events: int
        -_total_errors: int
        -_start_time: datetime | None
        +add_connector(connector, adapter, pipeline)
        +add_connector_from_config(type, config, adapter_name)
        +start()
        +stop()
        +wait_for_shutdown()
        +get_status() dict
        +get_connector(name) IngestionPort | None
        -_run_connector(connector, pipeline, adapter)
        -_send_to_dlq(raw_event, error, source)
    }

    class BaseConnector {
        <<abstract>>
        #_name: str
        #_source_type: SourceType
        #_expected_latency_ms: int
        #_circuit_breaker: CircuitBreaker | None
        #_retry_policy: RetryPolicy
        #_metrics: MetricsPort | None
        #_connected: bool
        #_running: bool
        #_event_count: int
        #_error_count: int
        #_last_event_time: datetime | None
        +name: str
        +source_type: str
        +is_connected: bool
        +connect()*
        +disconnect()*
        +run() AsyncIterator
        +stream_events() AsyncIterator
        +health_check() bool
        +stop()
        +create_source_metadata() SourceMetadata
        +get_stats() dict
        #_fetch_events()* AsyncIterator
        #_pre_connect()
        #_post_connect()
        #_on_error(error)
        #_pre_disconnect()
        #_on_event(event)
    }

    class WebSocketConnector {
        -_url: str
        -_subscriptions: list
        -_heartbeat_interval: int
        -_reconnect_delay: int
        -_max_reconnect_attempts: int
        -_connection: WebSocketClientProtocol | None
        +connect()
        +disconnect()
        #_fetch_events() AsyncIterator
        -_send_subscriptions()
        -_handle_reconnect()
    }

    class BatchConnector {
        +SUPPORTED_FORMATS: set
        -_input_path: Path
        -_file_pattern: str
        -_poll_interval: int
        -_batch_size: int
        -_archive_path: Path | None
        -_delete_after_processing: bool
        -_checkpoint_file: Path | None
        -_processed_files: set~str~
        +connect()
        +disconnect()
        +process_single_file(path) AsyncIterator
        #_fetch_events() AsyncIterator
        -_load_checkpoint()
        -_save_checkpoint()
        -_get_unprocessed_files() list~Path~
        -_read_file(path) DataFrame
        -_archive_file(path)
        -_delete_file(path)
        -_process_file(path) AsyncIterator
    }

    class DataAdapter {
        <<abstract>>
        +source_name: str
        +source_type: SourceType
        +expected_latency_ms: int
        +transform(raw_data)* list~EnrichedTradeEvent~
        +can_transform(raw_data)* bool
        +create_source_metadata(batch_id) SourceMetadata
        +safe_transform(raw_data) list~EnrichedTradeEvent~
    }

    IngestionManager --> BaseConnector : manages
    IngestionManager --> DataAdapter : uses
    IngestionManager --> EventPublisherPort : publishes to

    BaseConnector <|-- WebSocketConnector
    BaseConnector <|-- BatchConnector
    BaseConnector ..|> IngestionPort : implements
```

---

## 4. Pipeline Handlers (Chain of Responsibility)

**Files:** `handlers.py:31-390`, `builder.py:20-260`

```mermaid
flowchart LR
    subgraph Pipeline["Handler Chain (builder.py)"]
        direction LR
        V[ValidationHandler]
        T[TransformationHandler]
        E[EnrichmentHandler]
        D[DeduplicationHandler]
        F[FilterHandler]
    end

    RAW[/"dict | EnrichedTradeEvent"/] --> V
    V -->|valid| T
    V -->|invalid strict| DROP1((filtered))
    T -->|has adapter| E
    T -->|no adapter| DROP2((filtered))
    E --> D
    D -->|unique key| F
    D -->|duplicate| DROP3((filtered))
    F -->|passes filters| OUT[/"EnrichedTradeEvent"/]
    F -->|filtered| DROP4((filtered))
```

```mermaid
classDiagram
    class Handler {
        <<abstract>>
        #_next: Handler | None
        #_name: str
        #_processed_count: int
        #_filtered_count: int
        #_error_count: int
        +name: str
        +set_next(handler) Handler
        +handle(event) EnrichedTradeEvent | None
        +get_stats() dict
        #_process(event)* EnrichedTradeEvent | None
    }

    class ValidationHandler {
        -_strict: bool
        -_max_future_seconds: int
        -_max_past_days: int
        #_process(event)
        -_validate_enriched_event(event)
        -_validate_raw_event(event)
    }

    class TransformationHandler {
        -_adapter: DataAdapter | None
        #_process(event)
        +set_adapter(adapter)
    }

    class DeduplicationHandler {
        -_cache: dict~str, float~
        -_cache_size: int
        -_ttl_seconds: int
        -_duplicate_count: int
        #_process(event)
        -_cleanup_expired(now)
        +get_stats() dict
    }

    class EnrichmentHandler {
        -_source_metadata: SourceMetadata | None
        #_process(event)
        +set_source_metadata(metadata)
    }

    class FilterHandler {
        -_filter_func: Callable | None
        -_symbols: set~str~ | None
        -_min_price: float | None
        -_max_price: float | None
        #_process(event)
    }

    class PipelineBuilder {
        -_handlers: list~Handler~
        +add_handler(handler) PipelineBuilder
        +add_validation(...) PipelineBuilder
        +add_deduplication(...) PipelineBuilder
        +add_enrichment(...) PipelineBuilder
        +add_transformation(...) PipelineBuilder
        +add_filter(...) PipelineBuilder
        +build() Handler
        +build_default(adapter) Handler
    }

    class Pipeline {
        -_head: Handler
        -_processed_count: int
        -_error_count: int
        +process(event) EnrichedTradeEvent | None
        +process_batch(events) list~EnrichedTradeEvent~
        +get_stats() dict
    }

    Handler <|-- ValidationHandler
    Handler <|-- TransformationHandler
    Handler <|-- DeduplicationHandler
    Handler <|-- EnrichmentHandler
    Handler <|-- FilterHandler

    Handler --> Handler : _next

    PipelineBuilder ..> Handler : creates
    Pipeline --> Handler : _head
```

---

## 5. Circuit Breaker State Machine

**Files:** `circuit_breaker.py:44-259`

```mermaid
stateDiagram-v2
    [*] --> CLOSED

    CLOSED --> CLOSED : success → reset failure_count
    CLOSED --> OPEN : failure_count >= failure_threshold

    OPEN --> OPEN : request → raise CircuitOpenError
    OPEN --> HALF_OPEN : recovery_timeout elapsed

    HALF_OPEN --> CLOSED : success_count >= half_open_max_calls
    HALF_OPEN --> OPEN : any failure
```

```mermaid
classDiagram
    class CircuitState {
        <<enumeration>>
        CLOSED = "closed"
        OPEN = "open"
        HALF_OPEN = "half_open"
    }

    class CircuitOpenError {
        +name: str
        +remaining_seconds: float
    }

    class CircuitBreaker {
        +name: str
        +failure_threshold: int
        +recovery_timeout: int
        +half_open_max_calls: int
        +excluded_exceptions: tuple
        -_state: CircuitState
        -_failure_count: int
        -_success_count: int
        -_last_failure_time: datetime | None
        -_lock: asyncio.Lock
        +state: CircuitState
        +failure_count: int
        +call(func, *args, **kwargs) T
        +reset()
        +get_stats() dict
        -_should_attempt_reset() bool
        -_get_remaining_timeout() float
        -_on_success()
        -_on_failure(error)
        -_open_circuit()
        -_close_circuit()
    }

    CircuitBreaker --> CircuitState
    CircuitBreaker ..> CircuitOpenError : raises
```

---

## 6. Consumer Windowed Aggregation

**Files:** `windowed_aggregator.py:23-473`, `kafka_consumer.py`, `common/models.py:51-126, 128-206`

```mermaid
flowchart TB
    subgraph Consumer["TradeConsumer (kafka_consumer.py)"]
        POLL[poll Kafka]
        DESER[deserialize → TradeEvent]
        AGG[WindowedAggregator]
        COMMIT[safe_commit offsets]
    end

    subgraph Aggregator["WindowedAggregator"]
        CALC[_get_window_start]
        ADD[WindowState.add_trade]
        CHECK[_flush_completed_windows]
        EMIT[WindowFlushResult]
    end

    POLL --> DESER
    DESER --> AGG
    AGG --> CALC
    CALC --> ADD
    ADD --> CHECK
    CHECK -->|window closed| EMIT
    EMIT --> COMMIT
    CHECK -->|window open| POLL
```

```mermaid
classDiagram
    class OffsetWatermark {
        +partition: int
        +min_offset: int
        +max_offset: int
        +update(partition, offset)
    }

    class WindowFlushResult {
        +aggregate: TradeAggregate
        +partition_offsets: dict~int, int~
    }

    class WindowState {
        +total_value: Decimal
        +total_volume: Decimal
        +trade_count: int
        +max_price: Decimal | None
        +min_price: Decimal | None
        -_offsets: dict~int, OffsetWatermark~
        -_created_at: datetime
        +add_trade(trade, partition, offset)
        +get_max_offset(partition) int
        +get_all_max_offsets() dict
        +compute_vwap() Decimal
        +is_empty() bool
        +get_memory_size_estimate() int
    }

    class WindowedAggregator {
        +window_duration: timedelta
        +late_grace_period: timedelta
        +max_windows: int
        +max_memory_bytes: int
        -_windows: dict~tuple, WindowState~
        -_latest_event_time: datetime | None
        -_evicted_window_count: int
        -_partition_offsets: dict~int, int~
        +add_trade(trade, partition, offset) list~WindowFlushResult~
        +flush_all() list~WindowFlushResult~
        +get_active_window_count() int
        +get_partition_offsets() dict
        +get_estimated_memory_usage() int
        +get_state_summary() dict
        -_get_window_start(event_time) datetime
        -_get_window_end(window_start) datetime
        -_flush_completed_windows() list~WindowFlushResult~
        -_evict_oldest_windows() list~WindowFlushResult~
    }

    class TradeEvent {
        +trade_id: UUID
        +symbol: str
        +price: Decimal
        +volume: Decimal
        +side: TradeSide
        +trader_id: str
        +event_timestamp: datetime
        +to_kafka_key() bytes
        +to_kafka_value() dict
        +from_kafka_value(data)$ TradeEvent
    }

    class TradeAggregate {
        +symbol: str
        +window_start: datetime
        +window_end: datetime
        +vwap: Decimal
        +total_volume: Decimal
        +trade_count: int
        +max_price: Decimal
        +min_price: Decimal
        +total_value: Decimal
        +lmp: Decimal | None
        +lmp_energy: Decimal | None
        +lmp_congestion: Decimal | None
        +lmp_loss: Decimal | None
        +to_db_tuple() tuple
    }

    WindowedAggregator --> WindowState : manages
    WindowState --> OffsetWatermark : tracks offsets
    WindowedAggregator ..> WindowFlushResult : produces
    WindowFlushResult --> TradeAggregate
    WindowState ..> TradeEvent : receives
```

**VWAP Calculation:**
```
VWAP = Σ(Price × Volume) / Σ(Volume)

Example (1-minute window):
  Trade 1: AAPL $175.00 × 100 shares = $17,500
  Trade 2: AAPL $176.00 × 200 shares = $35,200
  Trade 3: AAPL $174.00 × 150 shares = $26,100

  Total Value  = $78,800
  Total Volume = 450 shares
  VWAP = $78,800 / 450 = $175.11
```

---

## 7. Kafka Topic Partitioning

**Files:** `kafka_utils.py:19-111`, `kafka_producer.py`, `config.py:85-120`

```mermaid
flowchart TB
    subgraph Producers
        P1[Producer 1<br/>acks=all<br/>idempotence=true]
        P2[Producer 2]
    end

    subgraph Topic["market-trades (3 partitions)"]
        PA0[Partition 0<br/>AAPL, MSFT]
        PA1[Partition 1<br/>GOOGL, AMZN]
        PA2[Partition 2<br/>BTC, ETH]
    end

    subgraph ConsumerGroup["Consumer Group: trade-processor"]
        C1[Consumer 1<br/>auto.commit=false]
        C2[Consumer 2<br/>manual offset commits]
    end

    P1 -->|key=symbol| PA0
    P1 -->|key=symbol| PA1
    P2 -->|key=symbol| PA2

    PA0 --> C1
    PA1 --> C2
    PA2 --> C2
```

**Producer Config** (`kafka_utils.py:19-63`):
```python
{
    "acks": "all",                    # All replicas acknowledge
    "enable.idempotence": True,       # Exactly-once producer
    "compression.type": "lz4",        # Fast compression
    "linger.ms": 5,                   # Batch small messages
}
```

**Consumer Config** (`kafka_utils.py:66-111`):
```python
{
    "enable.auto.commit": False,      # Manual commits only
    "auto.offset.reset": "earliest",  # Start from beginning
    "max.poll.interval.ms": 300000,   # 5 min processing time
}
```

---

## 8. Deployment Modes

**Files:** `docker-compose-full.yml`, `config.py:15-28`

```mermaid
flowchart TB
    subgraph LOCAL["LOCAL Mode (--profile local)"]
        L_PROD[producer<br/>Synthetic Data] --> L_KAFKA[Kafka]
        L_KAFKA --> L_CONS[consumer]
        L_CONS --> L_DB[(TimescaleDB)]
    end

    subgraph REALTIME["REALTIME Mode (--profile realtime)"]
        R_API[Finnhub/Polygon<br/>WebSocket] --> R_ING[ingestion]
        R_ING --> R_KAFKA[Kafka]
        R_KAFKA --> R_CONS[consumer]
        R_CONS --> R_DB[(TimescaleDB)]
    end

    subgraph BATCH["BATCH Mode (--profile batch)"]
        B_FILE[CSV/Parquet<br/>Files] --> B_BATCH[batch-processor]
        B_BATCH --> B_KAFKA[Kafka]
        B_KAFKA --> B_CONS[consumer]
        B_CONS --> B_DB[(TimescaleDB)]
    end

    subgraph HYBRID["HYBRID Mode (--profile hybrid)"]
        H_API[External APIs] --> H_ING[ingestion]
        H_FILE[Files] --> H_ING
        H_ING --> H_KAFKA[Kafka]
        H_KAFKA --> H_CONS[consumer]
        H_CONS --> H_DB[(TimescaleDB)]
    end
```

**IngestionMode Enum** (`config.py:15-28`):
```python
class IngestionMode(str, Enum):
    LOCAL = "local"       # Synthetic data only
    REALTIME = "realtime" # External APIs only
    BATCH = "batch"       # File processing only
    HYBRID = "hybrid"     # APIs + files
```

---

## 9. Hexagonal Architecture (Ports & Adapters)

**Files:** `ports/ingestion_port.py`, `ports/publisher_port.py`, `ports/metrics_port.py`, `base.py`

```mermaid
flowchart TB
    subgraph Adapters_In["Input Adapters (Connectors)"]
        WS[WebSocketConnector]
        BATCH[BatchConnector]
    end

    subgraph Ports_In["Input Ports"]
        IP[IngestionPort]
        BIP[BatchIngestionPort]
    end

    subgraph Core["Application Core"]
        MGR[IngestionManager]
        PIPE[Pipeline]
        DOM[Domain Models]
    end

    subgraph Ports_Out["Output Ports"]
        EP[EventPublisherPort]
        MP[MetricsPort]
    end

    subgraph Adapters_Out["Output Adapters"]
        KP[KafkaPublisher]
        PROM[PrometheusMetrics]
    end

    WS --> IP
    BATCH --> BIP
    BIP --> IP
    IP --> MGR
    MGR --> PIPE
    PIPE --> DOM
    MGR --> EP
    MGR --> MP
    EP --> KP
    MP --> PROM

    style Core fill:#e1f5fe
    style Ports_In fill:#fff3e0
    style Ports_Out fill:#fff3e0
    style Adapters_In fill:#f3e5f5
    style Adapters_Out fill:#f3e5f5
```

```mermaid
classDiagram
    class IngestionPort {
        <<interface>>
        +name: str
        +source_type: str
        +is_connected: bool
        +connect()*
        +disconnect()*
        +stream_events()* AsyncIterator
        +health_check()* bool
    }

    class BatchIngestionPort {
        <<interface>>
        +fetch_batch()* list~dict~
        +get_batch_id()* str
    }

    class EventPublisherPort {
        <<interface>>
        +publish(event)*
        +publish_batch(events)*
        +flush()*
        +health_check()* bool
    }

    class MetricsPort {
        <<interface>>
        +record_event_ingested(...)
        +record_event_published(...)
        +record_error(...)
        +set_connector_status(...)
    }

    class PublishError {
        +message: str
        +event: EnrichedTradeEvent | None
    }

    BatchIngestionPort --|> IngestionPort
    EventPublisherPort ..> PublishError : raises
```

---

## 10. Domain Models

**Files:**
- `src/common/models.py` - Shared enums (`SourceType`, `TradeSide`) and core models (`TradeEvent`, `TradeAggregate`)
- `src/ingestion/domain/models.py` - Ingestion-specific models (`RawEvent`, `EnrichedTradeEvent`, `SourceMetadata`)

> **Note:** `SourceType` and `TradeSide` are defined ONLY in `common/models.py` and imported elsewhere (DRY principle).

```mermaid
classDiagram
    class SourceType {
        <<enumeration>>
        %%Defined in: common/models.py
        WEBSOCKET = "websocket"
        SSE = "sse"
        POLLING = "polling"
        WEBHOOK = "webhook"
        MICRO_BATCH = "micro_batch"
        BATCH = "batch"
        SYNTHETIC = "synthetic"
    }

    class TradeSide {
        <<enumeration>>
        %%Defined in: common/models.py
        BUY = "BUY"
        SELL = "SELL"
    }

    class SourceMetadata {
        +source_type: SourceType
        +source_name: str
        +ingestion_timestamp: datetime
        +expected_latency_ms: int
        +batch_id: str | None
        +retry_count: int
        +to_dict() dict
        +from_dict(data)$ SourceMetadata
    }

    class RawEvent {
        +raw_id: UUID
        +source_metadata: SourceMetadata
        +received_at: datetime
        +raw_data: dict~str, Any~
        +to_kafka_value() dict
    }

    class TradeEvent {
        +trade_id: UUID
        +symbol: str
        +price: Decimal
        +volume: Decimal
        +side: TradeSide
        +trader_id: str
        +event_timestamp: datetime
        +to_kafka_key() bytes
        +to_kafka_value() dict
        +from_kafka_value(data)$ TradeEvent
    }

    class EnrichedTradeEvent {
        +trade_id: UUID
        +symbol: str
        +price: Decimal
        +volume: Decimal
        +side: TradeSide
        +trader_id: str
        +event_timestamp: datetime
        +source_metadata: SourceMetadata | None
        +processing_timestamp: datetime
        +idempotency_key: str | None
        +to_kafka_key() bytes
        +to_kafka_value() dict
        +from_kafka_value(data)$ EnrichedTradeEvent
        +compute_idempotency_key() str
        +calculate_latency_ms() float | None
    }

    class TradeAggregate {
        +symbol: str
        +window_start: datetime
        +window_end: datetime
        +vwap: Decimal
        +total_volume: Decimal
        +trade_count: int
        +max_price: Decimal
        +min_price: Decimal
        +total_value: Decimal
        +lmp: Decimal | None
        +lmp_energy: Decimal | None
        +lmp_congestion: Decimal | None
        +lmp_loss: Decimal | None
        +to_db_tuple() tuple
    }

    class DLQMessage {
        +original_message: str
        +error_type: str
        +error_message: str
        +failed_at: datetime
        +consumer_group: str
        +partition: int
        +offset: int
        +to_kafka_value() dict
    }

    SourceMetadata --> SourceType
    RawEvent --> SourceMetadata
    TradeEvent --> TradeSide
    EnrichedTradeEvent --> TradeSide
    EnrichedTradeEvent --> SourceMetadata

    RawEvent ..> EnrichedTradeEvent : "Bronze → Silver"
    TradeEvent ..> TradeAggregate : "aggregated to (Gold)"
```

---

## Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MEDALLION ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   BRONZE    │───▶│   SILVER    │───▶│    GOLD     │───▶│   SERVING   │  │
│  │  (Raw)      │    │  (Clean)    │    │ (Aggregate) │    │   (Query)   │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                             │
│  RawEvent           EnrichedTradeEvent  TradeAggregate    REST API         │
│  • raw_data         • validated         • vwap            • /trades        │
│  • source_metadata  • deduplicated      • total_volume    • /aggregates    │
│                     • enriched          • trade_count     • /symbols       │
│                                                                             │
│  Files:             Files:              Files:            Files:           │
│  connectors/        handlers.py         windowed_         api/             │
│  base.py            builder.py          aggregator.py                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. DeliveryCallbackMixin (Template Method Pattern)

**File:** `src/common/kafka_utils.py`

> **Pattern:** Template Method - defines the skeleton of the delivery callback algorithm, allowing subclasses to customize specific steps via hooks.

```mermaid
classDiagram
    class DeliveryCallbackMixin {
        <<mixin>>
        +_delivery_errors: int
        +_delivery_callback(err, msg) void
        +_on_delivery_failure(err, msg) void
        +_on_delivery_success(msg) void
    }

    class TradeProducer {
        +_on_delivery_failure(err, msg) void
        +_on_delivery_success(msg) void
    }

    class KafkaPublisher {
        +_pending_count: int
        +_delivered_count: int
        +_delivery_callback(err, msg) void
        +_on_delivery_failure(err, msg) void
        +_on_delivery_success(msg) void
    }

    class DLQHandler {
        +_on_delivery_failure(err, msg) void
        +_on_delivery_success(msg) void
    }

    DeliveryCallbackMixin <|-- TradeProducer
    DeliveryCallbackMixin <|-- KafkaPublisher
    DeliveryCallbackMixin <|-- DLQHandler

    note for DeliveryCallbackMixin "Template Method:\n_delivery_callback() calls hooks\n_on_delivery_failure()\n_on_delivery_success()"
```

**Benefits:**
- Single source of truth for callback structure
- Consistent error tracking (`_delivery_errors`)
- Subclasses only implement custom behavior (metrics, logging)
- Easy to test - mock the hooks
