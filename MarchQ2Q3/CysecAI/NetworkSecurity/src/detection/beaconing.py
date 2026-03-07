"""C2 beaconing detector — periodic outbound connections (MITRE T1071)."""

from __future__ import annotations

import datetime
import statistics
from collections import defaultdict

from src.detection.base import BaseDetector
from src.models import AlertSeverity, NetworkAlert, PacketRecord, Protocol, TCPFlags

_MIN_COUNT = 10
_REGULARITY_THRESHOLD = 0.15  # std_dev / mean


def _regularity_score(intervals: list[float]) -> float:
    """Return coefficient of variation (std_dev / mean). Lower = more regular."""
    if len(intervals) < 2:
        return float("inf")
    mean = statistics.mean(intervals)
    if mean == 0:
        return float("inf")
    return statistics.stdev(intervals) / mean


class BeaconingDetector(BaseDetector):
    """Detects C2 beaconing by identifying periodic connection patterns."""

    def __init__(
        self,
        min_count: int = _MIN_COUNT,
        regularity_threshold: float = _REGULARITY_THRESHOLD,
    ) -> None:
        self._min_count = min_count
        self._regularity = regularity_threshold

    @property
    def rule_id(self) -> str:
        return "c2_beaconing"

    def analyze(self, packets: list[PacketRecord]) -> list[NetworkAlert]:
        # Group SYN packets by (src_ip, dst_ip, dst_port) — each new connection
        # key → list of timestamps
        groups: dict[tuple[str, str, int], list[float]] = defaultdict(list)
        for pkt in packets:
            if pkt.protocol != Protocol.TCP:
                continue
            if pkt.tcp_flags != TCPFlags.SYN:
                continue
            if pkt.dst_port is None:
                continue
            key = (pkt.src_ip, pkt.dst_ip, pkt.dst_port)
            groups[key].append(pkt.timestamp)

        alerts: list[NetworkAlert] = []
        for (src_ip, dst_ip, dst_port), timestamps in groups.items():
            if len(timestamps) < self._min_count:
                continue
            sorted_ts = sorted(timestamps)
            intervals = [sorted_ts[i + 1] - sorted_ts[i] for i in range(len(sorted_ts) - 1)]
            score = _regularity_score(intervals)
            if score <= self._regularity:
                mean_interval = statistics.mean(intervals)
                ts = datetime.datetime.fromtimestamp(sorted_ts[0], tz=datetime.UTC)
                alerts.append(
                    NetworkAlert(
                        rule_id=self.rule_id,
                        title="C2 Beaconing Detected",
                        severity=AlertSeverity.HIGH,
                        mitre_technique_id="T1071",
                        source_ip=src_ip,
                        dest_ip=dst_ip,
                        timestamp=ts,
                        evidence=(
                            f"{len(timestamps)} connections to {dst_ip}:{dst_port} "
                            f"with mean interval {mean_interval:.1f}s "
                            f"(regularity score {score:.3f})"
                        ),
                        packet_count=len(timestamps),
                    )
                )
        return alerts
