# Source A

## Part 1 — System Design & Architecture

## Question 1: End-to-End Architecture

### Task
Design a real-time analytics platform that ingests energy trade events and produces trader-facing metrics.

### Deliverables

**Architecture diagram (ASCII or image) showing:**
- Trade producer  
- Kafka  
- Stream processing service  
- Storage layers  
- Runtime environment  

**Written explanation (1–2 pages max) covering:**
- Why Kafka is used instead of writing directly to a database  
- How the system scales with increased trade volume  
- How latency and backpressure are handled  
- How correctness is preserved across restarts and failures  
- Where OLTP (PostgreSQL) ends and OLAP (e.g. StarRocks) begins  

### Focus
- Decoupling  
- Scalability  
- Failure-aware design  

---

## Question 2: Streaming Semantics

### Task
Explain, in your own words:
- At-most-once, at-least-once, and exactly-once processing  
- Which semantics your implementation provides and why  
- How Kafka offsets, consumer commits, and database upserts interact  

### Stretch
Describe how you would achieve end-to-end exactly-once semantics and what trade-offs it introduces.

### Focus
- Idempotency  
- Offset discipline  
- Real-world streaming behavior  

---

# Part 2 — Streaming Implementation

## Question 3: Trade Event Producer

### Task
Implement a Python service that produces realistic energy trade events to Kafka.

### Requirements

**Event schema must include:**
- `trade_id` (UUID)  
- `symbol` (e.g. `POWER_DE`, `GAS_NL`)  
- `price`  
- `volume`  
- `event_timestamp` (UTC)  

- Use `symbol` as the Kafka message key  
- Produce events continuously at a configurable rate  

### Focus
- Partitioning strategy  
- Event time vs processing time  
- Message ordering guarantees  

---

## Question 4: Streaming Consumer with Windowed Aggregation

### Task
Build a Kafka consumer that:
- Consumes trade events  
- Groups them into 1-minute tumbling windows  
- Computes:
  - Total traded volume  
  - VWAP (Volume Weighted Average Price)  
- Writes aggregates to PostgreSQL  

### Requirements
- Safe restart behavior  
- No duplicate aggregates  
- Kafka offsets committed only after successful database writes  

### Focus
- Stateful stream processing  
- Windowing logic  
- Failure recovery  

---

# Part 3 — Data Modeling & SQL Analytics

## Question 5: Schema Design

### Task
Design the PostgreSQL schema for storing minute-level trade aggregates.

### Deliverables
- SQL DDL  

**Explanation of:**
- Primary key choice  
- Indexing strategy  
- Numeric precision considerations (trading correctness)  
- Time-series access patterns  

---

## Question 6: Analytical Queries

### Task
Write SQL queries for:
- VWAP per symbol over the last 60 minutes  
- Rolling 24-hour traded volume per symbol  
- Busiest trading minute per symbol  

**Explain:**
- How these queries scale as data volume grows  
- What would change if this data moved to an OLAP engine  

---

# Part 4 — Containerization & Kubernetes (System Engineering Focus)

## Question 7: Containerization

### Task
Create Dockerfiles for:
- Trade producer  
- Streaming consumer  

**Explain:**
- Why minimal base images matter  
- How configuration should be injected via environment variables  
- How secrets would be handled in production  

---

## Question 8: Kubernetes Deployment

### Task
Deploy the streaming consumer to Kubernetes (kind or minikube).

### Requirements
- Deployment with multiple replicas  
- Resource requests and limits  
- Consumer runs as part of a Kafka consumer group  

**Explain:**
- How Kafka consumer groups enable parallelism  
- Why having more consumers than partitions causes idle pods  
- How you would autoscale consumers based on lag  

---

## Question 9: Failure Scenarios

### Task
Demonstrate and explain the system’s behavior when:
- A consumer pod is killed  
- PostgreSQL becomes unavailable  
- Kafka is restarted  

For each case, explain:
- Risk of data loss or duplication  
- Recovery behavior  
- Observability gaps and mitigations  

---

# Part 5 — CI/CD & Operational Readiness

## Question 10: Continuous Integration

### Task
Implement a CI pipeline that:
- Runs unit tests  
- Runs linting/static checks  
- Builds Docker images  

**Explain:**
- Why CI should fail fast  
- What belongs in CI vs what does not  
- The difference between CI and CD  

---

## Question 11: Local CD Simulation

### Task
Simulate a CD flow locally:
- Code change  
- Image rebuild  
- Kubernetes rolling update  

**Explain:**
- Zero-downtime deployment strategy  
- Rollback mechanics  
- Versioning and image tagging strategy  

---

# Part 6 — Observability & Production Thinking

## Question 12: Monitoring and Alerting

### Task
Define:
- Key metrics for Kafka (lag, throughput)  
- Application metrics (processing latency, error rate)  
- Database metrics (write latency, connection saturation)  

**Explain:**
- Alert thresholds  
- Example incidents  
- Impact of lag, partial data, or incorrect aggregation on traders  

---

# Submission Expectations

Your submission should include:
- A Git repository  
- Clear README with:
  - Local setup instructions  
  - Architecture and design explanations  
  - Trade-offs and assumptions  
- Clean commit history  

---

# Evaluation Criteria

You will be evaluated on:
- Correctness and robustness  
- Streaming and system engineering fundamentals  
- Production awareness  
- Code quality and clarity of communication  
- Ability to reason about trade-offs  





---
# Source B

**1. System Design: Real-Time Trading Platform**

**Prompt:**
Architect a robust system that ingests real-time market prices and weather data, calculates live volatility metrics, and displays them to traders with sub-second latency. Historical data must be preserved for backtesting.

