"""Tests for the ARP spoofing detector."""

from __future__ import annotations

from src.detection.arp_spoof import ARPSpoofDetector
from src.models import PacketRecord, Protocol

_BASE_TS = 1735689600.0


def _arp(ts: float, src_ip: str, mac: str) -> PacketRecord:
    return PacketRecord(
        timestamp=ts,
        src_ip=src_ip,
        dst_ip="10.0.0.255",
        protocol=Protocol.ARP,
        arp_sender_mac=mac,
        arp_sender_ip=src_ip,
    )


class TestARPSpoofDetector:
    def test_detects_duplicate_mac(self) -> None:
        packets = [
            _arp(_BASE_TS, "10.0.0.1", "aa:bb:cc:dd:ee:ff"),
            _arp(_BASE_TS + 1, "10.0.0.1", "11:22:33:44:55:66"),
        ]
        alerts = ARPSpoofDetector().analyze(packets)
        assert len(alerts) == 1

    def test_rule_id(self) -> None:
        assert ARPSpoofDetector().rule_id == "arp_spoof"

    def test_mitre_technique(self) -> None:
        packets = [
            _arp(_BASE_TS, "10.0.0.1", "aa:bb:cc:dd:ee:ff"),
            _arp(_BASE_TS + 1, "10.0.0.1", "11:22:33:44:55:66"),
        ]
        alerts = ARPSpoofDetector().analyze(packets)
        assert alerts[0].mitre_technique_id == "T1557.002"

    def test_single_mac_no_alert(self) -> None:
        packets = [
            _arp(_BASE_TS, "10.0.0.1", "aa:bb:cc:dd:ee:ff"),
            _arp(_BASE_TS + 1, "10.0.0.1", "aa:bb:cc:dd:ee:ff"),  # same MAC
        ]
        assert ARPSpoofDetector().analyze(packets) == []

    def test_different_ips_no_alert(self) -> None:
        packets = [
            _arp(_BASE_TS, "10.0.0.1", "aa:bb:cc:dd:ee:ff"),
            _arp(_BASE_TS + 1, "10.0.0.2", "11:22:33:44:55:66"),
        ]
        assert ARPSpoofDetector().analyze(packets) == []

    def test_evidence_contains_macs(self) -> None:
        packets = [
            _arp(_BASE_TS, "10.0.0.1", "aa:bb:cc:dd:ee:ff"),
            _arp(_BASE_TS + 1, "10.0.0.1", "11:22:33:44:55:66"),
        ]
        alerts = ARPSpoofDetector().analyze(packets)
        ev = alerts[0].evidence
        assert "aa:bb:cc:dd:ee:ff" in ev or "11:22:33:44:55:66" in ev

    def test_non_arp_ignored(self) -> None:
        packets = [
            PacketRecord(
                timestamp=_BASE_TS, src_ip="10.0.0.1", dst_ip="10.0.0.2", protocol=Protocol.TCP
            ),
        ]
        assert ARPSpoofDetector().analyze(packets) == []

    def test_empty_packets(self) -> None:
        assert ARPSpoofDetector().analyze([]) == []

    def test_missing_mac_skipped(self) -> None:
        # Packet with no arp_sender_mac set
        packets = [
            PacketRecord(
                timestamp=_BASE_TS, src_ip="10.0.0.1", dst_ip="10.0.0.255", protocol=Protocol.ARP
            ),
        ]
        assert ARPSpoofDetector().analyze(packets) == []

    def test_source_ip_is_victim_ip(self) -> None:
        packets = [
            _arp(_BASE_TS, "10.0.0.5", "aa:bb:cc:dd:ee:ff"),
            _arp(_BASE_TS + 1, "10.0.0.5", "11:22:33:44:55:66"),
        ]
        alerts = ARPSpoofDetector().analyze(packets)
        assert alerts[0].source_ip == "10.0.0.5"
