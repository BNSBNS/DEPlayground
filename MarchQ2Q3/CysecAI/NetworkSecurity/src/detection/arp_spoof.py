"""ARP spoofing detector — duplicate IP-to-MAC mappings (MITRE T1557.002)."""

from __future__ import annotations

import datetime
from collections import defaultdict

from src.detection.base import BaseDetector
from src.models import AlertSeverity, NetworkAlert, PacketRecord, Protocol


class ARPSpoofDetector(BaseDetector):
    """Detects ARP spoofing by tracking IP → MAC mappings."""

    @property
    def rule_id(self) -> str:
        return "arp_spoof"

    def analyze(self, packets: list[PacketRecord]) -> list[NetworkAlert]:
        # ip → set of MACs seen
        ip_to_macs: dict[str, set[str]] = defaultdict(set)
        ip_to_first: dict[str, float] = {}
        for pkt in packets:
            if pkt.protocol != Protocol.ARP:
                continue
            if pkt.arp_sender_ip is None or pkt.arp_sender_mac is None:
                continue
            ip = pkt.arp_sender_ip
            mac = pkt.arp_sender_mac
            ip_to_macs[ip].add(mac)
            if ip not in ip_to_first:
                ip_to_first[ip] = pkt.timestamp

        alerts: list[NetworkAlert] = []
        for ip, macs in ip_to_macs.items():
            if len(macs) > 1:
                ts = datetime.datetime.fromtimestamp(ip_to_first.get(ip, 0.0), tz=datetime.UTC)
                mac_list = ", ".join(sorted(macs))
                alerts.append(
                    NetworkAlert(
                        rule_id=self.rule_id,
                        title="ARP Spoofing Detected",
                        severity=AlertSeverity.HIGH,
                        mitre_technique_id="T1557.002",
                        source_ip=ip,
                        timestamp=ts,
                        evidence=f"IP {ip} announced from {len(macs)} different MACs: {mac_list}",
                        packet_count=len(macs),
                    )
                )
        return alerts
