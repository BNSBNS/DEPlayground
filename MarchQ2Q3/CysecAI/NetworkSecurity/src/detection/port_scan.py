"""Port scan detector — SYN, FIN, and XMAS scan detection (MITRE T1046)."""

from __future__ import annotations

import datetime
from collections import defaultdict

from src.detection.base import BaseDetector
from src.models import AlertSeverity, NetworkAlert, PacketRecord, Protocol, TCPFlags

_WINDOW_S = 60
_THRESHOLD = 20  # unique destination ports


class PortScanDetector(BaseDetector):
    """Detects SYN, FIN, and XMAS port scans."""

    def __init__(self, threshold: int = _THRESHOLD, window_s: int = _WINDOW_S) -> None:
        self._threshold = threshold
        self._window_s = window_s

    @property
    def rule_id(self) -> str:
        return "port_scan"

    def analyze(self, packets: list[PacketRecord]) -> list[NetworkAlert]:
        # Group TCP SYN/FIN/XMAS packets by src_ip within rolling window
        alerts: list[NetworkAlert] = []
        alerts.extend(self._scan_type(packets, TCPFlags.SYN, "SYN", AlertSeverity.HIGH))
        alerts.extend(self._scan_type(packets, TCPFlags.FIN, "FIN", AlertSeverity.MEDIUM))
        alerts.extend(self._scan_type(packets, TCPFlags.XMAS, "XMAS", AlertSeverity.MEDIUM))
        return alerts

    def _scan_type(
        self,
        packets: list[PacketRecord],
        flag: TCPFlags,
        label: str,
        severity: AlertSeverity,
    ) -> list[NetworkAlert]:
        # Collect (timestamp, dst_ip, dst_port) for packets with the given flag
        # src_ip → list of (ts, dst_ip, dst_port)
        candidates: dict[str, list[tuple[float, str, int]]] = defaultdict(list)
        for pkt in packets:
            if pkt.protocol != Protocol.TCP:
                continue
            if pkt.tcp_flags != flag:
                continue
            if pkt.dst_port is None:
                continue
            candidates[pkt.src_ip].append((pkt.timestamp, pkt.dst_ip, pkt.dst_port))

        alerts: list[NetworkAlert] = []
        for src_ip, events in candidates.items():
            events_sorted = sorted(events, key=lambda e: e[0])
            # Sliding window
            start = 0
            for end in range(len(events_sorted)):
                while events_sorted[end][0] - events_sorted[start][0] > self._window_s:
                    start += 1
                window = events_sorted[start : end + 1]
                unique_ports = {e[2] for e in window}
                if len(unique_ports) >= self._threshold:
                    target = window[0][1]
                    ts = datetime.datetime.fromtimestamp(window[0][0], tz=datetime.UTC)
                    alerts.append(
                        NetworkAlert(
                            rule_id=f"port_scan_{flag.lower()}",
                            title=f"{label} Port Scan Detected",
                            severity=severity,
                            mitre_technique_id="T1046",
                            source_ip=src_ip,
                            dest_ip=target,
                            timestamp=ts,
                            evidence=(
                                f"{label} scan: {len(unique_ports)} unique ports probed "
                                f"within {self._window_s}s "
                                f"(ports {sorted(unique_ports)[:5]}...)"
                            ),
                            packet_count=len(window),
                        )
                    )
                    break  # one alert per source in this scan type
        return alerts
