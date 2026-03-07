# Network Security Monitor

A Python-based threat detection system for network packet traffic and cloud logs. Detects port scans, brute-force attacks, ARP spoofing, DNS exfiltration, C2 beaconing, cleartext credentials, and cloud-native attacks across CloudTrail, VPC Flow, and Kubernetes Audit sources.

## Features

| Category | Detectors |
|----------|-----------|
| **Network** | Port Scan (SYN/FIN/XMAS) · Brute Force (SSH/FTP/HTTP/RDP/VNC) · ARP Spoofing · DNS Exfiltration · C2 Beaconing · Cleartext Credentials |
| **Cloud — AWS** | IAM Privilege Escalation · Logging Disabled · Suspicious AssumeRole |
| **Cloud — K8s** | Privileged Container · RBAC Wildcard Rules |

All alerts include: `rule_id`, `severity`, `mitre_technique_id`, `source_ip`, `evidence`, `packet_count`, `timestamp`.

## Architecture

```
src/
  models.py              # PacketRecord, CloudEvent, NetworkAlert (Pydantic)
  config.py              # NetworkSecuritySettings (env-configurable thresholds)
  parser/
    json_loader.py       # Load packet fixtures from JSON
    pcap_reader.py       # dpkt-based PCAP reader
  cloud/
    cloudtrail_parser.py
    vpc_flow_parser.py   # JSON + space-delimited text formats
    k8s_audit_parser.py
  detection/
    base.py              # BaseDetector / BaseCloudDetector ABCs
    port_scan.py         # T1046 — SYN/FIN/XMAS scans
    brute_force.py       # T1110 — rolling-window RST count
    arp_spoof.py         # T1557.002 — MAC conflict detection
    dns_exfil.py         # T1048.003 — Shannon entropy + long subdomain + volume
    beaconing.py         # T1071 — low coefficient-of-variation on inter-arrival intervals
    cleartext_creds.py   # T1552.001 — HTTP Basic Auth / FTP PASS / Telnet
    cloud_detectors.py   # Five cloud threat detectors
    rule_engine.py       # Loads YAML detection rules from rules/
  alerts/
    emitter.py           # Write alerts to JSON output file
    alert_manager.py     # SQLite persistence + in-memory deduplication
  api/
    main.py              # FastAPI with lifespan (initialize AlertManager)
    routers/
      health.py          # GET /health
      alerts.py          # POST /analyze/packets · /analyze/cloud · GET /alerts · /alerts/stats
  dashboard/
    app.py               # Streamlit threat dashboard
rules/
  port_scan.yml
  brute_force.yml
  dns_exfil.yml
  beaconing.yml
test_data/               # Synthetic JSON fixtures for all detector types
```

## Detection Logic

### Network Detectors

**Port Scan** (`T1046`) — Groups SYN, FIN, or XMAS packets by source IP. Fires when a single source scans >20 unique destination ports within a 60-second sliding window.

**Brute Force** (`T1110`) — Tracks RST packets to known auth ports (21/22/23/80/443/3389/5900). Fires when maximum window count exceeds 10 failed connections within 5 minutes.

**ARP Spoof** (`T1557.002`) — Maps `(sender_ip → set[mac])` from ARP packets. Fires when the same IP is claimed by more than one MAC address.

**DNS Exfiltration** (`T1048.003`) — Three triggers per source IP: subdomain length >30 chars, Shannon entropy >4.0 bits, or DNS query volume >100/minute. One alert per source.

**C2 Beaconing** (`T1071`) — Groups `(src_ip, dst_ip, dst_port)` SYN packets. Regularity score = `stdev / mean` of inter-arrival intervals. Score ≤0.15 with ≥10 connections = beacon. Lower score = more regular = more suspicious.

**Cleartext Credentials** (`T1552.001`) — Fires on HTTP Basic Auth header present, FTP `PASS` command, or any Telnet traffic. Deduplicates per `(src, dst, port)`.

### Cloud Detectors

| Detector | Trigger | Severity |
|----------|---------|----------|
| `K8sPrivilegedContainerDetector` | create/patch/update pod with `securityContext.privileged=True` | CRITICAL |
| `K8sRBACWildcardDetector` | role/clusterrole with `verbs: ["*"]` or `resources: ["*"]` | HIGH |
| `CloudTrailIAMPrivescDetector` | AttachUserPolicy, PutRolePolicy, CreateAccessKey, AddUserToGroup, etc. | HIGH |
| `CloudTrailLoggingDisabledDetector` | DeleteTrail, StopLogging, DisableKey, DeleteFlowLogs | CRITICAL |
| `CloudTrailAssumeRoleDetector` | Root account login or failed AssumeRole | CRITICAL / MEDIUM |

