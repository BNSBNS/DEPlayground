"""Multi-source synthetic log generator for SIEM testing.

Generates auth, firewall, DNS, and application logs with embedded attack
sequences: brute force, privilege escalation, lateral movement, data exfiltration.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from src.config import GeneratorSettings


class LogSource(StrEnum):
    """Log source types."""

    AUTH = "auth"
    FIREWALL = "firewall"
    DNS = "dns"
    APP = "app"


class AttackType(StrEnum):
    """Known attack sequence types for labeling."""

    BRUTE_FORCE = "brute_force"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    LATERAL_MOVEMENT = "lateral_movement"
    DATA_EXFILTRATION = "data_exfiltration"


class LogEvent(BaseModel):
    """A single normalized log event."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime
    source: LogSource
    event_type: str
    severity: str = "info"
    src_ip: str
    dst_ip: str | None = None
    user: str | None = None
    action: str
    details: dict[str, Any] = Field(default_factory=dict)
    is_attack: bool = False
    attack_type: str | None = None


class LogGenerator:
    """Synthetic multi-source security log generator.

    Creates realistic normal traffic mixed with labeled attack sequences.
    Deterministic via seed for reproducibility.
    """

    def __init__(self, settings: GeneratorSettings | None = None) -> None:
        self._settings = settings or GeneratorSettings()
        self._rng = __import__("random").Random(self._settings.seed)
        self._base_time = datetime(2024, 6, 1, tzinfo=UTC)

        # Build user/host pools
        self._users = [f"user_{i:03d}" for i in range(self._settings.num_users)]
        self._hosts = [f"host-{i:03d}.corp.local" for i in range(self._settings.num_hosts)]
        self._internal_ips = [f"10.0.{i // 256}.{i % 256}" for i in range(self._settings.num_hosts)]
        self._external_ips = [f"203.0.113.{self._rng.randint(1, 254)}" for _ in range(100)]
        self._domains = [
            "google.com",
            "github.com",
            "stackoverflow.com",
            "pypi.org",
            "aws.amazon.com",
            "office365.com",
            "slack.com",
            "zoom.us",
            "cdn.jsdelivr.net",
            "api.internal.corp",
        ]
        self._malicious_domains = [
            "c2-server.evil.com",
            "exfil.darknet.io",
            "malware-drop.ru",
            "phishing-kit.cn",
        ]
        self._admin_users = self._users[:3]  # First 3 are admins
        self._app_endpoints = [
            "/api/v1/users",
            "/api/v1/data",
            "/api/v1/reports",
            "/api/v1/settings",
            "/api/v1/health",
            "/login",
            "/dashboard",
        ]
        self._admin_endpoints = [
            "/admin/users",
            "/admin/config",
            "/admin/audit",
            "/admin/roles",
        ]

    def generate(self) -> list[LogEvent]:
        """Generate all log events: normal traffic + attack sequences."""
        # Calculate attack budget
        total = self._settings.num_events
        attack_budget = int(total * self._settings.attack_rate)
        normal_budget = total - attack_budget

        events: list[LogEvent] = []

        # Generate normal events
        events.extend(self._generate_normal_events(normal_budget))

        # Generate attack sequences (equal split across 4 types)
        per_attack = attack_budget // 4
        events.extend(self._generate_brute_force(per_attack))
        events.extend(self._generate_privilege_escalation(per_attack))
        events.extend(self._generate_lateral_movement(per_attack))
        events.extend(
            self._generate_data_exfiltration(
                attack_budget - 3 * per_attack  # remainder goes here
            )
        )

        # Sort by timestamp for realistic ordering
        events.sort(key=lambda e: e.timestamp)
        return events

    def _random_timestamp(self, day_range: int = 30) -> datetime:
        """Random timestamp within the generation window."""
        offset = timedelta(
            days=self._rng.randint(0, day_range),
            hours=self._rng.randint(0, 23),
            minutes=self._rng.randint(0, 59),
            seconds=self._rng.randint(0, 59),
        )
        return self._base_time + offset

    def _business_hours_timestamp(self, day_range: int = 30) -> datetime:
        """Random timestamp during business hours (8am-6pm)."""
        offset = timedelta(
            days=self._rng.randint(0, day_range),
            hours=self._rng.randint(8, 17),
            minutes=self._rng.randint(0, 59),
            seconds=self._rng.randint(0, 59),
        )
        return self._base_time + offset

    def _generate_normal_events(self, count: int) -> list[LogEvent]:
        """Generate normal (benign) log events across all sources."""
        events: list[LogEvent] = []
        generators = [
            self._normal_auth,
            self._normal_firewall,
            self._normal_dns,
            self._normal_app,
        ]
        per_source = count // 4
        for gen_fn in generators:
            events.extend(gen_fn(per_source))
        # Fill remainder with random source
        remainder = count - len(events)
        for _ in range(remainder):
            fn = self._rng.choice(generators)
            events.extend(fn(1))
        return events

    def _normal_auth(self, count: int) -> list[LogEvent]:
        """Normal authentication events (mostly successes)."""
        events: list[LogEvent] = []
        for _ in range(count):
            user = self._rng.choice(self._users)
            success = self._rng.random() > 0.05  # 5% typo failures
            events.append(
                LogEvent(
                    timestamp=self._business_hours_timestamp(),
                    source=LogSource.AUTH,
                    event_type="login_success" if success else "login_failure",
                    severity="info" if success else "warning",
                    src_ip=self._rng.choice(self._internal_ips),
                    dst_ip=self._rng.choice(self._internal_ips),
                    user=user,
                    action="allow" if success else "deny",
                    details={
                        "method": self._rng.choice(["password", "sso", "mfa"]),
                        "host": self._rng.choice(self._hosts),
                    },
                )
            )
        return events

    def _normal_firewall(self, count: int) -> list[LogEvent]:
        """Normal firewall events (mostly allows)."""
        events: list[LogEvent] = []
        common_ports = [80, 443, 22, 53, 8080, 3389]
        for _ in range(count):
            allowed = self._rng.random() > 0.02  # 2% blocked
            events.append(
                LogEvent(
                    timestamp=self._random_timestamp(),
                    source=LogSource.FIREWALL,
                    event_type="connection_allowed" if allowed else "connection_blocked",
                    severity="info" if allowed else "warning",
                    src_ip=self._rng.choice(self._internal_ips),
                    dst_ip=self._rng.choice(self._external_ips),
                    action="allow" if allowed else "deny",
                    details={
                        "dst_port": self._rng.choice(common_ports),
                        "protocol": self._rng.choice(["tcp", "udp"]),
                        "bytes_sent": self._rng.randint(100, 10000),
                        "bytes_received": self._rng.randint(100, 50000),
                    },
                )
            )
        return events

    def _normal_dns(self, count: int) -> list[LogEvent]:
        """Normal DNS query events."""
        events: list[LogEvent] = []
        for _ in range(count):
            domain = self._rng.choice(self._domains)
            events.append(
                LogEvent(
                    timestamp=self._random_timestamp(),
                    source=LogSource.DNS,
                    event_type="dns_query",
                    severity="info",
                    src_ip=self._rng.choice(self._internal_ips),
                    dst_ip="10.0.0.1",  # internal DNS
                    action="query",
                    details={
                        "query": domain,
                        "query_type": self._rng.choice(["A", "AAAA", "CNAME"]),
                        "response_code": "NOERROR",
                    },
                )
            )
        return events

    def _normal_app(self, count: int) -> list[LogEvent]:
        """Normal application request events."""
        events: list[LogEvent] = []
        for _ in range(count):
            user = self._rng.choice(self._users)
            endpoint = self._rng.choice(self._app_endpoints)
            codes = [200, 201, 304, 400, 404, 500]
            weights = [60, 10, 10, 5, 10, 5]
            status = self._rng.choices(codes, weights=weights)[0]
            events.append(
                LogEvent(
                    timestamp=self._business_hours_timestamp(),
                    source=LogSource.APP,
                    event_type="http_request",
                    severity="info" if status < 400 else ("warning" if status < 500 else "error"),
                    src_ip=self._rng.choice(self._internal_ips),
                    dst_ip=self._rng.choice(self._internal_ips),
                    user=user,
                    action="request",
                    details={
                        "method": self._rng.choice(["GET", "POST", "PUT"]),
                        "endpoint": endpoint,
                        "status_code": status,
                        "user_agent": "Mozilla/5.0",
                        "response_time_ms": self._rng.randint(10, 500),
                    },
                )
            )
        return events

    # --- Attack sequences ---

    def _generate_brute_force(self, budget: int) -> list[LogEvent]:
        """Brute force: many failed logins then success from same IP.

        Pattern: 50 failures within 10 minutes, then 1 success.
        """
        events: list[LogEvent] = []
        target_user = self._rng.choice(self._users)
        attacker_ip = self._rng.choice(self._external_ips)
        target_host = self._rng.choice(self._hosts)
        base_time = self._random_timestamp()
        # Cap failures to budget-1 (save 1 for success), max 50
        num_failures = min(budget - 1, 50) if budget > 1 else 0

        for i in range(num_failures):
            events.append(
                LogEvent(
                    timestamp=base_time + timedelta(seconds=i * 12),
                    source=LogSource.AUTH,
                    event_type="login_failure",
                    severity="warning",
                    src_ip=attacker_ip,
                    dst_ip=self._rng.choice(self._internal_ips),
                    user=target_user,
                    action="deny",
                    details={"method": "password", "host": target_host, "attempt": i + 1},
                    is_attack=True,
                    attack_type=AttackType.BRUTE_FORCE,
                )
            )

        # Successful login after failures
        if budget > 0:
            events.append(
                LogEvent(
                    timestamp=base_time + timedelta(seconds=num_failures * 12 + 5),
                    source=LogSource.AUTH,
                    event_type="login_success",
                    severity="warning",
                    src_ip=attacker_ip,
                    dst_ip=self._rng.choice(self._internal_ips),
                    user=target_user,
                    action="allow",
                    details={"method": "password", "host": target_host, "post_brute_force": True},
                    is_attack=True,
                    attack_type=AttackType.BRUTE_FORCE,
                )
            )

        # Pad remaining budget with reconnaissance activity
        remaining = budget - len(events)
        for i in range(remaining):
            events.append(
                LogEvent(
                    timestamp=base_time + timedelta(minutes=15, seconds=i * 30),
                    source=LogSource.APP,
                    event_type="http_request",
                    severity="info",
                    src_ip=attacker_ip,
                    user=target_user,
                    action="request",
                    details={
                        "method": "GET",
                        "endpoint": self._rng.choice(self._app_endpoints + self._admin_endpoints),
                        "status_code": 200,
                    },
                    is_attack=True,
                    attack_type=AttackType.BRUTE_FORCE,
                )
            )

        return events

    def _generate_privilege_escalation(self, budget: int) -> list[LogEvent]:
        """Privilege escalation: normal user accesses admin endpoints.

        Pattern: regular activity, then sudden admin API calls.
        """
        events: list[LogEvent] = []
        attacker = self._rng.choice([u for u in self._users if u not in self._admin_users])
        attacker_ip = self._rng.choice(self._internal_ips)
        base_time = self._random_timestamp()

        # Normal activity first (1/3 of budget)
        normal_count = max(budget // 3, 1)
        for i in range(normal_count):
            events.append(
                LogEvent(
                    timestamp=base_time + timedelta(minutes=i * 5),
                    source=LogSource.APP,
                    event_type="http_request",
                    severity="info",
                    src_ip=attacker_ip,
                    user=attacker,
                    action="request",
                    details={
                        "method": "GET",
                        "endpoint": self._rng.choice(self._app_endpoints),
                        "status_code": 200,
                    },
                    is_attack=True,
                    attack_type=AttackType.PRIVILEGE_ESCALATION,
                )
            )

        # Admin endpoint access (remaining budget)
        admin_count = budget - normal_count
        for i in range(admin_count):
            endpoint = self._rng.choice(self._admin_endpoints)
            events.append(
                LogEvent(
                    timestamp=base_time + timedelta(hours=1, minutes=i * 2),
                    source=LogSource.APP,
                    event_type="http_request",
                    severity="warning",
                    src_ip=attacker_ip,
                    user=attacker,
                    action="request",
                    details={
                        "method": self._rng.choice(["GET", "POST", "PUT", "DELETE"]),
                        "endpoint": endpoint,
                        "status_code": self._rng.choice([200, 403]),
                        "is_admin_endpoint": True,
                    },
                    is_attack=True,
                    attack_type=AttackType.PRIVILEGE_ESCALATION,
                )
            )

        return events

    def _generate_lateral_movement(self, budget: int) -> list[LogEvent]:
        """Lateral movement: same user accesses multiple hosts sequentially.

        Pattern: login to 5+ hosts within 1 hour.
        """
        events: list[LogEvent] = []
        attacker = self._rng.choice(self._users)
        attacker_ip = self._rng.choice(self._internal_ips)
        base_time = self._random_timestamp()

        # Access at least 5 hosts (or as many as budget allows)
        num_hosts = min(budget, max(5, len(self._hosts)))
        target_hosts = self._rng.sample(self._hosts, min(num_hosts, len(self._hosts)))

        for i, host in enumerate(target_hosts):
            if len(events) >= budget:
                break
            # Login event
            events.append(
                LogEvent(
                    timestamp=base_time + timedelta(minutes=i * 8),
                    source=LogSource.AUTH,
                    event_type="login_success",
                    severity="info",
                    src_ip=attacker_ip,
                    dst_ip=self._internal_ips[i % len(self._internal_ips)],
                    user=attacker,
                    action="allow",
                    details={"method": "ssh", "host": host},
                    is_attack=True,
                    attack_type=AttackType.LATERAL_MOVEMENT,
                )
            )

        # Fill remaining with internal network scans
        remaining = budget - len(events)
        for i in range(remaining):
            events.append(
                LogEvent(
                    timestamp=base_time + timedelta(hours=1, seconds=i * 5),
                    source=LogSource.FIREWALL,
                    event_type="connection_allowed",
                    severity="info",
                    src_ip=attacker_ip,
                    dst_ip=self._rng.choice(self._internal_ips),
                    action="allow",
                    details={
                        "dst_port": self._rng.choice([22, 445, 3389, 5985]),
                        "protocol": "tcp",
                        "bytes_sent": self._rng.randint(500, 5000),
                    },
                    is_attack=True,
                    attack_type=AttackType.LATERAL_MOVEMENT,
                )
            )

        return events

    def _generate_data_exfiltration(self, budget: int) -> list[LogEvent]:
        """Data exfiltration: large outbound transfers at unusual hours.

        Pattern: DNS queries to suspicious domains + large data transfers at 2am.
        """
        events: list[LogEvent] = []
        attacker = self._rng.choice(self._users)
        attacker_ip = self._rng.choice(self._internal_ips)
        exfil_ip = self._rng.choice(self._external_ips)
        base_day = self._rng.randint(0, 20)
        # 2am timestamp
        base_time = self._base_time + timedelta(days=base_day, hours=2)

        # DNS lookups to malicious domains (1/3 budget)
        dns_count = max(budget // 3, 1)
        for i in range(dns_count):
            if len(events) >= budget:
                break
            events.append(
                LogEvent(
                    timestamp=base_time + timedelta(seconds=i * 10),
                    source=LogSource.DNS,
                    event_type="dns_query",
                    severity="info",
                    src_ip=attacker_ip,
                    dst_ip="10.0.0.1",
                    user=attacker,
                    action="query",
                    details={
                        "query": self._rng.choice(self._malicious_domains),
                        "query_type": "A",
                        "response_code": "NOERROR",
                    },
                    is_attack=True,
                    attack_type=AttackType.DATA_EXFILTRATION,
                )
            )

        # Large outbound data transfers
        remaining = budget - len(events)
        for i in range(remaining):
            events.append(
                LogEvent(
                    timestamp=base_time + timedelta(minutes=5, seconds=i * 15),
                    source=LogSource.FIREWALL,
                    event_type="connection_allowed",
                    severity="info",
                    src_ip=attacker_ip,
                    dst_ip=exfil_ip,
                    action="allow",
                    details={
                        "dst_port": 443,
                        "protocol": "tcp",
                        "bytes_sent": self._rng.randint(500_000, 50_000_000),
                        "bytes_received": self._rng.randint(100, 1000),
                    },
                    is_attack=True,
                    attack_type=AttackType.DATA_EXFILTRATION,
                )
            )

        return events

    def generate_sample_alerts(self, count: int = 10) -> list[dict[str, Any]]:
        """Generate sample SecurityAlert dicts matching Foundations #8 schema.

        Returns dicts (not SecurityAlert objects) so generator has no hard
        dependency on cysec_shared at runtime for testing flexibility.
        """
        alerts: list[dict[str, Any]] = []
        alert_templates = [
            {
                "source_project": "FraudAndAnomaly",
                "rule_id": "FRAUD-001",
                "severity": "high",
                "title": "Suspicious Transaction Detected",
                "mitre_technique_id": "T1078",
                "mitre_tactic": "Initial Access",
            },
            {
                "source_project": "NetworkSecurity",
                "rule_id": "NET-001",
                "severity": "critical",
                "title": "Port Scan Detected",
                "mitre_technique_id": "T1046",
                "mitre_tactic": "Discovery",
            },
            {
                "source_project": "AIMMLSecurity",
                "rule_id": "AI-001",
                "severity": "medium",
                "title": "Prompt Injection Attempt",
                "mitre_technique_id": "T1059",
                "mitre_tactic": "Execution",
            },
            {
                "source_project": "APISecurity",
                "rule_id": "API-001",
                "severity": "high",
                "title": "BOLA Vulnerability Detected",
                "mitre_technique_id": "T1190",
                "mitre_tactic": "Initial Access",
            },
        ]

        for i in range(count):
            template = alert_templates[i % len(alert_templates)]
            alerts.append(
                {
                    "alert_id": str(uuid.uuid4()),
                    "timestamp": (self._base_time + timedelta(hours=i)).isoformat(),
                    "source_project": template["source_project"],
                    "rule_id": template["rule_id"],
                    "severity": template["severity"],
                    "title": template["title"],
                    "description": f"Sample alert {i + 1}: {template['title']}",
                    "mitre_technique_id": template["mitre_technique_id"],
                    "mitre_tactic": template["mitre_tactic"],
                    "affected_asset": self._rng.choice(self._hosts),
                    "source_ip": self._rng.choice(self._external_ips),
                    "evidence": {"sample": True, "index": i},
                    "recommendations": ["Investigate immediately"],
                }
            )
        return alerts
