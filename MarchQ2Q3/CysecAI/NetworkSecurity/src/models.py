"""Core data models for network security monitoring."""

from __future__ import annotations

import datetime
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AlertSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Protocol(StrEnum):
    TCP = "TCP"
    UDP = "UDP"
    ICMP = "ICMP"
    ARP = "ARP"
    DNS = "DNS"
    HTTP = "HTTP"
    FTP = "FTP"
    TELNET = "TELNET"
    SSH = "SSH"
    UNKNOWN = "UNKNOWN"


class TCPFlags(StrEnum):
    SYN = "SYN"
    FIN = "FIN"
    RST = "RST"
    ACK = "ACK"
    SYN_ACK = "SYN-ACK"
    PSH_ACK = "PSH-ACK"
    FIN_ACK = "FIN-ACK"
    XMAS = "XMAS"  # FIN + PSH + URG


class PacketRecord(BaseModel):
    """Normalised representation of a single network packet."""

    timestamp: float
    src_ip: str
    dst_ip: str
    src_port: int | None = None
    dst_port: int | None = None
    protocol: Protocol = Protocol.UNKNOWN
    tcp_flags: TCPFlags | None = None
    payload_size: int = 0
    # DNS fields
    dns_query: str | None = None
    dns_response: str | None = None
    # HTTP fields
    http_method: str | None = None
    http_url: str | None = None
    http_host: str | None = None
    http_auth_header: str | None = None  # stored redacted
    # FTP fields
    ftp_command: str | None = None  # USER, PASS (arg redacted)
    ftp_arg: str | None = None  # redacted for PASS commands
    # ARP fields
    arp_sender_mac: str | None = None
    arp_sender_ip: str | None = None
    arp_target_mac: str | None = None


class CloudEvent(BaseModel):
    """Normalised cloud log event (CloudTrail / VPC flow / K8s audit)."""

    timestamp: datetime.datetime
    event_source: str  # "cloudtrail" | "vpc_flow" | "k8s_audit"
    event_name: str | None = None
    source_ip: str | None = None
    user_identity: str | None = None
    error_code: str | None = None
    # VPC flow
    src_addr: str | None = None
    dst_addr: str | None = None
    src_port: int | None = None
    dst_port: int | None = None
    action: str | None = None  # "ACCEPT" | "REJECT"
    bytes_transferred: int = 0
    # K8s audit
    verb: str | None = None
    resource: str | None = None
    namespace: str | None = None
    response_code: int | None = None
    privileged: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)


class NetworkAlert(BaseModel):
    """A security alert raised by a detector."""

    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str
    title: str
    severity: AlertSeverity
    mitre_technique_id: str
    source_ip: str
    dest_ip: str | None = None
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    evidence: str
    packet_count: int = 0
    extra: dict[str, Any] = Field(default_factory=dict)
