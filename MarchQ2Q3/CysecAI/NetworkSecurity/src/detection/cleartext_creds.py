"""Cleartext credentials detector — HTTP Basic auth, FTP PASS, Telnet (MITRE T1552.001)."""

from __future__ import annotations

import datetime

from src.detection.base import BaseDetector
from src.models import AlertSeverity, NetworkAlert, PacketRecord, Protocol


class CleartextCredsDetector(BaseDetector):
    """Detects credentials transmitted in cleartext over the wire."""

    @property
    def rule_id(self) -> str:
        return "cleartext_creds"

    def analyze(self, packets: list[PacketRecord]) -> list[NetworkAlert]:
        alerts: list[NetworkAlert] = []
        seen: set[tuple[str, str, int | None]] = set()
        for pkt in packets:
            alert = self._check_packet(pkt)
            if alert is None:
                continue
            dedup_key = (pkt.src_ip, pkt.dst_ip, pkt.dst_port)
            if dedup_key not in seen:
                seen.add(dedup_key)
                alerts.append(alert)
        return alerts

    def _check_packet(self, pkt: PacketRecord) -> NetworkAlert | None:
        ts = datetime.datetime.fromtimestamp(pkt.timestamp, tz=datetime.UTC)
        # HTTP Basic auth
        if pkt.protocol == Protocol.HTTP and pkt.http_auth_header is not None:
            return NetworkAlert(
                rule_id=self.rule_id,
                title="Cleartext HTTP Basic Auth",
                severity=AlertSeverity.HIGH,
                mitre_technique_id="T1552.001",
                source_ip=pkt.src_ip,
                dest_ip=pkt.dst_ip,
                timestamp=ts,
                evidence=(
                    f"HTTP Basic auth on {pkt.http_host or pkt.dst_ip}:{pkt.dst_port}: "
                    f"{pkt.http_auth_header}"
                ),
            )
        # FTP PASS command
        if pkt.protocol == Protocol.FTP and pkt.ftp_command == "PASS":
            return NetworkAlert(
                rule_id=self.rule_id,
                title="Cleartext FTP Password",
                severity=AlertSeverity.HIGH,
                mitre_technique_id="T1552.001",
                source_ip=pkt.src_ip,
                dest_ip=pkt.dst_ip,
                timestamp=ts,
                evidence=f"FTP PASS command (arg redacted) to {pkt.dst_ip}:{pkt.dst_port}",
            )
        # Telnet traffic (any payload = potential cleartext)
        if pkt.protocol == Protocol.TELNET and pkt.payload_size > 0:
            return NetworkAlert(
                rule_id=self.rule_id,
                title="Cleartext Telnet Session",
                severity=AlertSeverity.MEDIUM,
                mitre_technique_id="T1552.001",
                source_ip=pkt.src_ip,
                dest_ip=pkt.dst_ip,
                timestamp=ts,
                evidence=f"Telnet traffic to {pkt.dst_ip}:{pkt.dst_port} ({pkt.payload_size}B)",
            )
        return None
