"""Brute-force login detector — SSH, FTP, HTTP (MITRE T1110)."""

from __future__ import annotations

import datetime
from collections import defaultdict

from src.detection.base import BaseDetector
from src.models import AlertSeverity, NetworkAlert, PacketRecord, Protocol, TCPFlags

_WINDOW_S = 300  # 5 minutes
_THRESHOLD = 10  # failed connections

_AUTH_PORTS = frozenset({21, 22, 23, 80, 443, 3389, 5900})
_PORT_LABELS = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    80: "HTTP",
    443: "HTTPS",
    3389: "RDP",
    5900: "VNC",
}

# Protocols that carry TCP-style RST semantics for auth services
_AUTH_PROTOCOLS = frozenset({Protocol.TCP, Protocol.SSH, Protocol.FTP, Protocol.TELNET})


def _is_failed_connection(pkt: PacketRecord) -> bool:
    """Heuristic: RST flag on an auth-capable protocol = failed auth."""
    return pkt.protocol in _AUTH_PROTOCOLS and pkt.tcp_flags == TCPFlags.RST


class BruteForceDetector(BaseDetector):
    """Detects repeated failed connections to auth services."""

    def __init__(self, threshold: int = _THRESHOLD, window_s: int = _WINDOW_S) -> None:
        self._threshold = threshold
        self._window_s = window_s

    @property
    def rule_id(self) -> str:
        return "brute_force"

    def analyze(self, packets: list[PacketRecord]) -> list[NetworkAlert]:
        # Group RST packets by (src_ip, dst_port) for known auth ports
        # src_ip + dst_port → list of timestamps
        groups: dict[tuple[str, int], list[float]] = defaultdict(list)
        for pkt in packets:
            if not _is_failed_connection(pkt):
                continue
            if pkt.dst_port not in _AUTH_PORTS:
                continue
            groups[(pkt.src_ip, pkt.dst_port)].append(pkt.timestamp)

        alerts: list[NetworkAlert] = []
        for (src_ip, dst_port), timestamps in groups.items():
            sorted_ts = sorted(timestamps)
            # Find the maximum number of failures within any rolling window
            start = 0
            max_count = 0
            max_start_idx = 0
            for end in range(len(sorted_ts)):
                while sorted_ts[end] - sorted_ts[start] > self._window_s:
                    start += 1
                count = end - start + 1
                if count > max_count:
                    max_count = count
                    max_start_idx = start
            if max_count >= self._threshold:
                ts = datetime.datetime.fromtimestamp(
                    sorted_ts[max_start_idx], tz=datetime.UTC
                )
                service = _PORT_LABELS.get(dst_port, f"port/{dst_port}")
                alerts.append(
                    NetworkAlert(
                        rule_id=self.rule_id,
                        title=f"Brute Force — {service}",
                        severity=AlertSeverity.HIGH,
                        mitre_technique_id="T1110",
                        source_ip=src_ip,
                        timestamp=ts,
                        evidence=(
                            f"{max_count} failed {service} connections within {self._window_s}s"
                        ),
                        packet_count=max_count,
                    )
                )
        return alerts
