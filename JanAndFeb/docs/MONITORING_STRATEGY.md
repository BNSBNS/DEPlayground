# Monitoring and Alerting Strategy

## Question 14: Comprehensive Platform Monitoring

This document defines the monitoring strategy for the Energy Trading Platform, including key metrics, alert thresholds, and operational runbooks.

---

## Key Metrics

### Kafka Metrics

| Metric | Description | Alert Threshold | Rationale |
|--------|-------------|-----------------|-----------|
| `kafka_consumer_lag` | Messages behind current offset | > 10,000 for 5 min | Data freshness SLO |
| `kafka_consumer_lag_rate` | Rate of lag change | Increasing for 10 min | Falling behind |
| `kafka_messages_per_second` | Throughput | < 1 for 5 min (during market hours) | Producer issue |
| `kafka_broker_disk_usage_pct` | Broker disk utilization | > 80% | Capacity planning |
| `kafka_under_replicated_partitions` | Partitions below RF | > 0 for 5 min | Durability risk |
| `kafka_offline_partitions` | Unavailable partitions | > 0 | Data unavailable |
| `kafka_consumer_rebalances` | Rebalance count | > 3 in 15 min | Instability |

### Application Metrics

| Metric | Description | Alert Threshold | Rationale |
|--------|-------------|-----------------|-----------|
| `trade_processing_latency_p50` | Median processing time | > 100ms | Performance baseline |
| `trade_processing_latency_p95` | 95th percentile | > 250ms | SLO warning |
| `trade_processing_latency_p99` | 99th percentile | > 500ms | SLO breach |
| `messages_processed_per_minute` | Throughput | < 100 (market hours) | Processing issue |
| `error_rate` | Errors / total messages | > 1% | Data quality issue |
| `dlq_message_count` | Messages in DLQ | > 0 | Immediate investigation |
| `active_windows` | In-memory window count | > 1000 | Memory pressure |
| `aggregates_written_per_minute` | DB write rate | < 5 (market hours) | Processing issue |

### Database Metrics

| Metric | Description | Alert Threshold | Rationale |
|--------|-------------|-----------------|-----------|
| `db_write_latency_p99` | 99th percentile write time | > 100ms | Performance degradation |
| `db_connection_pool_usage_pct` | Pool utilization | > 80% | Capacity limit |
| `db_connection_errors` | Failed connection attempts | > 0 for 1 min | Connectivity issue |
| `db_query_duration_p99` | Slow query detection | > 1s | Query optimization needed |
| `db_replication_lag` | Replica lag (if applicable) | > 1 min | Replica staleness |
| `db_disk_usage_pct` | Storage utilization | > 75% | Capacity planning |
| `db_active_connections` | Current connections | > 80% of max | Connection exhaustion |

---

## Alert Configuration

### Critical Alerts (PagerDuty - Immediate Response)

```yaml
- alert: KafkaConsumerLagCritical
  expr: kafka_consumer_lag{topic="trades"} > 50000
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Critical consumer lag on trades topic"
    runbook: "docs/runbooks/high-consumer-lag.md"

- alert: DatabaseUnavailable
  expr: db_connection_errors > 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Cannot connect to PostgreSQL"
    runbook: "docs/runbooks/database-unavailable.md"

- alert: DLQMessagesDetected
  expr: dlq_message_count > 0
  for: 0m
  labels:
    severity: critical
  annotations:
    summary: "Messages sent to Dead Letter Queue"
    runbook: "docs/runbooks/dlq-investigation.md"
```

### Warning Alerts (Slack - Business Hours Response)

```yaml
- alert: KafkaConsumerLagWarning
  expr: kafka_consumer_lag{topic="trades"} > 10000
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Consumer lag elevated on trades topic"

- alert: ProcessingLatencyHigh
  expr: trade_processing_latency_p99 > 500
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Processing latency exceeds SLO"

- alert: DatabaseWriteLatencyHigh
  expr: db_write_latency_p99 > 100
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Database write latency elevated"
```

---

## Grafana Dashboard Layout

