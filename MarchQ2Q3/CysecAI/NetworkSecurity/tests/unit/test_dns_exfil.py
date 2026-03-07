"""Tests for the DNS exfiltration detector."""

from __future__ import annotations

from src.detection.dns_exfil import DNSExfilDetector, shannon_entropy
from src.models import PacketRecord, Protocol

_BASE_TS = 1735689600.0
_SRC = "10.0.0.5"
_RESOLVER = "8.8.8.8"


def _dns_pkt(ts: float, query: str, src: str = _SRC) -> PacketRecord:
    return PacketRecord(
        timestamp=ts,
        src_ip=src,
        dst_ip=_RESOLVER,
        src_port=12345,
        dst_port=53,
        protocol=Protocol.DNS,
        dns_query=query,
    )


class TestShannonEntropy:
    def test_empty_string(self) -> None:
        assert shannon_entropy("") == 0.0

    def test_single_char(self) -> None:
        assert shannon_entropy("a") == 0.0

    def test_uniform_distribution(self) -> None:
        # "abcd" has entropy 2.0 bits
        result = shannon_entropy("abcd")
        assert abs(result - 2.0) < 0.01

    def test_high_entropy_base64(self) -> None:
        # 32 distinct characters → entropy = log2(32) = 5.0 bits, well above 4.0
        encoded = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef"
        assert shannon_entropy(encoded) > 4.0

    def test_repetitive_string_low_entropy(self) -> None:
        assert shannon_entropy("aaaaaaaaaa") == 0.0


class TestDNSExfilDetector:
    def test_detects_long_subdomain(self) -> None:
        long_sub = "a" * 31  # > 30 chars
        query = f"{long_sub}.attacker.com"
        packets = [_dns_pkt(_BASE_TS, query)]
        alerts = DNSExfilDetector().analyze(packets)
        assert len(alerts) > 0

    def test_rule_id(self) -> None:
        assert DNSExfilDetector().rule_id == "dns_exfil"

    def test_mitre_technique(self) -> None:
        long_sub = "a" * 31
        packets = [_dns_pkt(_BASE_TS, f"{long_sub}.x.com")]
        alerts = DNSExfilDetector().analyze(packets)
        assert alerts[0].mitre_technique_id == "T1048.003"

    def test_normal_short_query_no_alert(self) -> None:
        packets = [_dns_pkt(_BASE_TS, "www.google.com")]
        assert DNSExfilDetector().analyze(packets) == []

    def test_high_entropy_subdomain_detected(self) -> None:
        # High entropy subdomain: 32 distinct chars → entropy = 5.0 bits > 4.0 threshold
        sub = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef"
        packets = [_dns_pkt(_BASE_TS, f"{sub}.example.com")]
        alerts = DNSExfilDetector().analyze(packets)
        assert len(alerts) > 0

    def test_volume_detection(self) -> None:
        # 110 queries in 60 seconds — triggers volume detection
        packets = [_dns_pkt(_BASE_TS + i * 0.5, f"query{i}.example.com") for i in range(110)]
        alerts = DNSExfilDetector(volume_per_minute=100).analyze(packets)
        assert len(alerts) > 0

    def test_low_volume_no_alert(self) -> None:
        packets = [_dns_pkt(_BASE_TS + i * 5, f"q{i}.example.com") for i in range(10)]
        assert DNSExfilDetector().analyze(packets) == []

    def test_empty_packets(self) -> None:
        assert DNSExfilDetector().analyze([]) == []

    def test_non_dns_ignored(self) -> None:
        packets = [
            PacketRecord(timestamp=_BASE_TS, src_ip=_SRC, dst_ip=_RESOLVER, protocol=Protocol.TCP)
        ]
        assert DNSExfilDetector().analyze(packets) == []

    def test_no_query_skipped(self) -> None:
        packets = [
            PacketRecord(
                timestamp=_BASE_TS,
                src_ip=_SRC,
                dst_ip=_RESOLVER,
                protocol=Protocol.DNS,
                dns_query=None,
            )
        ]
        assert DNSExfilDetector().analyze(packets) == []

    def test_dedup_single_alert_per_source(self) -> None:
        # Multiple triggering queries from same source → single alert
        sub = "a" * 35
        packets = [_dns_pkt(_BASE_TS + i, f"{sub}.evil.com") for i in range(5)]
        alerts = DNSExfilDetector().analyze(packets)
        src_alerts = [a for a in alerts if a.source_ip == _SRC]
        assert len(src_alerts) == 1
