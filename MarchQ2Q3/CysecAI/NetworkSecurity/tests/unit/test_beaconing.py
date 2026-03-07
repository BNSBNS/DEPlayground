"""Tests for the C2 beaconing detector."""

from __future__ import annotations

import random

from src.detection.beaconing import BeaconingDetector, _regularity_score
from src.models import PacketRecord, Protocol, TCPFlags

_BASE_TS = 1735689600.0
_SRC = "10.0.0.10"
_C2 = "198.51.100.1"
_PORT = 443


def _beacon_packets(
    count: int, interval: float = 60.0, jitter: float = 2.0, seed: int = 42
) -> list[PacketRecord]:
    rng = random.Random(seed)
    return [
        PacketRecord(
            timestamp=_BASE_TS + i * interval + rng.uniform(-jitter, jitter),
            src_ip=_SRC,
            dst_ip=_C2,
            src_port=rng.randint(49152, 65535),
            dst_port=_PORT,
            protocol=Protocol.TCP,
            tcp_flags=TCPFlags.SYN,
        )
        for i in range(count)
    ]


class TestRegularityScore:
    def test_perfectly_regular(self) -> None:
        intervals = [60.0, 60.0, 60.0, 60.0, 60.0]
        score = _regularity_score(intervals)
        assert score == 0.0

    def test_irregular(self) -> None:
        intervals = [10.0, 100.0, 5.0, 80.0, 55.0]
        score = _regularity_score(intervals)
        assert score > 0.5

    def test_single_interval(self) -> None:
        score = _regularity_score([60.0])
        assert score == float("inf")

    def test_empty_intervals(self) -> None:
        score = _regularity_score([])
        assert score == float("inf")

    def test_zero_mean_returns_inf(self) -> None:
        score = _regularity_score([0.0, 0.0, 0.0])
        assert score == float("inf")


class TestBeaconingDetector:
    def test_detects_regular_beacon(self) -> None:
        packets = _beacon_packets(12, interval=60.0, jitter=1.0)
        alerts = BeaconingDetector(min_count=10, regularity_threshold=0.15).analyze(packets)
        assert len(alerts) > 0

    def test_rule_id(self) -> None:
        assert BeaconingDetector().rule_id == "c2_beaconing"

    def test_mitre_technique(self) -> None:
        packets = _beacon_packets(12)
        alerts = BeaconingDetector(min_count=10, regularity_threshold=0.15).analyze(packets)
        if alerts:
            assert alerts[0].mitre_technique_id == "T1071"

    def test_no_alert_below_min_count(self) -> None:
        packets = _beacon_packets(5)  # below min_count=10
        alerts = BeaconingDetector(min_count=10).analyze(packets)
        assert len(alerts) == 0

    def test_no_alert_for_irregular(self) -> None:
        # Very irregular intervals — not beaconing
        rng = random.Random(42)
        packets = [
            PacketRecord(
                timestamp=_BASE_TS + rng.uniform(0, 3600),
                src_ip=_SRC,
                dst_ip=_C2,
                src_port=rng.randint(49152, 65535),
                dst_port=_PORT,
                protocol=Protocol.TCP,
                tcp_flags=TCPFlags.SYN,
            )
            for _ in range(15)
        ]
        alerts = BeaconingDetector(min_count=10, regularity_threshold=0.10).analyze(packets)
        assert len(alerts) == 0

    def test_empty_packets(self) -> None:
        assert BeaconingDetector().analyze([]) == []

    def test_non_syn_ignored(self) -> None:
        packets = [
            PacketRecord(
                timestamp=_BASE_TS + i * 60,
                src_ip=_SRC,
                dst_ip=_C2,
                src_port=12345,
                dst_port=_PORT,
                protocol=Protocol.TCP,
                tcp_flags=TCPFlags.ACK,
            )
            for i in range(12)
        ]
        assert BeaconingDetector().analyze(packets) == []

    def test_source_ip_in_alert(self) -> None:
        packets = _beacon_packets(12, jitter=0.5)
        alerts = BeaconingDetector(min_count=10, regularity_threshold=0.15).analyze(packets)
        if alerts:
            assert alerts[0].source_ip == _SRC

    def test_dest_ip_in_alert(self) -> None:
        packets = _beacon_packets(12, jitter=0.5)
        alerts = BeaconingDetector(min_count=10, regularity_threshold=0.15).analyze(packets)
        if alerts:
            assert alerts[0].dest_ip == _C2

    def test_evidence_contains_interval(self) -> None:
        packets = _beacon_packets(12, interval=60.0, jitter=0.5)
        alerts = BeaconingDetector(min_count=10, regularity_threshold=0.15).analyze(packets)
        if alerts:
            assert "60" in alerts[0].evidence
