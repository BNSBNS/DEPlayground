"""Tests for multi-format log parser (Phase 2)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from src.ingestion.log_parser import ParseError, parse_cef, parse_json, parse_log_line, parse_syslog


class TestAutoDetect:
    """parse_log_line auto-detection tests."""

    def test_detects_json(self) -> None:
        line = json.dumps({"event_type": "login_success", "user": "admin"})
        result = parse_log_line(line)
        assert result["event_type"] == "login_success"

    def test_detects_cef(self) -> None:
        line = "CEF:0|Vendor|Product|1.0|100|Login|3|src=10.0.0.1 dst=10.0.0.2"
        result = parse_log_line(line)
        assert result["source"] == "cef"

    def test_detects_syslog(self) -> None:
        line = "Jun 15 14:30:00 webserver sshd[12345]: Accepted password for admin from 10.0.0.1"
        result = parse_log_line(line)
        assert result["source"] == "syslog"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ParseError, match="Empty"):
            parse_log_line("")

    def test_rejects_unknown_format(self) -> None:
        with pytest.raises(ParseError, match="Unrecognized"):
            parse_log_line("this is not a valid log format at all")


class TestJsonParser:
    """JSON log parser tests."""

    def test_parses_simple_json(self) -> None:
        data = {"event_type": "dns_query", "src_ip": "10.0.0.1", "details": {"query": "google.com"}}
        result = parse_json(json.dumps(data))
        assert result["event_type"] == "dns_query"
        assert result["details"]["query"] == "google.com"

    def test_rejects_invalid_json(self) -> None:
        with pytest.raises(ParseError, match="Invalid JSON"):
            parse_json("{broken")

    def test_rejects_non_object_json(self) -> None:
        with pytest.raises(ParseError, match="must be an object"):
            parse_json("[1, 2, 3]")

    def test_preserves_all_fields(self) -> None:
        data = {"a": 1, "b": "two", "c": [3], "d": {"nested": True}}
        result = parse_json(json.dumps(data))
        assert result == data


class TestSyslogParser:
    """Syslog (RFC 3164) parser tests."""

    def test_parses_ssh_success(self) -> None:
        line = "Jun 15 14:30:00 webserver sshd[12345]: Accepted password for admin from 10.0.0.1"
        result = parse_syslog(line)
        assert result["hostname"] == "webserver"
        assert result["process"] == "sshd"
        assert result["pid"] == "12345"
        assert result["event_type"] == "login_success"

    def test_parses_ssh_failure(self) -> None:
        line = "Jun 15 14:30:00 webserver sshd[12345]: Failed password for root from 10.0.0.5"
        result = parse_syslog(line)
        assert result["event_type"] == "login_failure"

    def test_parses_with_priority(self) -> None:
        line = "<34>Jun 15 14:30:00 firewall kernel: iptables DROP IN=eth0"
        result = parse_syslog(line)
        assert result["hostname"] == "firewall"
        assert result["event_type"] == "firewall_event"

    def test_timestamp_has_utc(self) -> None:
        line = "Jun 15 14:30:00 host app: test message"
        result = parse_syslog(line)
        ts = datetime.fromisoformat(result["timestamp"])
        assert ts.tzinfo == UTC

    def test_rejects_invalid_syslog(self) -> None:
        with pytest.raises(ParseError, match="Invalid syslog"):
            parse_syslog("not a syslog line")

    def test_classifies_sudo(self) -> None:
        line = "Jun 15 14:30:00 host sudo[999]: session opened for user root"
        result = parse_syslog(line)
        assert result["event_type"] == "login_success"

    def test_classifies_dns(self) -> None:
        line = "Jun 15 14:30:00 dns named[123]: query: google.com A"
        result = parse_syslog(line)
        assert result["event_type"] == "dns_event"


class TestCefParser:
    """CEF (Common Event Format) parser tests."""

    def test_parses_basic_cef(self) -> None:
        line = (
            "CEF:0|SecurityVendor|Firewall|1.0|100|Connection Allowed|3|"
            "src=10.0.0.1 dst=192.168.1.1"
        )
        result = parse_cef(line)
        assert result["source"] == "cef"
        assert result["event_type"] == "Connection Allowed"
        assert result["src_ip"] == "10.0.0.1"
        assert result["dst_ip"] == "192.168.1.1"

    def test_severity_mapping_critical(self) -> None:
        line = "CEF:0|V|P|1|1|Event|10|src=10.0.0.1"
        result = parse_cef(line)
        assert result["severity"] == "critical"

    def test_severity_mapping_high(self) -> None:
        line = "CEF:0|V|P|1|1|Event|8|src=10.0.0.1"
        result = parse_cef(line)
        assert result["severity"] == "high"

    def test_severity_mapping_medium(self) -> None:
        line = "CEF:0|V|P|1|1|Event|5|src=10.0.0.1"
        result = parse_cef(line)
        assert result["severity"] == "medium"

    def test_severity_mapping_low(self) -> None:
        line = "CEF:0|V|P|1|1|Event|2|src=10.0.0.1"
        result = parse_cef(line)
        assert result["severity"] == "low"

    def test_severity_mapping_info(self) -> None:
        line = "CEF:0|V|P|1|1|Event|0|src=10.0.0.1"
        result = parse_cef(line)
        assert result["severity"] == "info"

    def test_parses_user_field(self) -> None:
        line = "CEF:0|V|P|1|1|Login|3|suser=admin src=10.0.0.1"
        result = parse_cef(line)
        assert result["user"] == "admin"

    def test_parses_action(self) -> None:
        line = "CEF:0|V|P|1|1|Event|3|act=deny src=10.0.0.1"
        result = parse_cef(line)
        assert result["action"] == "deny"

    def test_rejects_invalid_cef(self) -> None:
        with pytest.raises(ParseError, match="Invalid CEF"):
            parse_cef("CEF:bad format")

    def test_empty_extension(self) -> None:
        line = "CEF:0|V|P|1|1|Event|3|"
        result = parse_cef(line)
        assert result["event_type"] == "Event"

    def test_text_severity(self) -> None:
        line = "CEF:0|V|P|1|1|Event|High|src=10.0.0.1"
        result = parse_cef(line)
        assert result["severity"] == "high"
