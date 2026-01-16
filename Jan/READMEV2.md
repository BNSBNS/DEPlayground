# Data Engineering Assessment — Energy Trading Platform

Design, build, and scale robust data and software solutions, powering trading operations and analytics across a complex energy data landscape.

---

## Part 1 — System Design & Architecture

### Question 1: End-to-End Architecture

#### Task
Design a real-time analytics platform that ingests energy trade events and produces trader-facing metrics with sub-second latency. Historical data must be preserved for backtesting.

#### Deliverables

**Architecture diagram (ASCII or image) showing:**
- Trade producer
- Kafka
- Stream processing service
- Storage layers (hot and cold)
- Runtime environment

**Written explanation (1–2 pages max) covering:**
- Why Kafka is used instead of writing directly to a database
- How the system scales with increased trade volume
- How latency and backpressure are handled
- How correctness is preserved across restarts and failures
- Where OLTP (PostgreSQL) ends and OLAP (e.g. StarRocks) begins
- How historical data flows to cold storage for backtesting

#### Focus
- Decoupling
- Scalability
- Failure-aware design

#### Senior Engineer Guidance: Lambda Architecture

The system should be divided into two paths: a **hot path** for speed and live trading, and a **cold path** for accuracy and historical analysis.

**A. Ingestion Layer (Decoupling)**
- **Component:** Python producers running as Kubernetes pods
- **Function:** Connect to external APIs (such as EPEX and Nord Pool), normalize incoming data to a strict schema using Avro or Protobuf, and publish to Kafka.
- **Key Insight:** Data is never written directly from an API to a database. If a database is unavailable, market ticks must not be lost. Kafka serves as a durable, persistent buffer.

**B. Message Bus (Kafka)**
- **Configuration:** `acks=all`, requiring all replicas to acknowledge a message
- **Rationale:** In trading systems, durability is more important than throughput. Price updates cannot be sent on a fire-and-forget basis.

**C. Stream Processing (Business Logic)**
- **Component:** Python consumers or Apache Flink
- **Logic:** Calculate rolling volatility metrics or VWAP (Volume Weighted Average Price).
- **State Management:** Redis can store sliding-window state (e.g., last 15 minutes of prices), avoiding repeated database queries.

**D. Storage Strategy**
- **Hot Storage (StarRocks):** Aggregated metrics written here to power trader dashboards. StarRocks is optimized for sub-second OLAP queries.
- **Cold Storage (S3 Data Lake):** Kafka Connect sinks raw event logs to S3 in Parquet format, enabling quantitative analysts to backtest trading strategies.

---

### Question 2: Streaming Semantics

#### Task
Explain, in your own words:
- At-most-once, at-least-once, and exactly-once processing
- Which semantics your implementation provides and why
- How Kafka offsets, consumer commits, and database upserts interact

#### Stretch
Describe how you would achieve end-to-end exactly-once semantics and what trade-offs it introduces.

#### Focus
- Idempotency
- Offset discipline
- Real-world streaming behavior

#### Senior Engineer Guidance: Idempotency Patterns

**Preventing Duplicate Trade Processing**

Network retries can result in duplicate message delivery. The solution is idempotency at both the application and database level.

**Strategy:**
- Assign a unique `event_id` (or `trade_id`) to every trade at the source.
- Enforce idempotency at the database level using an upsert or ignore pattern.

**Example:**
```sql
INSERT INTO trades (id, price, volume)
VALUES (...)
ON CONFLICT (id) DO NOTHING;
```

This guarantees that even if Kafka delivers the same message twice, downstream PnL calculations remain correct.

**Key Interactions:**
- Commit offsets only **after** successful database writes
- Use transactional outbox pattern for true exactly-once when needed
- Understand the latency vs. correctness trade-off

---

## Part 2 — Streaming Implementation

### Question 3: Trade Event Producer

#### Task
Implement a Python service that produces realistic energy trade events to Kafka.

#### Requirements

**Event schema must include:**
- `trade_id` (UUID)
- `symbol` (e.g. `POWER_DE`, `GAS_NL`, `BRENT_OIL`)
- `price` (decimal)
- `volume` (decimal)
- `side` (BUY/SELL)
- `trader_id`
- `event_timestamp` (UTC)

