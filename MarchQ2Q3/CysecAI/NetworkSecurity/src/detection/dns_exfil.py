"""DNS exfiltration detector (MITRE T1048.003)."""

from __future__ import annotations

import datetime
import math
from collections import Counter, defaultdict

from src.detection.base import BaseDetector
from src.models import AlertSeverity, NetworkAlert, PacketRecord, Protocol

_SUBDOMAIN_LEN_THRESHOLD = 30
_ENTROPY_THRESHOLD = 4.0
_VOLUME_PER_MINUTE = 100
_VOLUME_WINDOW_S = 60


def _extract_subdomain(query: str) -> str:
    """Return the leftmost label of a DNS query (the encoded data part)."""
    return query.split(".", maxsplit=1)[0] if "." in query else query


def shannon_entropy(text: str) -> float:
    """Calculate Shannon entropy of a string (bits per character)."""
    if not text:
        return 0.0
    counts = Counter(text.lower())
    total = len(text)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


class DNSExfilDetector(BaseDetector):
    """Detects DNS exfiltration via long subdomains, high entropy, and volume."""

    def __init__(
        self,
        subdomain_len_threshold: int = _SUBDOMAIN_LEN_THRESHOLD,
        entropy_threshold: float = _ENTROPY_THRESHOLD,
        volume_per_minute: int = _VOLUME_PER_MINUTE,
    ) -> None:
        self._subdomain_len = subdomain_len_threshold
        self._entropy = entropy_threshold
        self._volume = volume_per_minute

    @property
    def rule_id(self) -> str:
        return "dns_exfil"

    def analyze(self, packets: list[PacketRecord]) -> list[NetworkAlert]:
        alerts: list[NetworkAlert] = []
        # Collect DNS queries per source IP
        src_queries: dict[str, list[tuple[float, str]]] = defaultdict(list)
        for pkt in packets:
            if pkt.protocol != Protocol.DNS:
                continue
            if pkt.dns_query is None:
                continue
            src_queries[pkt.src_ip].append((pkt.timestamp, pkt.dns_query))

        seen_sources: set[str] = set()
        for src_ip, queries in src_queries.items():
            for ts_float, query in queries:
                sub = _extract_subdomain(query)
                triggers: list[str] = []
                # Check subdomain length
                if len(sub) >= self._subdomain_len:
                    triggers.append(f"subdomain length {len(sub)}")
                # Check entropy
                ent = shannon_entropy(sub)
                if ent >= self._entropy:
                    triggers.append(f"entropy {ent:.2f}")
                if triggers and src_ip not in seen_sources:
                    ts = datetime.datetime.fromtimestamp(ts_float, tz=datetime.UTC)
                    seen_sources.add(src_ip)
                    alerts.append(
                        NetworkAlert(
                            rule_id=self.rule_id,
                            title="DNS Exfiltration Detected",
                            severity=AlertSeverity.HIGH,
                            mitre_technique_id="T1048.003",
                            source_ip=src_ip,
                            timestamp=ts,
                            evidence=(f"Suspicious DNS query '{query}': {'; '.join(triggers)}"),
                            packet_count=1,
                        )
                    )
            # Check volume
            if src_ip not in seen_sources:
                timestamps = sorted(q[0] for q in queries)
                if self._volume_exceeded(timestamps):
                    ts = datetime.datetime.fromtimestamp(timestamps[0], tz=datetime.UTC)
                    seen_sources.add(src_ip)
                    alerts.append(
                        NetworkAlert(
                            rule_id=self.rule_id,
                            title="DNS Exfiltration Detected",
                            severity=AlertSeverity.MEDIUM,
                            mitre_technique_id="T1048.003",
                            source_ip=src_ip,
                            timestamp=ts,
                            evidence=f"High DNS query volume: {len(timestamps)} queries/min",
                            packet_count=len(timestamps),
                        )
                    )
        return alerts

    def _volume_exceeded(self, timestamps: list[float]) -> bool:
        """Return True if any 60s window contains ≥ volume_per_minute queries."""
        if len(timestamps) < self._volume:
            return False
        start = 0
        for end in range(len(timestamps)):
            while timestamps[end] - timestamps[start] > _VOLUME_WINDOW_S:
                start += 1
            if end - start + 1 >= self._volume:
                return True
        return False
