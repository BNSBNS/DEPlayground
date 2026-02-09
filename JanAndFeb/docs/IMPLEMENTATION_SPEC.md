# Implementation Specification - Reliability Fixes

## Acceptance Criteria & Defaults

### Fix #1: DB Retry with Connection Pool

**Acceptance Criteria (Definition of Done):**
- [ ] Connection pool configured (min=2, max=5)
- [ ] OperationalError triggers reconnect with backoff (1s, 2s, 4s)
- [ ] Max 3 retries per batch write
- [ ] Metric: `db_write_retries_total` counter with labels `{status=success|failure}`
- [ ] Test: `test_db_reconnect_on_operational_error()` passes
- [ ] Alert: `db_write_failures > 10 in 5m` → page

**Shutdown Semantics When Retries Exhausted:**
- **Keep running** - log error, skip failed batch, continue processing new messages
- Readiness: `/readyz` returns 503 if DB unavailable for > 30s
- Degraded mode: Accept new messages but don't write (queue backlog)

**Configuration:**
```python
DB_POOL_MIN = 2
DB_POOL_MAX = 5
DB_RETRY_MAX = 3
DB_RETRY_BACKOFF = [1, 2, 4]  # seconds
DB_POOL_RECYCLE = 1800  # 30 min (avoid stale connections)
DB_POOL_PRE_PING = True  # Health check before use
```

---

### Fix #2: Producer Retry + Circuit Breaker

**Acceptance Criteria:**
- [ ] Circuit breaker for DB writes (threshold=5 failures, timeout=60s)
- [ ] Bounded retry for Kafka produce (max=3, backoff + jitter)
- [ ] Parking queue for failed produces (local disk queue)
- [ ] Metric: `kafka_produce_retries_total{status=success|failure}`
- [ ] Metric: `circuit_breaker_state{component=db|kafka, state=open|closed|half_open}`
- [ ] Test: `test_circuit_breaker_opens_after_failures()` passes
- [ ] Alert: `parking_queue_size > 100` → investigate

**Shutdown Semantics:**
- **Give up to DLQ after max attempts** - don't block indefinitely
- Parking queue flushed to `trades-parking` topic on shutdown
- Circuit breaker logs state transitions (open → half-open → closed)

**Configuration:**
```python
KAFKA_PRODUCE_MAX_RETRIES = 3
KAFKA_PRODUCE_BACKOFF_BASE = 1  # seconds
KAFKA_PRODUCE_JITTER_MAX = 0.5  # 50% jitter
CIRCUIT_BREAKER_THRESHOLD = 5  # failures to open
CIRCUIT_BREAKER_TIMEOUT = 60  # seconds before half-open
PARKING_QUEUE_MAX_SIZE = 1000
```

---

### Fix #3: Idle Window Flush Timer

**Acceptance Criteria:**
- [ ] Background task flushes windows every 60s
- [ ] Max flush batch size: 100 windows per cycle
- [ ] Task cancelled gracefully on shutdown (no orphaned windows)
- [ ] Metric: `idle_flushes_total` counter
- [ ] Metric: `idle_flush_windows_count` histogram
- [ ] Test: `test_idle_windows_flushed_after_interval()` passes
- [ ] No data loss when traffic stops for > 1 minute

**Shutdown Semantics:**
- Task cancellation → flush all remaining windows immediately
- Wait for flush to complete before closing consumer

**Configuration:**
```python
IDLE_FLUSH_INTERVAL = 60  # seconds
IDLE_FLUSH_MAX_BATCH = 100  # windows per cycle
IDLE_FLUSH_GRACE_PERIOD = 30  # seconds (same as late event grace)
```