## API Reference

```
GET  /health
POST /api/v1/analyze/packets   body: {"packets": [...]}
POST /api/v1/analyze/cloud     body: {"source": "cloudtrail|vpc_flow|k8s_audit", "events": [...]}
GET  /api/v1/alerts            ?severity=HIGH&limit=100
GET  /api/v1/alerts/stats
```

### Example: Analyze Packets

```bash
curl -X POST http://localhost:8000/api/v1/analyze/packets \
  -H "Content-Type: application/json" \
  -d '{"packets": [
    {"timestamp": 1735689600, "src_ip": "192.168.1.5", "dst_ip": "10.0.0.1",
     "src_port": 54321, "dst_port": 22, "protocol": "SSH", "tcp_flags": "RST"}
  ]}'
```

### Example: Analyze CloudTrail

```bash
curl -X POST http://localhost:8000/api/v1/analyze/cloud \
  -H "Content-Type: application/json" \
  -d '{"source": "cloudtrail", "events": [
    {"eventTime": "2026-01-01T00:00:00Z", "eventName": "AttachUserPolicy",
     "sourceIPAddress": "1.2.3.4",
     "userIdentity": {"type": "IAMUser", "userName": "attacker"}}
  ]}'
```

### Alert Schema

```json
{
  "alert_id": "uuid",
  "rule_id": "brute_force",
  "title": "Brute Force — SSH",
  "severity": "HIGH",
  "mitre_technique_id": "T1110",
  "source_ip": "192.168.1.5",
  "dest_ip": "10.0.0.1",
  "timestamp": "2026-01-01T00:00:00+00:00",
  "evidence": "15 failed SSH connections within 300s",
  "packet_count": 15
}
```

## Streamlit Dashboard

```bash
streamlit run src/dashboard/app.py
```

Upload any JSON fixture file (Packet JSON, CloudTrail JSON, VPC Flow JSON, K8s Audit JSON) via the sidebar. The dashboard displays:

- Metric cards: Input Records · Total Alerts · Critical · High
- Severity breakdown bar chart
- Detections by rule bar chart
- Filterable alert feed table
- Per-alert detail view with MITRE ATT&CK technique ID and evidence

## Configuration

All thresholds are configurable via environment variables (`NS_` prefix):

| Variable | Default | Description |
|----------|---------|-------------|
| `NS_PORT_SCAN_THRESHOLD` | 20 | Unique ports to trigger scan alert |
| `NS_PORT_SCAN_WINDOW_S` | 60 | Sliding window in seconds |
| `NS_BRUTE_FORCE_THRESHOLD` | 10 | Failed connections threshold |
| `NS_BRUTE_FORCE_WINDOW_S` | 300 | Brute force window (5 min) |
| `NS_DNS_EXFIL_ENTROPY_THRESHOLD` | 4.0 | Shannon entropy cutoff (bits) |
| `NS_BEACON_REGULARITY_THRESHOLD` | 0.15 | Max CoV for beaconing detection |

## Development

```bash
# Install
pip install -e ".[dev]"

# Quality gate
make lint        # ruff check — zero errors
make format      # ruff format --check
make type-check  # mypy --strict — zero errors
make test-cov    # pytest — 94% coverage

# Generate test fixtures
cd test_data && python generate_traffic.py && python generate_cloud_logs.py

# Run API
uvicorn src.api.main:app --reload

# Run dashboard
streamlit run src/dashboard/app.py
```

## Test Coverage

208 tests · 94% coverage · `asyncio_mode = "auto"` for async fixtures

| Module | Coverage |
|--------|----------|
| `detection/` | 96–100% |
| `cloud/` | 86–100% |
| `alerts/` | 97–100% |
| `api/` | 100% |
| `parser/json_loader.py` | 100% |

## MITRE ATT&CK Coverage

| Technique | ID | Detector |
|-----------|----|---------|
| Network Service Discovery | T1046 | PortScanDetector |
| Brute Force | T1110 | BruteForceDetector |
| ARP Cache Poisoning | T1557.002 | ARPSpoofDetector |
| Exfiltration Over Alternative Protocol | T1048.003 | DNSExfilDetector |
| Application Layer Protocol | T1071 | BeaconingDetector |
| Unsecured Credentials in Files | T1552.001 | CleartextCredsDetector |
| Valid Accounts | T1078 | K8sPrivilegedContainer / K8sRBACWildcard |
| Account Manipulation | T1098 | CloudTrailIAMPrivesc |
| Disable or Modify Cloud Logs | T1562.008 | CloudTrailLoggingDisabled |
| Abuse Elevation Control Mechanism | T1548 | CloudTrailAssumeRole |
