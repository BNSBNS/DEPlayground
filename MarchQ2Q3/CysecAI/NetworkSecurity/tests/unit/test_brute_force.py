"""Tests for the brute force detector."""

from __future__ import annotations

from src.detection.brute_force import BruteForceDetector
from src.models import PacketRecord, Protocol, TCPFlags

_BASE_TS = 1735689600.0


def _rst_packets(
    count: int, port: int = 22, src: str = "1.2.3.4", interval: float = 5.0
) -> list[PacketRecord]:
    return [
        PacketRecord(
            timestamp=_BASE_TS + i * interval,
            src_ip=src,
            dst_ip="10.0.0.1",
            src_port=50000 + i,
            dst_port=port,
            protocol=Protocol.SSH if port == 22 else Protocol.TCP,
            tcp_flags=TCPFlags.RST,
        )
        for i in range(count)
    ]


class TestBruteForceDetector:
    def test_detects_ssh_brute_force(self, brute_force_packets: list[PacketRecord]) -> None:
        alerts = BruteForceDetector().analyze(brute_force_packets)
        assert len(alerts) > 0
        assert any("SSH" in a.title for a in alerts)

    def test_rule_id(self) -> None:
        assert BruteForceDetector().rule_id == "brute_force"

    def test_mitre_technique(self, brute_force_packets: list[PacketRecord]) -> None:
        alerts = BruteForceDetector().analyze(brute_force_packets)
        assert all(a.mitre_technique_id == "T1110" for a in alerts)

    def test_no_alert_below_threshold(self) -> None:
        packets = _rst_packets(5)  # below default 10
        assert BruteForceDetector().analyze(packets) == []

    def test_alert_at_threshold(self) -> None:
        packets = _rst_packets(11)
        alerts = BruteForceDetector().analyze(packets)
        assert len(alerts) > 0

    def test_ftp_brute_force(self) -> None:
        packets = _rst_packets(15, port=21)
        alerts = BruteForceDetector().analyze(packets)
        assert any("FTP" in a.title for a in alerts)

    def test_http_brute_force(self) -> None:
        packets = _rst_packets(15, port=80)
        alerts = BruteForceDetector().analyze(packets)
        assert len(alerts) > 0

    def test_non_auth_port_ignored(self) -> None:
        # Port 9999 is not in the auth ports set
        packets = _rst_packets(20, port=9999)
        assert BruteForceDetector().analyze(packets) == []

    def test_window_boundary(self) -> None:
        # 15 RSTs spread over 10 minutes — beyond the 5-minute window
        packets = _rst_packets(15, interval=45.0)  # 15 * 45 = 675s > 300s
        alerts = BruteForceDetector(threshold=10, window_s=300).analyze(packets)
        assert len(alerts) == 0

    def test_empty_packets(self) -> None:
        assert BruteForceDetector().analyze([]) == []

    def test_source_ip_in_alert(self) -> None:
        packets = _rst_packets(15, src="5.6.7.8")
        alerts = BruteForceDetector().analyze(packets)
        assert all(a.source_ip == "5.6.7.8" for a in alerts)

    def test_evidence_contains_count(self) -> None:
        packets = _rst_packets(15)
        alerts = BruteForceDetector().analyze(packets)
        assert any("15" in a.evidence for a in alerts)
