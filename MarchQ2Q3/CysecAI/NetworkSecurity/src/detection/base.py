"""BaseDetector abstract class for all network threat detectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import CloudEvent, NetworkAlert, PacketRecord


class BaseDetector(ABC):
    """Abstract base for packet-level threat detectors."""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique rule identifier, e.g. 'port_scan_syn'."""

    @abstractmethod
    def analyze(self, packets: list[PacketRecord]) -> list[NetworkAlert]:
        """Analyze a sequence of packets and return any alerts raised."""


class BaseCloudDetector(ABC):
    """Abstract base for cloud log threat detectors."""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique rule identifier, e.g. 'k8s_privileged_container'."""

    @abstractmethod
    def analyze(self, events: list[CloudEvent]) -> list[NetworkAlert]:
        """Analyze a sequence of cloud events and return any alerts raised."""