**Implementation:**
```python
async def _idle_flush_task(self):
    """Background task to flush stale windows."""
    while self._running:
        try:
            await asyncio.sleep(IDLE_FLUSH_INTERVAL)

            # Manually advance watermark
            now = datetime.now(UTC)
            results = self._aggregator.flush_stale_windows(now)

            if results:
                logger.info(f"Idle flush: {len(results)} windows")
                await self._write_and_commit(results)
                metrics.idle_flushes_total.inc()
                metrics.idle_flush_windows_count.observe(len(results))

        except asyncio.CancelledError:
            logger.info("Idle flush task cancelled")
            break
```

---

### Fix #4: DB Schema Contract Test

**Acceptance Criteria:**
- [ ] Contract test runs in CI on every commit
- [ ] Fails if model field missing from DB schema
- [ ] Fails if model field missing from INSERT statement
- [ ] Covers critical fields: `vwap`, `total_volume`, `total_value`, `lmp`, `lmp_energy`
- [ ] Test: `test_trade_aggregate_db_contract()` in CI

**Configuration:**
```python
REQUIRED_DB_FIELDS = {
    'symbol', 'window_start', 'window_end',
    'vwap', 'total_volume', 'total_value',
    'trade_count', 'max_price', 'min_price',
    'lmp', 'lmp_energy', 'lmp_congestion', 'lmp_loss',
}
```

---

### Fix #5: Offset Commit Timing Fix

**Acceptance Criteria:**
- [ ] Timer moved inside partition loop
- [ ] Metric: `offset_commit_duration_seconds` histogram per partition
- [ ] Test: Verify P50/P95/P99 are realistic (< 100ms)

**Expected Behavior:**
- Before: Partition 2 shows 30ms (cumulative)
- After: Partition 2 shows 10ms (actual per-commit time)

---

### Fix #6: Memory Estimation

**Acceptance Criteria:**
- [ ] Pick ONE method: **Empirical per-window cost**
- [ ] Measured empirically: 5KB per window (average)
- [ ] Alert threshold: 80% of max_memory_mb
- [ ] Metric: `aggregator_memory_bytes` gauge
- [ ] Metric: `aggregator_memory_utilization_pct` gauge
- [ ] Alert: `aggregator_memory_utilization_pct > 80` → backpressure

**Configuration:**
```python
EMPIRICAL_BYTES_PER_WINDOW = 5000  # Measured with 1000 windows
MAX_MEMORY_MB = 256
MEMORY_ALERT_THRESHOLD = 0.8  # 80%

def get_estimated_memory_usage(self) -> int:
    """Use empirical per-window cost (simplest, most reliable)."""
    return len(self._windows) * EMPIRICAL_BYTES_PER_WINDOW
```

**Why Empirical?**
- `sys.getsizeof()` underestimates by 50-70%
- `tracemalloc` adds 10-20% overhead
- Empirical is fast, accurate enough, zero overhead

---

### Fix #7: DB Connection Pool

**Acceptance Criteria:**
- [ ] Pool min=2, max=5 (per consumer)
- [ ] Recycle connections after 30min (avoid stale sockets)
- [ ] Pre-ping before each use (health check)
- [ ] OperationalError triggers close + reopen
- [ ] Metric: `db_pool_size{state=idle|active}` gauge
- [ ] Test: `test_pool_reconnects_on_operational_error()` passes

**Configuration:**
```python
DB_POOL_MIN = 2
DB_POOL_MAX = 5
DB_POOL_RECYCLE = 1800  # 30 minutes
DB_POOL_PRE_PING = True  # Test connection before use
DB_POOL_TIMEOUT = 10  # Wait 10s for connection from pool
```

---

### Fix #8: Producer Buffer Retry

**Acceptance Criteria:**
- [ ] Exponential backoff with jitter (1s, 2s, 4s, 8s, 10s max)
- [ ] Max 5 retries for BufferError
- [ ] Route to parking queue after exhausting retries
- [ ] Metric: `producer_buffer_full_retries_total{status=success|failure}`
- [ ] Alert: `producer_buffer_full_retries{status=failure} > 10` → tune buffer config

