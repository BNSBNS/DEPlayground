"""Tests for the port scan detector."""

from __future__ import annotations

from src.detection.port_scan import PortScanDetector
from src.models import PacketRecord, Protocol, TCPFlags

_BASE_TS = 1735689600.0
_SRC = "192.168.1.99"
_DST = "10.0.0.1"


def _syn_packets(count: int, interval: float = 0.5) -> list[PacketRecord]:
    return [
        PacketRecord(
            timestamp=_BASE_TS + i * interval,
            src_ip=_SRC,
            dst_ip=_DST,
            src_port=54321,
            dst_port=i + 1,
            protocol=Protocol.TCP,
            tcp_flags=TCPFlags.SYN,
        )
        for i in range(count)
    ]


def _fin_packets(count: int) -> list[PacketRecord]:
    return [
        PacketRecord(
            timestamp=_BASE_TS + i * 0.5,
            src_ip=_SRC,
            dst_ip=_DST,
            src_port=54321,
            dst_port=i + 1,
            protocol=Protocol.TCP,
            tcp_flags=TCPFlags.FIN,
        )
        for i in range(count)
    ]


def _xmas_packets(count: int) -> list[PacketRecord]:
    return [
        PacketRecord(
            timestamp=_BASE_TS + i * 0.5,
            src_ip=_SRC,
            dst_ip=_DST,
            src_port=54321,
            dst_port=i + 1,
            protocol=Protocol.TCP,
            tcp_flags=TCPFlags.XMAS,
        )
        for i in range(count)
    ]


class TestPortScanDetector:
    def test_detects_syn_scan(self, port_scan_packets: list[PacketRecord]) -> None:
        alerts = PortScanDetector().analyze(port_scan_packets)
        assert any("SYN" in a.title for a in alerts)

    def test_syn_scan_rule_id(self, port_scan_packets: list[PacketRecord]) -> None:
        alerts = PortScanDetector().analyze(port_scan_packets)
        assert any(a.rule_id == "port_scan_syn" for a in alerts)

    def test_syn_scan_mitre(self, port_scan_packets: list[PacketRecord]) -> None:
        alerts = PortScanDetector().analyze(port_scan_packets)
        assert all(a.mitre_technique_id == "T1046" for a in alerts)

    def test_no_alert_below_threshold(self) -> None:
        # Only 10 SYN packets — below default threshold of 20
        packets = _syn_packets(10)
        alerts = PortScanDetector().analyze(packets)
        syn_alerts = [a for a in alerts if "SYN" in a.title]
        assert len(syn_alerts) == 0

    def test_alert_at_threshold(self) -> None:
        packets = _syn_packets(21)
        alerts = PortScanDetector().analyze(packets)
        assert any("SYN" in a.title for a in alerts)

    def test_detects_fin_scan(self) -> None:
        packets = _fin_packets(25)
        alerts = PortScanDetector().analyze(packets)
        assert any("FIN" in a.title for a in alerts)

    def test_detects_xmas_scan(self) -> None:
        packets = _xmas_packets(25)
        alerts = PortScanDetector().analyze(packets)
        assert any("XMAS" in a.title for a in alerts)

    def test_empty_packets(self) -> None:
        assert PortScanDetector().analyze([]) == []

    def test_non_tcp_packets_ignored(self) -> None:
        packets = [
            PacketRecord(
                timestamp=_BASE_TS + i, src_ip=_SRC, dst_ip=_DST, dst_port=i, protocol=Protocol.UDP
            )
            for i in range(30)
        ]
        alerts = PortScanDetector().analyze(packets)
        assert len(alerts) == 0

    def test_window_boundary(self) -> None:
        # 25 SYN packets spread over 90s — should NOT trigger 60s window
        packets = _syn_packets(25, interval=3.6)  # 25 * 3.6 = 90s
        alerts = PortScanDetector(threshold=20, window_s=60).analyze(packets)
        syn_alerts = [a for a in alerts if "SYN" in a.title]
        assert len(syn_alerts) == 0

    def test_source_ip_in_alert(self, port_scan_packets: list[PacketRecord]) -> None:
        alerts = PortScanDetector().analyze(port_scan_packets)
        assert all(a.source_ip == _SRC for a in alerts)

    def test_rule_id(self) -> None:
        assert PortScanDetector().rule_id == "port_scan"