- Use `symbol` as the Kafka message key
- Produce events continuously at a configurable rate
- Support burst patterns to simulate market volatility

#### Focus
- Partitioning strategy (why symbol as key?)
- Event time vs processing time
- Message ordering guarantees within a partition

---

### Question 4: Streaming Consumer with Windowed Aggregation

#### Task
Build a Kafka consumer that:
- Consumes trade events
- Groups them into 1-minute tumbling windows
- Computes per symbol:
  - Total traded volume
  - VWAP (Volume Weighted Average Price)
  - Trade count
  - Max/Min price
- Writes aggregates to PostgreSQL

#### Requirements
- Safe restart behavior (resume from last committed offset)
- No duplicate aggregates on recovery
- Kafka offsets committed only after successful database writes
- Handle late-arriving events gracefully

#### Focus
- Stateful stream processing
- Windowing logic and watermarks
- Failure recovery

---

### Question 5: Failure Handling & Dead Letter Queues

#### Task
Extend your streaming consumer to handle malformed messages that would otherwise crash the consumer and block the pipeline.

#### Requirements
- Implement a Dead Letter Queue (DLQ) pattern
- Malformed messages should not stop processing of valid messages
- Provide visibility into failed messages for debugging
- Include alerting when DLQ receives messages

#### Deliverables
- Code implementation of DLQ handling
- Explanation of the workflow

#### Senior Engineer Guidance: DLQ Pattern

**Problem:** A malformed message can cause a consumer to crash repeatedly, blocking the entire pipeline.

**Strategy:** Wrap message processing logic in a try/except block.

**Workflow:**
1. Catch the specific parsing exception
2. Publish the invalid payload to a dedicated Kafka topic (e.g., `trades-dlq`)
3. Manually commit the offset so the consumer can continue processing subsequent messages
4. Trigger an alert (e.g., PagerDuty, Slack) so developers can inspect the DLQ
5. Build a separate DLQ processor for manual review and replay

**Code Pattern:**
```python
try:
    trade = parse_trade_event(message)
    process_trade(trade)
    consumer.commit()
except ValidationError as e:
    publish_to_dlq(message, error=str(e))
    consumer.commit()  # Move past the bad message
    alert_on_call_engineer(message, e)
```

---

## Part 3 — Data Modeling & SQL Analytics

### Question 6: Schema Design

#### Task
Design the PostgreSQL schema for storing minute-level trade aggregates.

#### Deliverables
- SQL DDL

**Explanation of:**
- Primary key choice (composite vs surrogate)
- Indexing strategy for common access patterns
- Numeric precision considerations (trading correctness requires exact decimals)
- Time-series access patterns and partitioning
- How you would handle late-arriving data updates

#### Senior Engineer Guidance: OLTP vs OLAP

**When PostgreSQL Works:**
- Transactional writes with ACID guarantees
- Moderate query volumes
- Complex joins and updates

**When to Move to OLAP (StarRocks/ClickHouse):**
- Dashboard queries aggregating millions of rows
- Sub-second latency requirements on large datasets
- Read-heavy workloads with simple aggregations

**PostgreSQL Optimization Path:**
- Time-based partitioning (e.g., daily partitions)
- Materialized views for common aggregations
- Proper indexing (BRIN indexes for time-series)

---

### Question 7: Analytical Queries

#### Task
Write SQL queries for:
- VWAP per symbol over the last 60 minutes
- Rolling 24-hour traded volume per symbol
- Busiest trading minute per symbol (highest trade count)
- Top 5 symbols by total volume in the last hour

**Explain:**
- How these queries scale as data volume grows
- What indexes support each query
- What would change if this data moved to an OLAP engine

#### Senior Engineer Guidance: OLAP Performance

**Problem:** A dashboard query aggregating 500 million rows takes 45 seconds, but traders require results in under one second.

**Solution: StarRocks Aggregate Key Model**

StarRocks pre-computes aggregates during ingestion. Instead of scanning hundreds of millions of rows at query time, it reads pre-aggregated results.