**Configuration:**
```python
PRODUCER_BUFFER_MAX_RETRIES = 5
PRODUCER_BUFFER_BACKOFF_BASE = 1  # seconds
PRODUCER_BUFFER_BACKOFF_MAX = 10  # seconds
PRODUCER_BUFFER_JITTER = 0.5  # 50%
```

---

## Future Enhancements Spec

### OpenTelemetry Tracing

**Acceptance Criteria:**
- [ ] Trace context propagated via Kafka headers: `traceparent`, `tracestate`
- [ ] Sampling: 10% default (configurable via OTEL_TRACES_SAMPLER_ARG)
- [ ] Spans: `kafka.poll` → `parse` → `aggregate` → `db.write` → `kafka.commit`
- [ ] Jaeger UI accessible at http://localhost:16686

**Configuration:**
```python
OTEL_EXPORTER_JAEGER_ENDPOINT = "http://localhost:14268/api/traces"
OTEL_TRACES_SAMPLER = "traceidratio"
OTEL_TRACES_SAMPLER_ARG = "0.1"  # 10% sampling
KAFKA_TRACE_HEADER_TRACEPARENT = "traceparent"
KAFKA_TRACE_HEADER_TRACESTATE = "tracestate"
```

---

### Schema Registry

**Acceptance Criteria:**
- [ ] Compatibility mode: **BACKWARD** (new schema can read old data)
- [ ] Value format: Avro (binary, 50% smaller than JSON)
- [ ] Key format: String (simple symbol partitioning)
- [ ] Subject naming: `<topic>-value` (default strategy)
- [ ] Schema evolution: Add optional fields only (no removals)

**Configuration:**
```python
SCHEMA_REGISTRY_URL = "http://localhost:8081"
SCHEMA_COMPATIBILITY_MODE = "BACKWARD"
SCHEMA_SUBJECT_NAMING = "TopicNameStrategy"  # <topic>-value
AVRO_VALUE_SCHEMA_FILE = "schemas/trade_event_v1.avsc"
```

---

### DLQ Replay CLI

**Acceptance Criteria:**
- [ ] Idempotency: Use original message keys (required)
- [ ] Tag replays: Add header `x-replay-id=<timestamp>-<user>`
- [ ] Loop prevention: Check for `x-replay-count` header, fail if > 3
- [ ] Dry-run mode: `--dry-run` flag shows what would be replayed
- [ ] Rate limit: Default 100 msg/s (configurable via `--rate-limit`)
- [ ] Commit strategy: Commit DLQ offset only after successful republish

**Configuration:**
```python
DLQ_REPLAY_RATE_LIMIT = 100  # messages per second
DLQ_REPLAY_MAX_COUNT = 3  # Max replay attempts per message
DLQ_REPLAY_HEADER_ID = "x-replay-id"
DLQ_REPLAY_HEADER_COUNT = "x-replay-count"
```

**Usage:**
```bash
# Dry run first
python -m tools.dlq replay --offset-range 100-200 --dry-run

# Actual replay
python -m tools.dlq replay --offset-range 100-200 --target-topic trades --rate-limit 50
```

---

### Chaos CI

**Acceptance Criteria:**
- [ ] Cleanup step: `docker-compose down -v` after tests
- [ ] Timeout guard: Workflow fails after 15 minutes
- [ ] Prometheus snapshot on failure: Saved to artifacts
- [ ] SLO checks: Lag < 10k, DLQ < 1/s, not paused > 10s
- [ ] Teardown even on failure (use `always()` condition)

**Workflow:**
```yaml
- name: Run chaos tests
  timeout-minutes: 10
  run: pytest tests/chaos/ -v

- name: Verify SLOs
  run: ./scripts/verify-slos.sh

- name: Save Prometheus snapshot on failure
  if: failure()
  run: |
    curl -XPOST http://localhost:9090/api/v1/admin/tsdb/snapshot
    cp -r /prometheus/snapshots/* $GITHUB_WORKSPACE/prom-snapshot/

- name: Upload artifacts
  if: failure()
  uses: actions/upload-artifact@v3
  with:
    name: prometheus-snapshot
    path: prom-snapshot/

- name: Cleanup (always runs)
  if: always()
  run: docker-compose -f docker-compose-full.yml down -v
```

