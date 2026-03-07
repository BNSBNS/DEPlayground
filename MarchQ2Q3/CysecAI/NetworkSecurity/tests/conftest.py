"""Shared fixtures for NetworkSecurity tests."""

from __future__ import annotations

import pytest

from src.models import PacketRecord, Protocol, TCPFlags

_BASE_TS = 1735689600.0


@pytest.fixture()
def syn_packet() -> PacketRecord:
    return PacketRecord(
        timestamp=_BASE_TS,
        src_ip="192.168.1.100",
        dst_ip="10.0.0.1",
        src_port=54321,
        dst_port=80,
        protocol=Protocol.TCP,
        tcp_flags=TCPFlags.SYN,
    )


@pytest.fixture()
def port_scan_packets() -> list[PacketRecord]:
    """25 SYN packets to different ports — triggers port scan detection."""
    return [
        PacketRecord(
            timestamp=_BASE_TS + i * 0.5,
            src_ip="192.168.1.99",
            dst_ip="10.0.0.1",
            src_port=54321,
            dst_port=i + 1,
            protocol=Protocol.TCP,
            tcp_flags=TCPFlags.SYN,
        )
        for i in range(25)
    ]


@pytest.fixture()
def brute_force_packets() -> list[PacketRecord]:
    """15 RST responses on SSH port — triggers brute force detection."""
    return [
        PacketRecord(
            timestamp=_BASE_TS + i * 5,
            src_ip="203.0.113.5",
            dst_ip="10.0.0.2",
            src_port=50000 + i,
            dst_port=22,
            protocol=Protocol.SSH,
            tcp_flags=TCPFlags.RST,
        )
        for i in range(15)
    ]
