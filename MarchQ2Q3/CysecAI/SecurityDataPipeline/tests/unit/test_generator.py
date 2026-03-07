"""Tests for multi-source log generator (Phase 1).

Verifies event generation, attack sequence patterns, determinism,
and schema correctness across all log sources.
"""

from __future__ import annotations

from datetime import UTC

from cysec_shared import SecurityAlert
from src.config import GeneratorSettings
from src.data.generator import AttackType, LogEvent, LogGenerator, LogSource


class TestEventGeneration:
    """Basic generation and schema tests."""

    def test_generates_correct_count(self, events: list[LogEvent]) -> None:
        assert len(events) == 1000

    def test_events_sorted_by_timestamp(self, events: list[LogEvent]) -> None:
        timestamps = [e.timestamp for e in events]
        assert timestamps == sorted(timestamps)

    def test_all_events_have_required_fields(self, events: list[LogEvent]) -> None:
        for event in events:
            assert event.event_id
            assert event.timestamp.tzinfo == UTC
            assert event.source in list(LogSource)
            assert event.event_type
            assert event.src_ip
            assert event.action

    def test_all_sources_present(self, events: list[LogEvent]) -> None:
        sources = {e.source for e in events}
        assert sources == {LogSource.AUTH, LogSource.FIREWALL, LogSource.DNS, LogSource.APP}

    def test_attack_rate_within_tolerance(self, events: list[LogEvent]) -> None:
        attack_count = sum(1 for e in events if e.is_attack)
        rate = attack_count / len(events)
        # Target 5%, allow 2-10% tolerance
        assert 0.02 <= rate <= 0.10, f"Attack rate {rate:.2%} outside tolerance"

    def test_attack_types_present(self, events: list[LogEvent]) -> None:
        attack_types = {e.attack_type for e in events if e.is_attack}
        expected = {
            AttackType.BRUTE_FORCE,
            AttackType.PRIVILEGE_ESCALATION,
            AttackType.LATERAL_MOVEMENT,
            AttackType.DATA_EXFILTRATION,
        }
        assert attack_types == expected

    def test_normal_events_not_labeled(self, events: list[LogEvent]) -> None:
        normal = [e for e in events if not e.is_attack]
        assert len(normal) > 0
        for e in normal:
            assert e.attack_type is None


class TestDeterminism:
    """Same seed should produce same data."""

    def test_same_seed_same_output(self) -> None:
        settings = GeneratorSettings(num_events=500, seed=123)
        gen1 = LogGenerator(settings)
        gen2 = LogGenerator(settings)
        events1 = gen1.generate()
        events2 = gen2.generate()
        assert len(events1) == len(events2)
        for e1, e2 in zip(events1, events2, strict=True):
            assert e1.timestamp == e2.timestamp
            assert e1.source == e2.source
            assert e1.event_type == e2.event_type
            assert e1.src_ip == e2.src_ip
            assert e1.is_attack == e2.is_attack

    def test_different_seed_different_output(self) -> None:
        settings1 = GeneratorSettings(num_events=500, seed=1)
        settings2 = GeneratorSettings(num_events=500, seed=2)
        events1 = LogGenerator(settings1).generate()
        events2 = LogGenerator(settings2).generate()
        # At least some events differ
        diffs = sum(1 for e1, e2 in zip(events1, events2, strict=True) if e1.src_ip != e2.src_ip)
        assert diffs > 0


class TestBruteForce:
    """Brute force attack sequence tests."""

    def test_has_failed_then_success_pattern(self, events: list[LogEvent]) -> None:
        bf_events = [e for e in events if e.attack_type == AttackType.BRUTE_FORCE]
        assert len(bf_events) > 1
        # Should have failures and at least one success
        failures = [e for e in bf_events if e.event_type == "login_failure"]
        successes = [
            e for e in bf_events if e.event_type == "login_success" and e.source == LogSource.AUTH
        ]
        assert len(failures) > 0
        assert len(successes) >= 1

    def test_same_attacker_ip(self, events: list[LogEvent]) -> None:
        bf_auth = [
            e
            for e in events
            if e.attack_type == AttackType.BRUTE_FORCE and e.source == LogSource.AUTH
        ]
        ips = {e.src_ip for e in bf_auth}
        assert len(ips) == 1  # All from same IP

    def test_same_target_user(self, events: list[LogEvent]) -> None:
        bf_auth = [
            e
            for e in events
            if e.attack_type == AttackType.BRUTE_FORCE and e.source == LogSource.AUTH
        ]
        users = {e.user for e in bf_auth}
        assert len(users) == 1


