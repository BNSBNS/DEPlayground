"""Tests for the JSON packet loader."""

from __future__ import annotations

import json
import pathlib
import tempfile

import pydantic
import pytest

from src.models import Protocol, TCPFlags
from src.parser.json_loader import load_packets, load_packets_from_list

_BASE_TS = 1735689600.0

_SAMPLE_PACKETS = [
    {
        "timestamp": _BASE_TS,
        "src_ip": "10.0.0.1",
        "dst_ip": "10.0.0.2",
        "src_port": 54321,
        "dst_port": 80,
        "protocol": "HTTP",
        "tcp_flags": "PSH-ACK",
        "payload_size": 500,
        "http_method": "GET",
        "http_url": "/index.html",
    },
    {
        "timestamp": _BASE_TS + 1,
        "src_ip": "10.0.0.1",
        "dst_ip": "8.8.8.8",
        "src_port": 49152,
        "dst_port": 53,
        "protocol": "DNS",
        "dns_query": "example.com",
    },
]


class TestLoadPacketsFromList:
    def test_basic_load(self) -> None:
        packets = load_packets_from_list(_SAMPLE_PACKETS)
        assert len(packets) == 2

    def test_protocol_parsed(self) -> None:
        packets = load_packets_from_list(_SAMPLE_PACKETS)
        assert packets[0].protocol == Protocol.HTTP

    def test_dns_query_preserved(self) -> None:
        packets = load_packets_from_list(_SAMPLE_PACKETS)
        assert packets[1].dns_query == "example.com"

    def test_tcp_flags_parsed(self) -> None:
        packets = load_packets_from_list(_SAMPLE_PACKETS)
        assert packets[0].tcp_flags == TCPFlags.PSH_ACK

    def test_timestamp_preserved(self) -> None:
        packets = load_packets_from_list(_SAMPLE_PACKETS)
        assert packets[0].timestamp == _BASE_TS

    def test_empty_list(self) -> None:
        assert load_packets_from_list([]) == []

    def test_invalid_raises(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            load_packets_from_list([{"timestamp": "bad", "src_ip": None, "dst_ip": None}])


class TestLoadPacketsFromFile:
    def test_load_from_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(_SAMPLE_PACKETS, f)
            path = pathlib.Path(f.name)
        packets = load_packets(path)
        assert len(packets) == 2
        path.unlink()

    def test_load_port_scan_fixture(self) -> None:
        fixture = pathlib.Path("test_data/port_scan.json")
        if fixture.exists():
            packets = load_packets(fixture)
            assert len(packets) == 100
            syn_count = sum(1 for p in packets if p.tcp_flags == TCPFlags.SYN)
            assert syn_count == 100
