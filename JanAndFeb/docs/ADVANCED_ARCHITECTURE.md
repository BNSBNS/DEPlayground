# Advanced Architecture Roadmap

This document outlines advanced features for production readiness that are beyond the current learning platform scope but provide guidance for future enhancement.

## 1. Persistent Window State

### Current State: In-Memory

The `WindowedAggregator` in `src/consumer/windowed_aggregator.py` uses in-memory state:

```python
# Current implementation
self._windows: dict[tuple[str, datetime], WindowState] = {}
```

**Limitations**:
- State lost on consumer restart
- Recovery requires full replay from Kafka
- Memory pressure with many active windows

### Recommended Solution: Redis State Store

Redis provides the best balance of simplicity and reliability for this learning platform.

#### Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Consumer  │────▶│   Redis     │────▶│  Consumer   │
│  (writes)   │     │ (state)     │     │  (reads)    │
└─────────────┘     └─────────────┘     └─────────────┘
      │                   │                   │
      │    Checkpoint every N events or T seconds
      │    Recovery: Load from Redis, resume Kafka
```

#### Implementation Sketch

```python
# src/consumer/persistent_aggregator.py
import redis
import json
from datetime import datetime
from decimal import Decimal

class RedisWindowStore:
    """Persistent window state using Redis."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.Redis.from_url(redis_url)
        self.key_prefix = "window:"
        self.ttl_seconds = 3600  # 1 hour TTL for windows

    def _make_key(self, symbol: str, window_start: datetime) -> str:
        return f"{self.key_prefix}{symbol}:{window_start.isoformat()}"

    def get_window(self, symbol: str, window_start: datetime) -> dict | None:
        """Get window state from Redis."""
        key = self._make_key(symbol, window_start)
        data = self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    def save_window(self, symbol: str, window_start: datetime, state: dict) -> None:
        """Save window state to Redis with TTL."""
        key = self._make_key(symbol, window_start)
        self.redis.setex(key, self.ttl_seconds, json.dumps(state))

    def delete_window(self, symbol: str, window_start: datetime) -> None:
        """Delete window after completion."""
        key = self._make_key(symbol, window_start)
        self.redis.delete(key)

    def get_all_windows(self, pattern: str = "*") -> list[dict]:
        """Get all active windows (for recovery)."""
        keys = self.redis.keys(f"{self.key_prefix}{pattern}")
        windows = []
        for key in keys:
            data = self.redis.get(key)
            if data:
                windows.append(json.loads(data))
        return windows


class PersistentWindowedAggregator:
    """Windowed aggregator with persistent state."""

    def __init__(
        self,
        store: RedisWindowStore,
        checkpoint_interval: int = 100,  # events
        checkpoint_timeout: int = 10,    # seconds
    ):
        self.store = store
        self.checkpoint_interval = checkpoint_interval
        self.checkpoint_timeout = checkpoint_timeout
        self._events_since_checkpoint = 0
        self._last_checkpoint = datetime.now()

        # In-memory working state (flushed to Redis periodically)
        self._windows: dict[tuple[str, datetime], WindowState] = {}

        # Recover state on startup
        self._recover_state()

    def _recover_state(self):
        """Recover window state from Redis on startup."""
        windows = self.store.get_all_windows()
        for w in windows:
            key = (w["symbol"], datetime.fromisoformat(w["window_start"]))
            self._windows[key] = WindowState.from_dict(w)

    def add_trade(self, trade: TradeEvent) -> list[TradeAggregate]:
        """Add trade with periodic checkpointing."""
        # ... existing add_trade logic ...

        self._events_since_checkpoint += 1
        if self._should_checkpoint():
            self._checkpoint()

        return completed

    def _should_checkpoint(self) -> bool:
        """Check if we should persist state."""
        if self._events_since_checkpoint >= self.checkpoint_interval:
            return True
        elapsed = (datetime.now() - self._last_checkpoint).total_seconds()
        if elapsed >= self.checkpoint_timeout:
            return True
        return False

    def _checkpoint(self):
        """Persist all window state to Redis."""
        for (symbol, window_start), state in self._windows.items():
            self.store.save_window(symbol, window_start, state.to_dict())
        self._events_since_checkpoint = 0
        self._last_checkpoint = datetime.now()
```

#### Docker Compose Addition

```yaml
# Add to docker-compose-full.yml
redis-state:
  image: redis:7-alpine
  container_name: redis-state
  ports:
    - "6380:6379"  # Different port to avoid conflict with Superset's Redis
  volumes:
    - redis_state_data:/data
  command: redis-server --appendonly yes  # AOF persistence

volumes:
  redis_state_data:
```

### Alternative: RocksDB (Embedded)

For higher performance without network overhead:

```python
# Using python-rocksdb
import rocksdb

class RocksDBWindowStore:
    def __init__(self, path: str = "/data/state/windows"):
        opts = rocksdb.Options()
        opts.create_if_missing = True
        self.db = rocksdb.DB(path, opts)
```

### Alternative: Kafka Streams (Python via Faust)

For Kafka-native state management:

```python
# Using Faust library
import faust

app = faust.App('energy-trading', broker='kafka://localhost:9092')

# Table automatically persisted with changelog topic
window_state = app.Table(
    'window_state',
    default=WindowState,
    partitions=6,
)

@app.agent(trades_topic)
async def process_trades(trades):
    async for trade in trades:
        key = (trade.symbol, get_window_start(trade.event_timestamp))
        window_state[key].add_trade(trade)
```

---

## 2. Distributed Tracing with OpenTelemetry

### Current State

- Prometheus metrics (push model)
- Structured logging with structlog
- No request correlation across services

### OpenTelemetry Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Producer   │────▶│   Kafka     │────▶│  Consumer   │────▶│ PostgreSQL  │
│  Span A     │     │ (headers)   │     │  Span A     │     │  Span A     │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                  │                   │                   │
       └──────────────────┴───────────────────┴───────────────────┘
                                   │
                            ┌──────▼──────┐
                            │   Jaeger/   │
                            │   Tempo     │
                            └─────────────┘
```

### Implementation

#### Setup Tracing

```python
# src/telemetry/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.kafka import KafkaInstrumentor

def setup_tracing(service_name: str, otlp_endpoint: str = "http://jaeger:4317"):
    """Initialize OpenTelemetry tracing."""
    provider = TracerProvider()

    # Export to Jaeger/Tempo via OTLP
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)

    # Auto-instrument Kafka
    KafkaInstrumentor().instrument()

    return trace.get_tracer(service_name)
```

#### Trace Context Propagation

```python
# In producer
from opentelemetry import trace
from opentelemetry.propagate import inject

tracer = trace.get_tracer("trade-producer")

def produce_trade(trade: TradeEvent):
    with tracer.start_as_current_span("produce_trade") as span:
        span.set_attribute("symbol", trade.symbol)
        span.set_attribute("trade_id", str(trade.trade_id))

        # Inject trace context into Kafka headers
        headers = {}
        inject(headers)

        producer.produce(
            topic="trades",
            key=trade.to_kafka_key(),
            value=trade.to_kafka_value(),
            headers=[(k, v.encode()) for k, v in headers.items()],
        )
```

```python
# In consumer
from opentelemetry.propagate import extract

def process_message(msg):
    # Extract trace context from Kafka headers
    headers = dict(msg.headers()) if msg.headers() else {}
    ctx = extract(headers)

    with tracer.start_as_current_span("consume_trade", context=ctx) as span:
        span.set_attribute("kafka.partition", msg.partition())
        span.set_attribute("kafka.offset", msg.offset())

        # Process trade
        trade = TradeEvent.from_kafka_value(json.loads(msg.value()))

        with tracer.start_as_current_span("aggregate_trade"):
            aggregates = aggregator.add_trade(trade)

        for agg in aggregates:
            with tracer.start_as_current_span("write_to_db"):
                db_writer.write(agg)
```

#### Docker Compose Addition

```yaml
# Jaeger for development
jaeger:
  image: jaegertracing/all-in-one:1.52
  container_name: jaeger
  ports:
    - "16686:16686"  # UI
    - "4317:4317"    # OTLP gRPC
    - "4318:4318"    # OTLP HTTP
  environment:
    COLLECTOR_OTLP_ENABLED: "true"

# Or Grafana Tempo for production
tempo:
  image: grafana/tempo:2.3.0
  container_name: tempo
  ports:
    - "3200:3200"    # Tempo API
    - "4317:4317"    # OTLP gRPC
  volumes:
    - ./monitoring/tempo.yml:/etc/tempo.yml:ro
  command: ["-config.file=/etc/tempo.yml"]
```

#### Dependencies

```toml
# pyproject.toml additions
"opentelemetry-api>=1.22.0",
"opentelemetry-sdk>=1.22.0",
"opentelemetry-exporter-otlp>=1.22.0",
"opentelemetry-instrumentation-kafka-python>=0.43b0",
"opentelemetry-instrumentation-psycopg>=0.43b0",
"opentelemetry-instrumentation-fastapi>=0.43b0",
```

### Trace Visualization

With Jaeger UI, you can:
- See end-to-end request flow
- Identify latency bottlenecks
- Debug failed requests
- Analyze service dependencies

---

## 3. Exactly-Once Semantics

### Current: At-Least-Once

```
Producer (idempotent) → Kafka → Consumer → DB (upsert)
                                    │
                            Manual commit after DB write
```

### Exactly-Once with Kafka Transactions

```python
# Producer with transactions
producer = Producer({
    'bootstrap.servers': 'kafka:9092',
    'transactional.id': 'trade-producer-1',
    'enable.idempotence': True,
})

producer.init_transactions()

try:
    producer.begin_transaction()
    producer.produce('trades', key=key, value=value)
    producer.commit_transaction()
except KafkaException:
    producer.abort_transaction()
```

```python
# Consumer with transactions (read-process-write)
consumer = Consumer({
    'bootstrap.servers': 'kafka:9092',
    'group.id': 'trade-aggregator',
    'isolation.level': 'read_committed',
    'enable.auto.commit': False,
})

producer = Producer({
    'bootstrap.servers': 'kafka:9092',
    'transactional.id': 'aggregator-producer-1',
})

producer.init_transactions()

for msg in consumer:
    producer.begin_transaction()
    try:
        # Process and produce output
        result = process(msg)
        producer.produce('aggregates', value=result)

        # Commit consumer offsets within transaction
        producer.send_offsets_to_transaction(
            consumer.position(consumer.assignment()),
            consumer.consumer_group_metadata()
        )

        producer.commit_transaction()
    except:
        producer.abort_transaction()
```

---

## Summary

| Feature | Current | Recommended Upgrade |
|---------|---------|---------------------|
| Window State | In-memory | Redis or RocksDB |
| Tracing | Logs only | OpenTelemetry + Jaeger |
| Delivery | At-least-once | Exactly-once (if needed) |
| State Recovery | Kafka replay | Checkpoint + resume |

These enhancements are documented here for reference but are not implemented in the current learning platform to maintain simplicity.
