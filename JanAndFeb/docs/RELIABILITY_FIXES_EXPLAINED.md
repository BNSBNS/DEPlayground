# Reliability Fixes - Deep Dive & Rationale

## Critical Fixes Explained

### 1. DB Crash Issue - Why Retry Instead of Prevent?

**Question:** Why does this occur? Why retry after error instead of preventing it? Should DB use singleton? Why not DLQ?

**Answer:**
```
DB ERRORS YOU CANNOT PREVENT:
├─ Network hiccups (transient)     ← Retry makes sense
├─ DB server restarting            ← Retry makes sense
├─ Connection pool exhausted       ← Retry + backoff makes sense
├─ Deadlock (concurrent writes)    ← Retry with jitter makes sense
└─ Disk full / OOM on DB server    ← Retry won't help, but still don't crash

YOU CAN PREVENT:
└─ Malformed SQL / bad data        ← This should go to DLQ
```

**Why Retry?**
- **80% of DB errors are transient** (network, temp overload, brief unavailability)
- **Crashing loses all in-flight windows** (hundreds of aggregates)
- **Retry with backoff** gives DB time to recover

**Connection Pool + Retry Pattern (Not Just Singleton)**
- **Singleton alone won't fix reconnect issues**
- Singleton becomes a single point of failure during DB restarts
- **Better: Small connection pool (3-5 connections) + retry/backoff**
- Pool handles drop/reconnect automatically
- Multiple connections prevent serial bottlenecks