class TestPrivilegeEscalation:
    """Privilege escalation attack sequence tests."""

    def test_non_admin_accesses_admin_endpoints(self, events: list[LogEvent]) -> None:
        pe_events = [e for e in events if e.attack_type == AttackType.PRIVILEGE_ESCALATION]
        assert len(pe_events) > 0
        admin_accesses = [e for e in pe_events if e.details.get("is_admin_endpoint")]
        assert len(admin_accesses) > 0

    def test_attacker_is_not_admin(self, generator: LogGenerator, events: list[LogEvent]) -> None:
        pe_events = [e for e in events if e.attack_type == AttackType.PRIVILEGE_ESCALATION]
        attackers = {e.user for e in pe_events}
        # Should not overlap with admin users
        assert not attackers.intersection(set(generator._admin_users))


class TestLateralMovement:
    """Lateral movement attack sequence tests."""

    def test_multiple_hosts_accessed(self, events: list[LogEvent]) -> None:
        lm_events = [
            e
            for e in events
            if e.attack_type == AttackType.LATERAL_MOVEMENT and e.source == LogSource.AUTH
        ]
        hosts = {e.details.get("host") for e in lm_events}
        assert len(hosts) >= 3, f"Expected >=3 unique hosts, got {len(hosts)}"

    def test_same_user(self, events: list[LogEvent]) -> None:
        lm_events = [e for e in events if e.attack_type == AttackType.LATERAL_MOVEMENT]
        users = {e.user for e in lm_events if e.user}
        assert len(users) == 1


class TestDataExfiltration:
    """Data exfiltration attack sequence tests."""

    def test_has_dns_and_transfer_events(self, events: list[LogEvent]) -> None:
        exfil = [e for e in events if e.attack_type == AttackType.DATA_EXFILTRATION]
        sources = {e.source for e in exfil}
        assert LogSource.DNS in sources
        assert LogSource.FIREWALL in sources

    def test_dns_queries_malicious_domains(
        self, generator: LogGenerator, events: list[LogEvent]
    ) -> None:
        dns_exfil = [
            e
            for e in events
            if e.attack_type == AttackType.DATA_EXFILTRATION and e.source == LogSource.DNS
        ]
        for e in dns_exfil:
            assert e.details["query"] in generator._malicious_domains

    def test_large_outbound_transfers(self, events: list[LogEvent]) -> None:
        fw_exfil = [
            e
            for e in events
            if e.attack_type == AttackType.DATA_EXFILTRATION and e.source == LogSource.FIREWALL
        ]
        for e in fw_exfil:
            # Exfiltration = large bytes_sent
            assert e.details["bytes_sent"] >= 500_000

    def test_occurs_at_unusual_hours(self, events: list[LogEvent]) -> None:
        exfil = [e for e in events if e.attack_type == AttackType.DATA_EXFILTRATION]
        # Should be around 2am
        hours = {e.timestamp.hour for e in exfil}
        assert any(h in hours for h in [1, 2, 3])


class TestSampleAlerts:
    """SecurityAlert sample generation tests."""

    def test_generates_correct_count(self, generator: LogGenerator) -> None:
        alerts = generator.generate_sample_alerts(10)
        assert len(alerts) == 10

    def test_alert_schema_matches_security_alert(self, generator: LogGenerator) -> None:
        alerts = generator.generate_sample_alerts(5)
        for alert_dict in alerts:
            # Should be parseable as SecurityAlert
            alert = SecurityAlert(**alert_dict)
            assert alert.alert_id
            assert alert.source_project
            assert alert.rule_id
            assert alert.severity in ("critical", "high", "medium", "low", "info")
            assert alert.title
            assert alert.affected_asset

    def test_multiple_source_projects(self, generator: LogGenerator) -> None:
        alerts = generator.generate_sample_alerts(10)
        projects = {a["source_project"] for a in alerts}
        assert len(projects) >= 3

    def test_alerts_have_mitre_mapping(self, generator: LogGenerator) -> None:
        alerts = generator.generate_sample_alerts(5)
        for alert in alerts:
            assert alert["mitre_technique_id"]
            assert alert["mitre_tactic"]
