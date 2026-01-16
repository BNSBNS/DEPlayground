# Streaming Semantics

## Question 2: Delivery Guarantees and Idempotency

This document explains the streaming semantics used in the Energy Trading Platform, including delivery guarantees, offset management, and idempotency patterns.

---

## Delivery Guarantee Semantics

### At-Most-Once

**Definition:** Messages are delivered zero or one time. Some messages may be lost.

**How it works:**
1. Consumer receives message
2. Consumer commits offset immediately
3. Consumer processes message
4. If processing fails, message is lost (offset already committed)

**Use cases:** Metrics, logs where some loss is acceptable

**Not suitable for:** Trading systems (cannot lose trade data)

### At-Least-Once

**Definition:** Messages are delivered one or more times. No messages are lost, but duplicates may occur.

**How it works:**
1. Consumer receives message
2. Consumer processes message
3. Consumer writes to database
4. Consumer commits offset
5. If step 4 fails after step 3, message will be reprocessed (duplicate)

**Use cases:** When combined with idempotent processing

**This is what we implement.**

### Exactly-Once

**Definition:** Messages are delivered exactly one time. No loss, no duplicates.

**How it works (true exactly-once):**
- Requires atomic transactions spanning Kafka and downstream system
- Kafka Transactions + Transactional Outbox pattern

**Trade-offs:**
- Higher latency (two-phase commit)
- More complex implementation
- Not all downstream systems support it

---

## Our Implementation: At-Least-Once + Idempotency

We achieve an **exactly-once effect** by combining at-least-once delivery with idempotent writes.

### The Pattern

```python
for message in consumer:
    try:
        # 1. Parse and validate
        trade = parse_trade_event(message)

        # 2. Process (window aggregation)
        aggregates = aggregator.add_trade(trade)

        # 3. Write to database (IDEMPOTENT)
        for agg in aggregates:
            db_writer.upsert(agg)  # ON CONFLICT DO UPDATE

        # 4. Commit offset (ONLY after successful write)
        consumer.commit()

    except ValidationError as e:
        # 5. Send to DLQ and commit (move past bad message)
        dlq_handler.send(message, error=e)
        consumer.commit()
```

### Key Principles

1. **Commit offset only after successful database write**
2. **Database upsert handles duplicates gracefully**
3. **DLQ prevents bad messages from blocking pipeline**

---

## Kafka Offset Management

### What is an Offset?

An offset is a unique identifier for each message within a Kafka partition. It represents the position of a message in the partition log.

```
Partition 0:  [msg0] [msg1] [msg2] [msg3] [msg4] ...
              offset  offset offset offset offset
                0      1      2      3      4
```

### Consumer Offset States

| State | Description |
|-------|-------------|
| **Current Position** | Next message to be consumed |
| **Committed Offset** | Last offset successfully processed (stored in Kafka) |

### Offset Commit Strategies

| Strategy | Description | Risk |
|----------|-------------|------|
| Auto-commit (periodic) | Kafka commits offsets periodically | Data loss if crash before processing |
| Auto-commit (on poll) | Commit before each poll | Data loss if crash during processing |
| **Manual commit** | Application commits after processing | Duplicates if crash after processing, before commit |

**We use manual commit** for maximum control and safety.

---

## Database Upsert Pattern

### The Problem

With at-least-once delivery, the same trade may be processed multiple times:

```
Trade T1 → Process → Write to DB → [CRASH] → Restart → Replay T1 → Process again
```

Without protection, this creates duplicate records.

### The Solution: Idempotent Upsert

```sql
INSERT INTO trade_aggregates (
    symbol, window_start, vwap, total_volume, trade_count, max_price, min_price
)
VALUES (%(symbol)s, %(window_start)s, %(vwap)s, ...)
ON CONFLICT (symbol, window_start) DO UPDATE SET
    vwap = EXCLUDED.vwap,
    total_volume = EXCLUDED.total_volume,
    trade_count = EXCLUDED.trade_count,
    max_price = EXCLUDED.max_price,
    min_price = EXCLUDED.min_price,
    updated_at = NOW();
```

### How It Works

| Scenario | Behavior |
|----------|----------|
| New window | INSERT new row |
| Replay (same data) | UPDATE with identical values (no effect) |
| Late event | UPDATE with correct aggregated values |

**Key insight:** The composite primary key `(symbol, window_start)` makes writes naturally idempotent.

---

## Interaction: Offsets, Commits, and Upserts

### Normal Processing Flow

```
1. Poll message (offset=42) from Kafka
2. Parse trade event
3. Add to window aggregator
4. If window complete:
   a. Compute VWAP, volume, etc.
   b. UPSERT to PostgreSQL
   c. Verify write success
5. Commit offset 42 to Kafka
6. Poll next message (offset=43)
```

### Failure Scenarios

| Scenario | What Happens | Recovery |
|----------|--------------|----------|
| Crash before DB write | Offset not committed | Replay from offset 42, process normally |
| Crash after DB write, before commit | Offset not committed | Replay from offset 42, upsert handles duplicate |
| Crash after commit | Normal operation | Resume from offset 43 |
| DB unavailable | Write fails, retry with backoff | Keep retrying until DB recovers |

---

## End-to-End Exactly-Once (Stretch Goal)

True exactly-once semantics require coordinating transactions across Kafka and the database.

### Transactional Outbox Pattern

```
┌─────────────────────────────────────────────────────────┐
│                    DATABASE TRANSACTION                 │
│                                                         │
│  1. Write trade aggregate to trade_aggregates table    │
│  2. Write offset to outbox table                       │
│  3. COMMIT (atomic)                                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   BACKGROUND PROCESS                    │
│                                                         │
│  1. Read uncommitted offsets from outbox               │
│  2. Commit offsets to Kafka                            │
│  3. Mark as committed in outbox                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Trade-offs

| Aspect | At-Least-Once + Idempotency | True Exactly-Once |
|--------|------------------------------|-------------------|
| **Complexity** | Simple | Complex |
| **Latency** | Lower | Higher (2PC) |
| **Dependencies** | Kafka + DB | Kafka + DB + Outbox |
| **Failure modes** | Well understood | More edge cases |
| **Correctness** | Equivalent for idempotent writes | Guaranteed |

**Our choice:** At-least-once + idempotency is sufficient for this use case because:
1. Aggregates are naturally idempotent (same inputs → same outputs)
2. Upsert pattern handles duplicates
3. Simpler to implement, operate, and debug

---

## Summary

| Component | Semantics | Implementation |
|-----------|-----------|----------------|
| **Producer → Kafka** | Exactly-once | `acks=all`, `enable.idempotence=true` |
| **Kafka → Consumer** | At-least-once | Manual offset commit after processing |
| **Consumer → Database** | Idempotent | `INSERT ... ON CONFLICT DO UPDATE` |
| **End-to-End Effect** | Exactly-once | Combination of above |