**Outcome:** Query latency drops from 45 seconds to under 50 milliseconds.

**PostgreSQL Fallback Strategy:**
- Time partitioning to limit scan scope
- Materialized views refreshed on schedule
- Summary tables updated by triggers or batch jobs

---

## Part 4 — Python Data Engineering

### Question 8: Financial Time-Series Processing

#### Task
Clean a time-series dataset of trading prices and volumes with missing values and duplicates, then resample it to hourly VWAP.

#### Requirements
- Handle duplicate timestamps (later values are corrections)
- Handle missing price data appropriately
- Handle missing volume data appropriately
- Validate output for data quality issues
- Production-grade error handling

#### Deliverables
- Python code with type hints
- Explanation of your approach to missing data

#### Senior Engineer Guidance: Time-Series Imputation

**Key Insight:** Different data types require different imputation strategies.

- **Prices:** Use forward-fill (prices behave like step functions—the last known price persists)
- **Volume/Consumption:** Use interpolation (represents continuous physical processes)

**Production-Grade Pattern:**
```python
import pandas as pd

def process_trading_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and aggregates raw trading data to hourly VWAP.
    """
    # 1. Deduplication - later timestamps are corrections
    df = (
        df.sort_values("timestamp")
          .drop_duplicates(subset=["timestamp", "symbol"], keep="last")
    )

    # 2. Index by timestamp
    df = df.set_index("timestamp").sort_index()

    # 3. Handle missing data by type
    df["price"] = df["price"].ffill()  # Step function
    df["volume"] = df["volume"].interpolate(method="time")  # Continuous

    # 4. Compute hourly VWAP
    df["value"] = df["price"] * df["volume"]
    hourly = df.resample("1h").agg({
        "value": "sum",
        "volume": "sum"
    })
    hourly["vwap"] = hourly["value"] / hourly["volume"]

    # 5. Validation
    if (hourly["volume"] < 0).any():
        raise ValueError("Critical error: negative volume detected")

    return hourly[["vwap", "volume"]]
```

---

## Part 5 — Containerization & Kubernetes

### Question 9: Containerization

#### Task
Create Dockerfiles for:
- Trade producer
- Streaming consumer

#### Deliverables
- Dockerfiles for both services

**Explain:**
- Why minimal base images matter (security, size, startup time)
- How configuration should be injected via environment variables
- How secrets would be handled in production (not baked into images)
- Multi-stage builds for smaller production images

---

### Question 10: Kubernetes Deployment

#### Task
Deploy the streaming consumer to Kubernetes (kind or minikube).

#### Requirements
- Deployment with multiple replicas
- Resource requests and limits properly configured
- Consumer runs as part of a Kafka consumer group
- Liveness and readiness probes

#### Deliverables
- Kubernetes manifests (Deployment, Service, ConfigMap)

**Explain:**
- How Kafka consumer groups enable parallelism
- Why having more consumers than partitions causes idle pods
- How you would autoscale consumers based on lag

#### Senior Engineer Guidance: Resource Management

**Problem:** Consumer pods are crashing with `OOMKilled` errors.

**Solutions:**

*Immediate:*
- Increase `resources.limits.memory`
- Set requests close to limits to achieve Guaranteed QoS class

*Long-Term:*
- Configure Horizontal Pod Autoscaler (HPA) based on Kafka consumer lag
- If backlog grows, Kubernetes automatically scales out consumers

**Example HPA Metric:**
```yaml
metrics:
- type: External
  external:
    metric:
      name: kafka_consumer_lag
      selector:
        matchLabels:
          topic: trades
    target:
      type: AverageValue
      averageValue: "1000"
```

---

### Question 11: Failure Scenarios

#### Task
Demonstrate and explain the system's behavior when:
- A consumer pod is killed mid-processing
- PostgreSQL becomes unavailable for 5 minutes
- Kafka broker is restarted
- Network partition between consumer and Kafka

For each case, explain:
- Risk of data loss or duplication
- Recovery behavior and timeline
- Observability gaps and how to mitigate them
- Impact on traders viewing dashboards

