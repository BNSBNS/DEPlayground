# Streaming Semantics

## Question 2: Delivery Guarantees and Idempotency

---

## Table of Contents

1. [Semantics vs Schematics](#1-semantics-vs-schematics)
2. [Delivery Guarantee Strategies](#2-delivery-guarantee-strategies)
3. [Our Implementation](#3-our-implementation-at-least-once--idempotency)
4. [Database Write Patterns](#4-database-write-patterns)
5. [CAP Theorem and ACID Properties](#5-cap-theorem-and-acid-properties)
6. [Streaming Semantics Implementation Details](#6-streaming-semantics-implementation-details)
7. [Kafka Offset Management](#7-kafka-offset-management)

---

## 1. Semantics vs Schematics

| Term | Definition | Example |
|------|------------|---------|
| **Semantics** | The *meaning/behavior* of operations | "At-least-once" = messages delivered 1+ times |
| **Schematics** | The *structure/diagram* of a system | Architecture diagrams, data flow charts |

We use **"semantics"** because we describe *behavioral guarantees*, not structural diagrams.

---

## 2. Delivery Guarantee Strategies

### Comparison Table

| Strategy | Data Loss | Duplicates | Latency | Complexity | Use Case |
|----------|-----------|------------|---------|------------|----------|
| **At-Most-Once** | Possible | None | Lowest | Simple | Logs, metrics |
| **At-Least-Once** | None | Possible | Medium | Medium | Analytics (with idempotency) |
| **Exactly-Once** | None | None | Highest | High | Financial transactions |

---

### At-Most-Once

**Flow:** Commit → Process (if crash, message lost)

```python
# AT-MOST-ONCE: Risky - data loss possible
for message in consumer:
    consumer.commit()          # Commit BEFORE processing
    process(message)           # If this fails, message LOST
```

**Pros:** Simple, lowest latency, no dedup needed
**Cons:** Data loss on failure
**Use Cases:** Click tracking, application logs, real-time metrics

---

### At-Least-Once (This Project)

**Flow:** Process → Write → Commit (if crash before commit, replay)

```python
# AT-LEAST-ONCE: Safe - duplicates handled by upsert
for message in consumer:
    result = process(message)
    db.upsert(result)          # Idempotent write
    consumer.commit()          # Commit AFTER success
```

**Pros:** No data loss, works with any downstream
**Cons:** Requires idempotent handling
**Use Cases:** Event pipelines, analytics, this project

---

### Exactly-Once

**Flow:** Transactional (process + commit atomic)

```python
# EXACTLY-ONCE: Transactional processing
producer.begin_transaction()
try:
    result = process(message)
    producer.send(output_topic, result)
    producer.send_offsets_to_transaction({partition: offset+1}, group_id)
    producer.commit_transaction()
except:
    producer.abort_transaction()
```

**Pros:** No loss, no duplicates
**Cons:** Higher latency, requires transactional support
**Use Cases:** Banking, inventory, financial ledgers

---

### Decision Flow

```
Is data loss acceptable?
    │
    ├─ YES → At-Most-Once
    │
    └─ NO → Can downstream handle duplicates?
              │
              ├─ YES → At-Least-Once + Idempotency  ← THIS PROJECT
              │
              └─ NO → Exactly-Once (transactions)
```

---

## 3. Our Implementation: At-Least-Once + Idempotency

### Pattern

```python
# src/consumer/kafka_consumer.py (simplified)
for message in consumer:
    try:
        trade = parse_trade_event(message)        # 1. Parse
        aggregates = aggregator.add_trade(trade)  # 2. Aggregate
        db_writer.upsert(aggregates)              # 3. Idempotent write
        consumer.commit()                          # 4. Commit after success
    except ValidationError as e:
        dlq_handler.send(message, e)              # 5. Bad msg → DLQ
        consumer.commit()                          # 6. Move past bad msg
```

### Key Principles

1. Commit offset **only after** successful DB write
2. Upsert handles duplicates gracefully
3. DLQ prevents pipeline blockage

---

## 4. Database Write Patterns

### Comparison Table

| Pattern | Duplicates | Speed | Use Case |
|---------|------------|-------|----------|
| **INSERT only** | Fails | Fast | Unique events (UUID PK) |
| **UPSERT** (this project) | Overwrites | Medium | Aggregates, latest state |
| **INSERT IGNORE** | Skips silently | Fast | Append-only logs |
| **Conditional INSERT** | App checks first | Slow | Custom logic |

### Upsert SQL (Our Choice)

```sql
INSERT INTO trade_aggregates (symbol, window_start, vwap, total_volume, ...)
VALUES (%(symbol)s, %(window_start)s, %(vwap)s, ...)
ON CONFLICT (symbol, window_start) DO UPDATE SET
    vwap = EXCLUDED.vwap,
    total_volume = EXCLUDED.total_volume,
    updated_at = NOW();
```

**Why it works:** Composite PK `(symbol, window_start)` = natural business key. Same inputs → same result.

---

## 5. CAP Theorem and ACID Properties

### CAP Theorem

| Property | Definition | Our System |
|----------|------------|------------|
| **C**onsistency | All nodes see same data | PostgreSQL: strong |
| **A**vailability | Always responds | Kafka: highly available |
| **P**artition Tolerance | Works during network splits | Required |

**Trade-off:** You can only guarantee 2 of 3 in distributed systems.

- **PostgreSQL:** CP (consistent, may reject writes if unavailable)
- **Kafka:** AP (available, eventually consistent across replicas)

### ACID Properties

| Property | Definition | Implementation |
|----------|------------|----------------|
| **A**tomicity | All or nothing | Batch writes in single transaction |
| **C**onsistency | Valid state transitions | Constraints, triggers |
| **I**solation | No interference | PostgreSQL default isolation |
| **D**urability | Survives crashes | WAL, Kafka `acks=all` |

### BASE (Kafka/NoSQL) vs ACID (PostgreSQL)

| ACID | BASE |
|------|------|
| Atomicity | **B**asically **A**vailable |
| Consistency | **S**oft state |
| Isolation | **E**ventual consistency |
| Durability | |

**Our hybrid:** Kafka (BASE) → PostgreSQL (ACID)

---

## 6. Streaming Semantics Implementation Details

### Implementation Comparison

| Aspect | At-Most-Once | At-Least-Once | Exactly-Once |
|--------|--------------|---------------|--------------|
| Offset commit | Before processing | After processing | Transactional |
| Failure handling | Skip | Retry/DLQ | Abort transaction |
| Downstream need | None | Idempotent writes | Transactional support |

### Code Implementations

#### At-Most-Once (Reference)
```python
class AtMostOnceConsumer:
    def run(self):
        for msg in self.consumer:
            self.consumer.commit()      # Commit first
            self._process(msg)          # Loss if fails here
```

#### At-Least-Once (This Project)
```python
class AtLeastOnceConsumer:
    def run(self):
        for msg in self.consumer:
            try:
                result = self._process(msg)
                self.db.upsert(result)  # Idempotent
                self.consumer.commit()  # After success
            except ValidationError as e:
                self.dlq.send(msg, e)
                self.consumer.commit()  # Move forward
            except DatabaseError:
                raise  # Don't commit, retry on restart
```

#### Exactly-Once (Reference)
```python
class ExactlyOnceConsumer:
    def run(self):
        self.producer.init_transactions()
        for msg in self.consumer:
            self.producer.begin_transaction()
            try:
                result = self._process(msg)
                self.producer.send("output", result)
                self.producer.send_offsets_to_transaction(
                    {msg.partition: msg.offset + 1}, self.group_id
                )
                self.producer.commit_transaction()
            except:
                self.producer.abort_transaction()
```

---

## 7. Kafka Offset Management

### What is an Offset?

```
Partition 0:  [msg0] [msg1] [msg2] [msg3] [msg4]
               ↑                    ↑
          offset=0             offset=3 (committed)
```

### Commit Strategies

| Strategy | When | Risk | Use |
|----------|------|------|-----|
| Auto-commit | Periodic | Data loss | Dev only |
| Manual (this project) | After success | Duplicates (handled) | Production |

### Failure Recovery

| Scenario | What Happens | Recovery |
|----------|--------------|----------|
| Crash before DB write | Offset not committed | Replay, process normally |
| Crash after write, before commit | Offset not committed | Replay, upsert handles dup |
| Crash after commit | Normal | Resume next offset |
| DB unavailable | Write fails | Retry until recovery |

---

## Summary

| Component | Semantics | Implementation |
|-----------|-----------|----------------|
| Producer → Kafka | Exactly-once | `acks=all`, `enable.idempotence=true` |
| Kafka → Consumer | At-least-once | Manual commit after processing |
| Consumer → DB | Idempotent | `INSERT ... ON CONFLICT DO UPDATE` |
| **End-to-End** | **Exactly-once effect** | Combination of above |