**Senior Engineer Solution: Lambda Architecture**

The system is divided into two paths: a hot path for speed and live trading, and a cold path for accuracy and historical analysis.

**A. Ingestion Layer (Decoupling)**

* **Component:** Python producers running as Kubernetes pods
* **Function:** These producers connect to external APIs (such as EPEX and Nord Pool), normalize incoming data to a strict schema using Avro or Protobuf, and publish it to Kafka.
* **Key Insight:** Data is never written directly from an API to a database. If a database is unavailable, market ticks must not be lost. Kafka serves as a durable, persistent buffer.

**B. Message Bus (Kafka)**

* **Configuration:** `acks=all`, requiring all replicas to acknowledge a message
* **Rationale:** In trading systems, durability is more important than throughput. Price updates cannot be sent on a fire-and-forget basis.

**C. Stream Processing (Business Logic)**

* **Component:** Python consumers or Apache Flink
* **Logic:** The processor calculates rolling volatility metrics or VWAP (Volume Weighted Average Price).
* **State Management:** Redis is used to store sliding-window state, such as the last 15 minutes of prices, avoiding repeated database queries.

**D. Storage Strategy**

* **Hot Storage (StarRocks):** Aggregated metrics are written here to power trader dashboards. StarRocks is optimized for sub-second OLAP queries.
* **Cold Storage (S3 Data Lake):** Kafka Connect sinks raw event logs to S3 in Parquet format, enabling quantitative analysts to backtest trading strategies.

---

**2. Streaming and Robustness**

**Prompt:**
How do you handle malformed messages that crash consumers, and how do you prevent duplicate trade processing?

**A. Failure Handling with a Dead Letter Queue (DLQ)**
A malformed message can cause a consumer to crash repeatedly, blocking the pipeline.

* **Strategy:** Wrap message processing logic in a try/except block.
* **Workflow:**

  * Catch the specific parsing exception.
  * Publish the invalid payload to a dedicated Kafka topic (for example, `market-data-dlq`).
  * Manually commit the offset so the consumer can continue processing subsequent messages.
  * Trigger an alert (such as PagerDuty) so developers can inspect the DLQ.

**B. Idempotency and Exactly-Once Semantics**
Network retries can result in duplicate message delivery.

* **Strategy:** Assign a unique `event_id` to every trade at the source.
* **Guardrail:** Enforce idempotency at the database level using an upsert or ignore pattern.

Example:

```
INSERT INTO trades (id, price, volume)
VALUES (...)
ON CONFLICT (id) DO NOTHING;
```

This guarantees that even if Kafka delivers the same message twice, downstream PnL calculations remain correct.

---

**3. Database Architecture: OLTP vs. OLAP**

**Prompt:**
A dashboard query aggregating 500 million rows takes 45 seconds, but traders require results in under one second.

**Solution: Use an OLAP Database (StarRocks)**
PostgreSQL is a row-oriented OLTP database. It excels at transactional safety but performs poorly on large-scale aggregations.

**Why StarRocks:**
StarRocks uses an aggregate key model. During ingestion, it pre-computes aggregates such as `SUM(volume)`.

**How It Works:**
Instead of scanning hundreds of millions of rows at query time, StarRocks reads pre-aggregated results.

**Outcome:**
Query latency drops from 45 seconds to under 50 milliseconds.

**Fallback:**
If PostgreSQL is mandatory, the mitigation strategy is time partitioning combined with materialized views.

---

**4. Python Data Engineering: Time-Series Processing**

**Prompt:**
Clean a time-series dataset of energy consumption with missing values and duplicates, then resample it to hourly totals.

**Production-Grade Approach:**

* Use forward-fill for prices, which behave like step functions.
* Use interpolation for consumption data, which represents a continuous physical process.

```python
import pandas as pd
import numpy as np

def process_energy_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and aggregates raw energy consumption data.
    """
    # 1. Deduplication
    # Later timestamps are treated as corrections.
    df = (
        df.sort_values("timestamp")
          .drop_duplicates(subset=["timestamp"], keep="last")
    )

    # 2. Indexing
    df = df.set_index("timestamp").sort_index()

    # 3. Handling Missing Data
    # Time-based interpolation for physical flow data (MWh).
    df["consumption"] = df["consumption"].interpolate(
        method="time",
        limit_direction="both"
    )

    # 4. Resampling
    # Consumption is summed; prices would use mean or VWAP.
    hourly_df = df.resample("1h").agg({"consumption": "sum"})

    # 5. Validation
    if (hourly_df["consumption"] < 0).any():
        raise ValueError("Critical data error: negative consumption detected.")

    return hourly_df
```

---

**5. CI/CD and Kubernetes: DevOps and Security**

**Prompt:**
Design a deployment pipeline that prevents faulty code from crashing a trading platform.

**A. CI/CD Pipeline**

**Continuous Integration:**

* **Linting and typing:** Use `ruff` and `mypy` to catch errors early.
* **Security scanning:** Scan Docker images with Trivy to detect known CVEs before deployment.

**Continuous Deployment with Canary Releases:**

* Deploy the new version to 10 percent of pods.
* Monitor error rates for five minutes.
* Automatically roll back to the previous stable version if error rates increase.

**B. Kubernetes Resource Management**

**Problem:**
Consumer pods are crashing with `OOMKilled` errors.

**Solutions:**

* **Immediate:** Increase `resources.limits.memory` and set requests close to limits to achieve guaranteed QoS.
* **Long-Term:** Configure Horizontal Pod Autoscaling based on Kafka consumer lag. If backlog grows, Kubernetes automatically scales out consumers to drain the queue.