---

## Part 6 — CI/CD & Operational Readiness

### Question 12: Continuous Integration

#### Task
Implement a CI pipeline (GitHub Actions, GitLab CI, or similar) that:
- Runs unit tests
- Runs linting and static type checks
- Builds Docker images
- Runs integration tests against containerized dependencies

#### Deliverables
- CI configuration file
- Explanation of pipeline stages

**Explain:**
- Why CI should fail fast (order of checks)
- What belongs in CI vs what does not
- The difference between CI and CD

#### Senior Engineer Guidance: CI Best Practices

**Tool Recommendations:**
- **Linting:** `ruff` (fast, comprehensive)
- **Type checking:** `mypy` with strict mode
- **Security:** Scan Docker images with `Trivy` to detect known CVEs before deployment

**Fail-Fast Order:**
1. Lint/format checks (fastest)
2. Type checks
3. Unit tests
4. Build Docker image
5. Security scan
6. Integration tests (slowest)

---

### Question 13: Local CD Simulation

#### Task
Simulate a CD flow locally:
- Make a code change
- Rebuild the image
- Perform a Kubernetes rolling update

#### Deliverables
- Scripts or commands to execute the flow
- Demonstration of zero-downtime deployment

**Explain:**
- Zero-downtime deployment strategy (rolling update settings)
- Rollback mechanics (`kubectl rollout undo`)
- Versioning and image tagging strategy (semantic versioning, git SHA)

#### Senior Engineer Guidance: Canary Releases

**Production CD Strategy:**

1. Deploy the new version to 10% of pods (canary)
2. Monitor error rates and latency for 5 minutes
3. If metrics are healthy, proceed to 50%, then 100%
4. If error rates increase, automatically roll back to the previous stable version

**Key Metrics to Watch:**
- Error rate (5xx responses)
- P99 latency
- Kafka consumer lag
- Database connection errors

---

## Part 7 — Observability & Production Thinking

### Question 14: Monitoring and Alerting

#### Task
Define a comprehensive monitoring strategy for the platform.

#### Deliverables

**Define key metrics for:**

*Kafka:*
- Consumer lag per partition
- Throughput (messages/sec)
- Broker disk usage
- Under-replicated partitions

*Application:*
- Processing latency (P50, P95, P99)
- Error rate by type
- Messages processed per minute
- DLQ message count

*Database:*
- Write latency
- Connection pool saturation
- Query execution time
- Replication lag (if applicable)

**Explain:**
- Alert thresholds and why (e.g., lag > 10,000 messages for > 5 minutes)
- Example incidents and runbook responses
- Impact of lag, partial data, or incorrect aggregation on traders

**Stretch:**
- Design a Grafana dashboard layout for on-call engineers
- Define SLOs (Service Level Objectives) for the platform

---

## Submission Expectations

Your submission should include:

- A Git repository with clean commit history
- Clear README with:
  - Local setup instructions (docker-compose for full stack)
  - Architecture diagram and design explanations
  - Trade-offs and assumptions documented
- Working code that can be run locally
- Tests demonstrating correctness

---

## Evaluation Criteria

You will be evaluated on:

| Criteria | Weight | Description |
|----------|--------|-------------|
| **Correctness** | High | Does the system produce accurate results? |
| **Robustness** | High | How does it handle failures, restarts, edge cases? |
| **Streaming Fundamentals** | High | Understanding of semantics, ordering, state |
| **System Design** | High | Appropriate architecture decisions and trade-offs |
| **Production Awareness** | Medium | Monitoring, alerting, operational considerations |
| **Code Quality** | Medium | Clean, readable, maintainable code |
| **Communication** | Medium | Clear explanations of decisions and trade-offs |

---

## Bonus Considerations

If you have additional time, consider addressing:

- **Schema Evolution:** How would you handle adding new fields to trade events?
- **Multi-Region:** How would the architecture change for a globally distributed system?
- **Backpressure:** Implement explicit backpressure handling when downstream is slow
- **Data Quality:** Add data quality checks and anomaly detection
- **Cost Optimization:** How would you optimize cloud costs for this workload?
