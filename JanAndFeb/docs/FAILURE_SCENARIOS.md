# Failure Scenarios

## Question 11: System Behavior Under Failure Conditions

This document describes the system's behavior when various failure scenarios occur, including data loss risks, recovery behavior, and impact on traders.

---

## Scenario 1: Consumer Pod Killed Mid-Processing

### Situation
A consumer pod is terminated (OOMKilled, node failure, or manual deletion) while processing a message.

### System Behavior

| Phase | State Before Kill | Recovery Behavior |
|-------|-------------------|-------------------|
| Parsing message | Offset not committed | Replay from last committed offset |
| Computing aggregates | Offset not committed | Replay, recompute aggregates |
| Writing to DB | Offset not committed | Replay, upsert handles duplicate |
| After DB write, before commit | Offset not committed | Replay, upsert handles duplicate |
| After commit | Offset committed | Resume from next message |

### Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Data loss | **None** | Uncommitted offsets trigger replay |
| Data duplication | **None** | Idempotent upserts |
| Processing delay | **Low** | Other consumers continue; rebalance completes in ~30s |

### Recovery Timeline

```
T+0s     Pod killed
T+10s    Kafka consumer group rebalance triggered
T+30s    Partitions reassigned to surviving consumers
T+45s    Processing resumes from last committed offset
T+60s    Caught up to current position
```

### Observability Gaps

- **Gap:** No immediate alert when single consumer dies
- **Mitigation:** Monitor consumer group member count; alert if below minimum

### Trader Impact

| Impact | Duration | Visibility |
|--------|----------|------------|
| Dashboard data stale | 30-60 seconds | Minimal |
| No data loss | N/A | None visible |

---

## Scenario 2: PostgreSQL Unavailable for 5 Minutes

### Situation
Database becomes unavailable (network partition, maintenance, crash).

### System Behavior

```
Consumer attempts DB write
       │
       ▼
Write fails (connection error)
       │
       ▼
Retry with exponential backoff (1s, 2s, 4s, 8s, 16s, 32s)
       │
       ▼
After max retries, consumer blocks
       │
       ▼
No offset committed → consumer lag increases
       │
       ▼
Kafka continues buffering messages
       │
       ▼
DB recovers → writes resume → catch up
```

### Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Data loss | **None** | Messages buffered in Kafka |
| Data duplication | **None** | Idempotent upserts on recovery |
| Consumer lag | **High** | Lag grows during outage |

### Recovery Timeline

```
T+0m     PostgreSQL becomes unavailable
T+0m     Consumer starts retry loop
T+1m     Consumer lag: ~600 messages (at 10/sec)
T+5m     Consumer lag: ~3000 messages
T+5m     PostgreSQL recovers
T+5m10s  First successful write
T+6m     Processing backlog at full speed
T+7m     Caught up (depends on consumer count)
```

### Observability

**Key Metrics to Monitor:**
- `db_write_errors` - Spikes immediately
- `kafka_consumer_lag` - Grows linearly during outage
- `db_connection_pool_available` - Drops to zero

**Alerts:**
- DB write error rate > 0 for 30 seconds
- Consumer lag > 5000 for 2 minutes

### Trader Impact

| Impact | Duration | Severity |
|--------|----------|----------|
| Dashboard shows stale data | 5-7 minutes | Medium |
| Historical data complete | After recovery | Low |
| No data loss | N/A | None |

---

## Scenario 3: Kafka Broker Restarted

### Situation
A Kafka broker is restarted (maintenance, upgrade, crash).

### System Behavior (3-broker cluster)

```
Single broker restart:
- Partition leaders on that broker become unavailable
- Controller elects new leaders from ISR (in-sync replicas)
- Producers/consumers reconnect to new leaders
- ~30 second interruption

Full cluster restart:
- All brokers unavailable
- Producers queue messages locally (buffer)
- Consumers block on poll
- Recovery when cluster comes back
```

### Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Data loss | **None** | Replication factor = 3, acks=all |
| Message duplication | **Low** | Producer idempotence enabled |
| Ordering violation | **None** | Maintained within partition |

### Recovery Timeline (Single Broker)

```
T+0s     Broker shutdown initiated
T+5s     Leader election for affected partitions
T+10s    New leaders ready
T+15s    Producers discover new leaders (metadata refresh)
T+30s    Normal operation resumed
```

### Observability

**Key Metrics:**
- `kafka_under_replicated_partitions` - Spikes during restart
- `kafka_offline_partitions` - Non-zero during election
- `kafka_request_latency` - May increase

### Trader Impact

| Impact | Duration | Severity |
|--------|----------|----------|
| Slight latency increase | 10-30 seconds | Low |
| No visible data gap | N/A | None |

---

## Scenario 4: Network Partition Between Consumer and Kafka

### Situation
Network issue prevents consumer from reaching Kafka brokers.

### System Behavior

```
Consumer poll timeout (1 second)
       │
       ▼
Retry poll (continues until session.timeout.ms = 45s)
       │
       ▼
Session timeout → consumer removed from group
       │
       ▼
Kafka triggers rebalance
       │
       ▼
Other consumers take over partitions
       │
       ▼
Network recovers → consumer rejoins → new rebalance
```

### Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Data loss | **None** | Other consumers process messages |
| Data duplication | **Low** | Possible during rebalance |
| Processing interruption | **Medium** | 45-60s per rebalance |

### Recovery Timeline

```
T+0s      Network partition begins
T+15s     Consumer heartbeat fails
T+45s     Session timeout, consumer removed
T+60s     Rebalance complete, others processing
T+120s    Network recovers
T+135s    Consumer rejoins, new rebalance
T+165s    Normal operation
```

### Observability

**Key Metrics:**
- `kafka_consumer_heartbeat_failures` - Increases
- `kafka_consumer_rebalances` - Count increases
- `kafka_consumer_lag` - May spike during rebalance

### Trader Impact

| Impact | Duration | Severity |
|--------|----------|----------|
| Potential data delay | 60-90 seconds | Low |
| No data loss | N/A | None |

---

## Summary: Failure Mode Comparison

| Scenario | Data Loss Risk | Duplication Risk | Recovery Time | Trader Impact |
|----------|----------------|------------------|---------------|---------------|
| Consumer pod killed | None | None | 30-60s | Minimal |
| PostgreSQL down 5min | None | None | 5-7min | Stale dashboard |
| Kafka broker restart | None | Low | 10-30s | Minimal |
| Network partition | None | Low | 60-90s | Minimal |

---

## Observability Gaps and Mitigations

| Gap | Mitigation |
|-----|------------|
| No alert for single consumer failure | Monitor consumer group size |
| DB outage not immediately visible | Alert on write error rate |
| Rebalance frequency not tracked | Monitor rebalance count |
| End-to-end latency not measured | Add timestamp at producer, measure at DB |

---

## Runbook Summary

### Consumer Pod Killed
1. Check consumer group status: `kafka-consumer-groups --describe`
2. Verify rebalance completed
3. Check lag is decreasing
4. No action needed if other consumers healthy

### PostgreSQL Unavailable
1. Check PostgreSQL status and logs
2. Verify connection from consumer pods
3. Monitor consumer lag
4. After recovery, verify catch-up progress
5. Check for any data quality alerts

### Kafka Broker Restart
1. Check cluster health: `kafka-broker-api-versions`
2. Verify under-replicated partitions = 0
3. Check producer/consumer metrics
4. No action needed if ISR maintained

### Network Partition
1. Check network connectivity from consumer pods
2. Verify consumer group membership
3. Monitor for excessive rebalances
4. Investigate network infrastructure if recurring