---

### Health Endpoints

**Acceptance Criteria:**
- [ ] Port: 8001 (consumer), 8002 (producer), 8003 (ingestion)
- [ ] Routes: `/healthz` (liveness), `/readyz` (readiness)
- [ ] Readiness checks:
  - Kafka: `consumer.list_topics(timeout=1)` succeeds
  - DB: `db_writer.ping()` succeeds (use pool)
  - Backpressure: Not paused for > 30s
- [ ] Thresholds:
  - Kafka timeout: 1s
  - DB timeout: 2s
  - Backpressure stuck threshold: 30s

**Configuration:**
```python
HEALTH_PORT = 8001
HEALTH_KAFKA_TIMEOUT = 1.0  # seconds
HEALTH_DB_TIMEOUT = 2.0  # seconds
HEALTH_BACKPRESSURE_MAX_PAUSE = 30  # seconds
```

**Kubernetes Integration:**
```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8001
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5

readinessProbe:
  httpGet:
    path: /readyz
    port: 8001
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3  # Mark unready after 3 failures (15s)
```

---

### Security Quick Win

**Acceptance Criteria:**
- [ ] TLS placeholders for Kafka (enabled via `KAFKA_SECURITY_PROTOCOL`)
- [ ] SASL placeholders for Kafka (enabled via `KAFKA_SASL_MECHANISM`)
- [ ] DB SSL mode (enabled via `DB_SSL_MODE`)
- [ ] Local dev: All security disabled by default
- [ ] Prod: Security enabled via environment variables

**Configuration:**
```python
# Kafka Security (disabled in local dev)
KAFKA_SECURITY_PROTOCOL = "PLAINTEXT"  # or "SSL", "SASL_SSL"
KAFKA_SASL_MECHANISM = None  # or "PLAIN", "SCRAM-SHA-256"
KAFKA_SSL_CA_LOCATION = None  # /path/to/ca-cert
KAFKA_SSL_CERT_LOCATION = None  # /path/to/client-cert
KAFKA_SSL_KEY_LOCATION = None  # /path/to/client-key

# DB Security (disabled in local dev)
DB_SSL_MODE = "disable"  # or "require", "verify-ca", "verify-full"
DB_SSL_ROOT_CERT = None  # /path/to/root.crt
DB_SSL_CERT = None  # /path/to/client.crt
DB_SSL_KEY = None  # /path/to/client.key
```

**Local Dev (.env):**
```bash
KAFKA_SECURITY_PROTOCOL=PLAINTEXT
DB_SSL_MODE=disable
```

**Production (K8s secrets):**
```yaml
env:
  - name: KAFKA_SECURITY_PROTOCOL
    value: "SASL_SSL"
  - name: KAFKA_SASL_MECHANISM
    value: "SCRAM-SHA-256"
  - name: DB_SSL_MODE
    value: "verify-full"
```

---

## Implementation Order

| Priority | Fix | Effort | Impact |
|----------|-----|--------|--------|
| P0 | DB retry + pool (#1, #7) | 4h | Prevents crash loops |
| P0 | Idle window flush (#3) | 2h | Prevents data loss |
| P0 | Schema contract test (#4) | 1h | Catches drift |
| P1 | Producer retry (#2) | 3h | Prevents crash loops |
| P1 | Memory estimation (#6) | 1h | Better monitoring |
| P2 | Offset timing (#5) | 30min | Better metrics |
| P2 | Buffer retry (#8) | 1h | Better resilience |

**Total Critical Path: 11.5 hours**

---

## Verification Checklist

Before merging:
- [ ] All acceptance criteria met
- [ ] Tests pass in CI
- [ ] Metrics visible in Prometheus
- [ ] Alerts configured in AlertManager
- [ ] Documentation updated
- [ ] Changelog entry added
