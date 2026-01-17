# Kubernetes Autoscaling and High Availability

## Q1: How Autoscaling and HA Work + Validation

---

## Table of Contents

1. [How Autoscaling Works](#1-how-autoscaling-works)
2. [How High Availability Works](#2-how-high-availability-works)
3. [Configuration](#3-configuration)
4. [Validation Commands](#4-validation-commands)
5. [Recovery Testing](#5-recovery-testing)
6. [Monitoring Stack Setup](#6-monitoring-stack-setup)

---

## 1. How Autoscaling Works

### Horizontal Pod Autoscaler (HPA)

```
                     ┌─────────────────┐
                     │   HPA Controller │
                     └────────┬────────┘
                              │ monitors
                              ▼
┌───────────┐  scale up   ┌───────────┐
│ CPU > 70% │────────────▶│  +1 Pod   │
└───────────┘              └───────────┘
                              │
┌───────────┐  scale down  ┌───────────┐
│ CPU < 30% │────────────▶│  -1 Pod   │
└───────────┘              └───────────┘
```

### Key Configuration

```yaml
# k8s/consumer/deployment.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  scaleTargetRef:
    kind: Deployment
    name: trade-consumer
  minReplicas: 2        # Always at least 2 for HA
  maxReplicas: 6        # Max = Kafka partition count
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70  # Scale up when CPU > 70%
```

### Scaling Triggers

| Metric | Threshold | Action |
|--------|-----------|--------|
| CPU > 70% | 5 min sustained | Scale up |
| CPU < 30% | 5 min sustained | Scale down |
| Kafka lag > 1000 | Immediate | Scale up (if external metrics configured) |

### Why Max = Partition Count?

- Kafka: 6 partitions for `trades` topic
- Each partition = 1 consumer max
- More consumers than partitions = idle pods (waste)

---

## 2. How High Availability Works

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                    HIGH AVAILABILITY                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Consumer 1  │    │  Consumer 2  │    │  Consumer 3  │  │
│  │  Partitions  │    │  Partitions  │    │  (standby)   │  │
│  │    0, 1      │    │    2, 3      │    │              │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                   │           │
│         └─────────────┬─────┴───────────────────┘           │
│                       │                                      │
│              Kafka Consumer Group                            │
│              (automatic rebalance)                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### HA Mechanisms

| Mechanism | Config | Purpose |
|-----------|--------|---------|
| `replicas: 2` | Deployment | Always 2+ pods running |
| `PodDisruptionBudget` | `minAvailable: 1` | Prevent all pods down during updates |
| Consumer Group | Kafka | Auto-rebalance on pod failure |
| `terminationGracePeriodSeconds: 60` | Pod | Allow offset commit before shutdown |

### PodDisruptionBudget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: trade-consumer-pdb
spec:
  minAvailable: 1  # At least 1 pod must be running
  selector:
    matchLabels:
      app: trade-consumer
```

---

## 3. Configuration

### Enable External Metrics (Kafka Lag)

```yaml
# Uncomment in k8s/consumer/deployment.yaml
metrics:
  - type: External
    external:
      metric:
        name: kafka_consumergroup_lag
        selector:
          matchLabels:
            consumergroup: trade-aggregator
      target:
        type: AverageValue
        averageValue: "1000"  # Scale when lag > 1000
```

**Requires:** Prometheus Adapter + Kafka Exporter

---

## 4. Validation Commands

### Check HPA Status

```bash
# View HPA status and current metrics
kubectl get hpa -n trading

# Example output:
# NAME                 REFERENCE                   TARGETS   MINPODS   MAXPODS   REPLICAS
# trade-consumer-hpa   Deployment/trade-consumer   45%/70%   2         6         2

# Detailed HPA info
kubectl describe hpa trade-consumer-hpa -n trading
```

### Check Pod Distribution

```bash
# View pods and their nodes
kubectl get pods -n trading -o wide

# View consumer group membership
kubectl exec -n trading deploy/trade-consumer -- \
  kafka-consumer-groups --bootstrap-server kafka:9092 \
  --describe --group trade-aggregator
```

### Check PDB Status

```bash
# View PDB status
kubectl get pdb -n trading

# Example output:
# NAME                 MIN AVAILABLE   MAX UNAVAILABLE   ALLOWED DISRUPTIONS   AGE
# trade-consumer-pdb   1               N/A               1                     1h
```

### Verify Autoscaling

```bash
# Generate load and watch scaling
kubectl run stress --image=busybox --restart=Never -- \
  /bin/sh -c "while true; do wget -q -O- http://producer:8080; done"

# Watch HPA react
kubectl get hpa -n trading -w

# Clean up
kubectl delete pod stress
```

---

## 5. Recovery Testing

### Test 1: Kill Single Consumer Pod

```bash
# 1. Get current pods
kubectl get pods -n trading -l app=trade-consumer

# 2. Kill one pod
kubectl delete pod -n trading <pod-name>

# 3. Watch recovery (should take ~30-60 seconds)
kubectl get pods -n trading -l app=trade-consumer -w

# 4. Verify consumer group rebalanced
kubectl exec -n trading deploy/trade-consumer -- \
  kafka-consumer-groups --bootstrap-server kafka:9092 \
  --describe --group trade-aggregator

# Expected: New pod started, partitions rebalanced
```

### Test 2: Simulate DB Outage

```bash
# 1. Scale down PostgreSQL
kubectl scale deployment postgres -n trading --replicas=0

# 2. Watch consumer logs (should show retry attempts)
kubectl logs -n trading -l app=trade-consumer -f

# 3. Check consumer lag increasing
kubectl exec -n trading deploy/trade-consumer -- \
  kafka-consumer-groups --bootstrap-server kafka:9092 \
  --describe --group trade-aggregator

# 4. Restore PostgreSQL
kubectl scale deployment postgres -n trading --replicas=1

# 5. Watch catch-up (lag should decrease)
kubectl get hpa -n trading -w

# Expected: Lag increases during outage, then decreases after recovery
```

### Test 3: Rolling Update (Zero Downtime)

```bash
# 1. Update image
kubectl set image deployment/trade-consumer \
  consumer=energy-trading-platform/consumer:v2 -n trading

# 2. Watch rollout
kubectl rollout status deployment/trade-consumer -n trading

# 3. Verify PDB maintained availability
kubectl get pods -n trading -l app=trade-consumer -w

# Expected: Old pods terminate only after new pods are ready
```

### Test 4: Node Failure Simulation

```bash
# 1. Drain a node (simulates node failure)
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# 2. Watch pods reschedule
kubectl get pods -n trading -o wide -w

# 3. Verify HA maintained
kubectl get pods -n trading -l app=trade-consumer

# 4. Restore node
kubectl uncordon <node-name>

# Expected: Pods rescheduled to other nodes, no data loss
```

---

## 6. Monitoring Stack Setup

### Deploy Prometheus + Grafana

```bash
# 1. Apply monitoring stack
kubectl apply -f k8s/monitoring/

# 2. Wait for pods
kubectl get pods -n monitoring -w

# 3. Port-forward Grafana
kubectl port-forward svc/grafana 3000:3000 -n monitoring

# 4. Access Grafana
# URL: http://localhost:3000
# User: admin
# Pass: admin123 (change in production!)
```

### Key Dashboards

| Dashboard | Panels | Purpose |
|-----------|--------|---------|
| Trading Platform | Consumer lag, DLQ, Latency | System overview |
| Kafka Metrics | Partition lag, throughput | Kafka deep-dive |
| PostgreSQL | Connections, write latency | DB health |

### Verify Metrics Collection

```bash
# Check Prometheus targets
kubectl port-forward svc/prometheus 9090:9090 -n monitoring
# Visit: http://localhost:9090/targets

# Query consumer lag
curl -s "http://localhost:9090/api/v1/query?query=kafka_consumergroup_lag" | jq
```

---

## Summary Checklist

### Autoscaling
- [ ] HPA configured with CPU threshold
- [ ] maxReplicas <= Kafka partition count
- [ ] (Optional) External metrics for Kafka lag

### High Availability
- [ ] Deployment replicas >= 2
- [ ] PodDisruptionBudget configured
- [ ] terminationGracePeriodSeconds set (60s)
- [ ] Consumer group for partition assignment

### Recovery Testing
- [ ] Single pod failure tested
- [ ] DB outage simulated
- [ ] Rolling update verified
- [ ] Node failure simulated (optional)

### Monitoring
- [ ] Prometheus deployed
- [ ] Grafana with dashboards
- [ ] Alerts configured