**Why Not DLQ for DB Errors?**
- DLQ is for **malformed data** (can't parse, invalid schema)
- DB errors are **infrastructure issues**, not data issues
- Retrying DB writes is idempotent (ON CONFLICT DO UPDATE)

**The Fix:**
```python
# Wrap DB writes in retry loop with exponential backoff
for attempt in range(max_retries):
    try:
        self._db_writer.write_aggregates_batch(aggregates)
        break  # Success
    except DBError as e:
        if attempt < max_retries - 1:
            backoff = min(2 ** attempt, 30)  # Max 30s
            logger.warning(f"DB write failed, retry in {backoff}s", error=e)
            await asyncio.sleep(backoff)
        else:
            logger.error("DB write failed after retries, keeping consumer alive")
            # Don't crash - keep processing new messages
```

---

### 2. Producer Exception Handling - Design Pattern?

**Question:** Is this basic handling? Can we use a design pattern to make it reusable?

**Answer:**
 **Yes! Use the Circuit Breaker Pattern + Retry Decorator**

**Why Circuit Breaker?**
- Prevents cascading failures
- Automatically stops retrying after N failures (opens circuit)
- Periodically tests if system recovered (half-open state)
- Used by Netflix, AWS, Google for resilience

**When to Use Each Pattern:**
- **Circuit Breaker**: DB writes, ingestion connectors (slow recovery)
- **Bounded Retry + DLQ**: Kafka produce (fast broker restarts, don't want flapping)

**Reusable Patterns:**
```python
# src/common/resilience.py
from tenacity import retry, stop_after_attempt, wait_exponential

# Circuit Breaker for DB/external APIs (slow recovery)
class CircuitBreaker:
    """Reusable circuit breaker for any operation."""
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.state = "closed"  # closed, open, half-open
        self.last_failure_time = None
        self.timeout = timeout

    def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"  # Try again
            else:
                raise CircuitOpenError("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise

# Bounded retry for Kafka produce (no circuit breaker - brokers restart fast)
def resilient_kafka_produce(producer, topic, key, value, max_retries=3):
    """Retry with backoff/jitter for Kafka produce. No circuit breaker to avoid flapping."""
    for attempt in range(max_retries):
        try:
            producer.produce(topic, key=key, value=value)
            producer.flush(timeout=5)
            return  # Success
        except BufferError:
            # Buffer full - poll and retry
            producer.poll(1.0)
            if attempt < max_retries - 1:
                backoff = min(2 ** attempt, 10)
                jitter = backoff * random.random()
                time.sleep(backoff + jitter)
        except KafkaException as e:
            logger.error(f"Kafka produce failed: {e}")
            if attempt == max_retries - 1:
                # Failed after retries - route to parking queue/DLQ
                parking_queue.put((topic, key, value, str(e)))
                return
            # Retry with backoff
            backoff = min(2 ** attempt, 10)
            jitter = backoff * random.random()
            time.sleep(backoff + jitter)
```

**Usage:**
```python
circuit_breaker = CircuitBreaker()
circuit_breaker.call(resilient_kafka_produce, producer, "trades", key, value)
```

---

### 3. Idle Window Flush - Is This a Timeout?

**Question:** Is this a timeout issue?

**Answer:**
**No, it's a "no-trigger" issue.**

**Current Behavior:**
```
Event arrives → Window closes ONLY when NEXT event arrives
                (watermark advances)

If traffic stops → Last window NEVER closes → Data stuck in memory
```

**Example:**
```
10:00:00 - Event A arrives → creates window [10:00:00-10:01:00]
10:00:30 - Event B arrives → still in same window
10:01:05 - Event C arrives → NOW window [10:00:00-10:01:00] closes
                             (watermark = 10:01:05, window ended at 10:01:00)

 PROBLEM: If no Event C arrives, window [10:00:00-10:01:00] NEVER closes!
```

**The Fix - Periodic Timer:**
```python
# In TradeConsumer.__init__
self._flush_task = None

async def _periodic_flush_task(self):
    """Background task to flush idle windows every 60s."""
    while self._running:
        await asyncio.sleep(60)

        # Manually advance watermark to current time
        now = datetime.now(UTC)
        if self._aggregator._latest_event_time is None:
            continue

        # Flush any windows that should have closed
        results = self._aggregator.flush_stale_windows(now)
        if results:
            await self._write_and_commit(results)

# Start timer in run()
self._flush_task = asyncio.create_task(self._periodic_flush_task())
```

---

### 4. Missing DB Fields - How Does This Happen?

**Question:** Explain how this happens and why the fix is ideal.

**Answer:**

**Root Cause: Model-Schema Mismatch**
```python
# MODEL (src/common/models.py)
class TradeAggregate(BaseModel):
    vwap: Decimal          Written to DB
    total_volume: Decimal  Written to DB
    total_value: Decimal   COMPUTED BUT NOT WRITTEN!
    lmp: Decimal          COMPUTED BUT NOT WRITTEN!
    lmp_energy: Decimal   COMPUTED BUT NOT WRITTEN!

# DB SCHEMA (sql/schema/002_trade_aggregates.sql)
CREATE TABLE trade_aggregates (
    vwap NUMERIC,          Exists
    total_volume NUMERIC,  Exists
    -- total_value missing!
    -- lmp fields missing!
);

# DB WRITER (src/consumer/db_writer.py)
INSERT INTO trade_aggregates (vwap, total_volume, ...)
VALUES (%(vwap)s, %(total_volume)s, ...)
-- total_value not in INSERT statement!
```

**How It Happens:**
1. Developer adds field to model for intermediate calculation
2. Forgets to add column to database schema
3. Forgets to add field to INSERT statement
4. Code runs fine (no error), but data is silently lost

**The Fix - 3 Options:**

**Option A: Remove Unused Fields (Simplest)**
```python
# If total_value is only used for VWAP calculation:
class TradeAggregate(BaseModel):
    vwap: Decimal
    total_volume: Decimal
    # Remove: total_value (internal calculation only)
```

**Option B: Add Missing Columns (If Needed)**
```sql
ALTER TABLE trade_aggregates
ADD COLUMN total_value NUMERIC,
ADD COLUMN lmp NUMERIC,
ADD COLUMN lmp_energy NUMERIC;
```

**Option C: Contract Test (Best Practice)**
```python
# tests/integration/test_db_schema_contract.py
import pytest
from src.common.models import TradeAggregate
from src.consumer.db_writer import DatabaseWriter

def test_trade_aggregate_db_contract():
    """Contract test: Ensure DB columns match TradeAggregate model fields.

    Catches drift when fields are added to model but not to DB schema.
    """
    # Get model fields
    model_fields = set(TradeAggregate.__fields__.keys())

    # Get DB columns
    db_writer = DatabaseWriter()
    db_columns = db_writer.get_table_columns("trade_aggregates")

    # Assert all model fields have corresponding DB columns
    missing_in_db = model_fields - db_columns
    assert not missing_in_db, f"Model fields missing in DB: {missing_in_db}"

    # Also check that INSERT statement includes all fields
    insert_fields = db_writer.get_insert_fields()
    missing_in_insert = model_fields - insert_fields
    assert not missing_in_insert, f"Model fields missing in INSERT: {missing_in_insert}"

    # Specific check for fields we know should be there
    required_fields = {'vwap', 'total_volume', 'total_value', 'lmp', 'lmp_energy'}
    assert required_fields.issubset(db_columns), f"Missing critical fields: {required_fields - db_columns}"
```

**Run on every commit:**
```bash
pytest tests/integration/test_db_schema_contract.py -v
```

---

### 5. Offset Commit Timing - Incorrect Sequence?

**Question:** Is this due to incorrect code sequence?

**Answer:**
**Yes, timer placement is wrong.**

**Current Code (WRONG):**
```python
commit_start = time.perf_counter()  # ← Timer starts ONCE

for partition, offset in partition_max_offsets.items():
    commit_result = self._offset_manager.commit_up_to(partition, offset)
    # Each commit takes ~10ms

    metrics.offset_commit_duration.observe(
        time.perf_counter() - commit_start  # ← WRONG! Accumulates
    )
    # Partition 0: records 10ms ✓
    # Partition 1: records 20ms ✗ (should be 10ms)
    # Partition 2: records 30ms ✗ (should be 10ms)
```

**Fix:**
```python
for partition, offset in partition_max_offsets.items():
    commit_start = time.perf_counter()  # ← Move timer INSIDE loop
    commit_result = self._offset_manager.commit_up_to(partition, offset)

    duration = time.perf_counter() - commit_start
    metrics.offset_commit_duration.observe(duration)  # ✓ Correct per-partition timing
```

---

### 6. Memory Estimation - Different Method?

**Question:** Is this due to a different calculation method?

**Answer:**
**Yes, `sys.getsizeof()` is too naive.**

**Why It Underestimates:**
```python
# Current code
sys.getsizeof(self.total_value)  # Returns ~32 bytes

# Reality:
# - Decimal object: 32 bytes
# - But doesn't count:
#   - String representation inside Decimal
#   - Coefficient array
#   - Context precision data
# Actual size: ~200 bytes!
```

**Better Approaches:**

**Option A: Use `tracemalloc` (Most Accurate)**
```python
import tracemalloc

tracemalloc.start()
# ... create windows ...
current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
```

**Option B: Use psutil for RSS (Process Memory)**
```python
import psutil
process = psutil.Process()
memory_bytes = process.memory_info().rss
```

**Option C: Empirical Multiplier (Simplest)**
```python
# Measure actual memory for 1000 windows, divide by 1000
BYTES_PER_WINDOW = 5000  # Empirically measured

def get_estimated_memory_usage(self) -> int:
    return len(self._windows) * BYTES_PER_WINDOW
```

---

### 7. DB Connection Pool - Concurrency + Reconnect

**Question:** Is this similar to #1 or for concurrent connections? Config change?

**Answer:**
**Different focus! #1 = retry on crashes, #7 = concurrency + auto-reconnect.**

**Problem:**
```
Single connection = Serial writes = Slow

Window 1 flush → [Wait 50ms for DB] → Window 2 flush → [Wait 50ms] → ...
                    ↑ Bottleneck!
```

**Solution: Connection Pool**
```
Pool of 5 connections = Parallel writes = Fast

Window 1 → [Connection A, 50ms]
Window 2 → [Connection B, 50ms]  } All at once!
Window 3 → [Connection C, 50ms]
Window 4 → [Connection D, 50ms]
Window 5 → [Connection E, 50ms]
```

**Config Change (Not Code):**
```python
# src/consumer/db_writer.py
from psycopg2.pool import ThreadedConnectionPool

class DatabaseWriter:
    def __init__(self, min_conn=2, max_conn=10):
        self._pool = ThreadedConnectionPool(
            minconn=min_conn,
            maxconn=max_conn,
            host=..., database=..., user=..., password=...
        )

    def write_aggregates_batch(self, aggregates):
        conn = self._pool.getconn()  # Get from pool
        try:
            # ... write ...
        finally:
            self._pool.putconn(conn)  # Return to pool
```

**Sizing Guide:**
- `min_conn=2` - Always ready connections
- `max_conn=10` - Cap to prevent overwhelming DB
- Rule of thumb: `max_conn = 2 * num_cores_on_db_server`

---

### 8. Buffer Retry - Industry Practice?

**Question:** What is the industry practice and why?

**Answer:**

**Industry Standard: "Retry with Exponential Backoff + Jitter"**

Used by:
- AWS SDK
- Google Cloud SDK
- Kafka (internally)
- Stripe API
- Twilio API

**Why?**
1. **Exponential Backoff**: Gives system time to recover
2. **Jitter**: Prevents thundering herd (all clients retry at same time)
3. **Circuit Breaker**: Stops after N failures to prevent overload

**Implementation:**
```python
import random

def retry_with_backoff(func, max_retries=5):
    for attempt in range(max_retries):
        try:
            return func()
        except BufferError:
            if attempt == max_retries - 1:
                raise  # Give up after max retries

            # Exponential backoff: 1s, 2s, 4s, 8s, 16s
            backoff = 2 ** attempt

            # Add jitter (random 0-100% of backoff)
            jitter = backoff * random.random()
            wait_time = backoff + jitter

            logger.warning(f"Buffer full, retry in {wait_time:.2f}s")
            time.sleep(wait_time)

            # Also poll to make space
            producer.poll(0.1)
```

**Why Not Infinite Retry?**
- Prevents infinite loops if broker is truly down
- Allows higher-level circuit breaker to engage
- Metrics show problem (retry_count)

---

## Nice-to-Have Features

### 9. Per-Symbol Watermark

**Problem:** Global watermark can evict truly late events.

**Example:**
```
Symbol A: Events every 1ms (high frequency)
Symbol B: Events every 10s (low frequency)

Global watermark advances with Symbol A
→ Symbol B's window closes before its events arrive
→ Data loss for Symbol B
```

**Solution:**
```python
class WindowedAggregator:
    def __init__(self):
        self._watermarks: dict[str, datetime] = {}  # Per symbol

    def _should_evict_window(self, symbol, window_start):
        symbol_watermark = self._watermarks.get(symbol)
        if not symbol_watermark:
            return False

        return symbol_watermark > window_start + self.grace_period
```

### 10. Adaptive Lag Refresh

**Problem:** Fixed 10s interval wastes broker calls when idle.

**Solution:**
```python
def _get_adaptive_interval(self, current_lag):
    if current_lag > 10000:
        return 1.0  # Check every 1s when falling behind
    elif current_lag > 1000:
        return 5.0  # Check every 5s when moderate lag
    else:
        return 30.0  # Check every 30s when caught up
```

### 11-15. Future Enhancements

See [FUTURE_ROADMAP.md](FUTURE_ROADMAP.md) for:
- OpenTelemetry integration
- Schema Registry setup
- DLQ Replay CLI
- Chaos testing in CI
- Health endpoint patterns

---

## Summary

| Fix | Why It Happens | Fix Type | Pattern |
|-----|----------------|----------|---------|
| #1 DB Crash | Transient network/DB issues | Retry + Keep Running | Resilience |
| #2 Producer Exception | Incomplete error handling | Circuit Breaker | Resilience |
| #3 Idle Flush | No trigger when quiet | Background Timer | Completeness |
| #4 Missing Fields | Model-schema mismatch | Validation Test | Correctness |
| #5 Offset Timing | Timer outside loop | Move Timer | Observability |
| #6 Memory Calc | Naive sizeof() | Use RSS/tracemalloc | Accuracy |
| #7 DB Pool | Serial writes | Connection Pool | Performance |
| #8 Buffer Retry | Single retry attempt | Exponential Backoff | Resilience |