### Overview Dashboard (On-Call Engineers)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ENERGY TRADING PLATFORM                         │
│                         System Health Overview                          │
├────────────────────────┬────────────────────────┬──────────────────────┤
│                        │                        │                      │
│    SYSTEM STATUS       │   CONSUMER LAG         │   DLQ COUNT          │
│    [GREEN/RED]         │   [GRAPH: 24h]         │   [SINGLE STAT]      │
│                        │                        │                      │
├────────────────────────┴────────────────────────┴──────────────────────┤
│                                                                         │
│                    MESSAGE THROUGHPUT (messages/sec)                   │
│                    [TIME SERIES GRAPH: Producer vs Consumer]            │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                    PROCESSING LATENCY (P50, P95, P99)                  │
│                    [TIME SERIES GRAPH]                                  │
│                                                                         │
├────────────────────────┬────────────────────────┬──────────────────────┤
│                        │                        │                      │
│    DB WRITE LATENCY    │   DB CONNECTIONS       │   ERROR RATE         │
│    [GAUGE: P99]        │   [GAUGE: % used]      │   [SINGLE STAT]      │
│                        │                        │                      │
└────────────────────────┴────────────────────────┴──────────────────────┘
```

### Kafka Deep Dive Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           KAFKA METRICS                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│    CONSUMER LAG BY PARTITION                                           │
│    [STACKED TIME SERIES]                                               │
│                                                                         │
├────────────────────────┬────────────────────────────────────────────────┤
│                        │                                                │
│    MESSAGES IN/SEC     │    BYTES IN/SEC BY TOPIC                      │
│    [TIME SERIES]       │    [TIME SERIES]                              │
│                        │                                                │
├────────────────────────┼────────────────────────────────────────────────┤
│                        │                                                │
│    BROKER DISK USAGE   │    UNDER-REPLICATED PARTITIONS                │
│    [BAR CHART]         │    [TIME SERIES]                              │
│                        │                                                │
└────────────────────────┴────────────────────────────────────────────────┘
```

---

## Runbook: High Consumer Lag

### Symptoms
- `kafka_consumer_lag > 10,000` alert triggered
- Dashboard shows stale data

### Investigation Steps

1. **Check consumer health**
   ```bash
   kubectl get pods -n trading -l app=trade-consumer
   kubectl logs -n trading -l app=trade-consumer --tail=100
   ```

2. **Check consumer group status**
   ```bash
   kafka-consumer-groups --bootstrap-server kafka:9092 \
     --describe --group trade-aggregator
   ```

3. **Check for processing errors**
   ```bash
   kubectl logs -n trading -l app=trade-consumer | grep -i error
   ```

4. **Check database connectivity**
   ```bash
   kubectl exec -n trading deploy/trade-consumer -- \
     python -c "from src.consumer.db_writer import DatabaseWriter; print(DatabaseWriter().check_connection())"
   ```

### Resolution Actions

| Cause | Action |
|-------|--------|
| Consumer pod crashed | Check logs, restart if needed |
| Database slow | Investigate DB metrics, add indexes |
| Burst traffic | Scale consumers: `kubectl scale deploy/trade-consumer --replicas=4` |
| Code bug | Check error logs, rollback if needed |

---

## Runbook: DLQ Messages Detected

### Symptoms
- `dlq_message_count > 0` alert triggered
- `trades-dlq` topic has messages

### Investigation Steps

1. **Check DLQ message content**
   ```bash
   kafka-console-consumer --bootstrap-server kafka:9092 \
     --topic trades-dlq --from-beginning --max-messages 5
   ```

2. **Identify error pattern**
   ```sql
   SELECT error_type, COUNT(*)
   FROM dlq_messages
   WHERE created_at > NOW() - INTERVAL '1 hour'
   GROUP BY error_type;
   ```

3. **Check producer data quality**
   - Verify producer logs for malformed data
   - Check external API responses

### Resolution Actions

| Cause | Action |
|-------|--------|
| Schema change | Update consumer model, replay DLQ |
| Bad data from source | Contact data provider, filter at producer |
| Bug in validation | Fix validation, replay DLQ |

---

## Service Level Objectives (SLOs)

### Data Freshness SLO

**Objective:** 99% of trades reflected in dashboard within 5 seconds of event time

**Measurement:**
```
freshness = event_timestamp - dashboard_update_timestamp
SLO_met = (freshness < 5s) for 99% of trades
```

**Error Budget:** 7.2 hours/month (30 days × 24 hours × 1%)

### Availability SLO

**Objective:** 99.9% uptime for data pipeline

**Measurement:**
```
availability = (successful_writes / total_writes) × 100
SLO_met = availability >= 99.9%
```

**Error Budget:** 43.2 minutes/month

### Data Accuracy SLO

**Objective:** 99.99% of aggregates are correct

**Measurement:**
- Cross-check VWAP calculation with independent system
- Verify trade counts match source

---

## Impact on Traders

### Lag Impact

| Lag (messages) | Delay (seconds) | Trader Impact |
|----------------|-----------------|---------------|
| 0-100 | < 10s | None noticeable |
| 100-1,000 | 10-100s | Slightly stale data |
| 1,000-10,000 | 1-15 min | Missing recent moves |
| > 10,000 | > 15 min | **Critical** - trading decisions affected |

### Data Quality Impact

| Issue | Trader Impact | Severity |
|-------|---------------|----------|
| Missing trades | Incorrect VWAP | High |
| Duplicate trades | Inflated volume | High |
| Late aggregates | Delayed signals | Medium |
| Incorrect prices | Wrong P&L display | Critical |
