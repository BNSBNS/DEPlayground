"""Tests for the cleartext credentials detector."""

from __future__ import annotations

from src.detection.cleartext_creds import CleartextCredsDetector
from src.models import PacketRecord, Protocol

_BASE_TS = 1735689600.0
_SRC = "10.0.0.20"
_DST = "10.0.0.100"


def _http_auth_pkt(ts: float = _BASE_TS) -> PacketRecord:
    return PacketRecord(
        timestamp=ts,
        src_ip=_SRC,
        dst_ip=_DST,
        src_port=54321,
        dst_port=80,
        protocol=Protocol.HTTP,
        http_method="GET",
        http_url="/admin",
        http_host=_DST,
        http_auth_header="Basic admin:[REDACTED]",
        payload_size=200,
    )


def _ftp_pass_pkt(ts: float = _BASE_TS) -> PacketRecord:
    return PacketRecord(
        timestamp=ts,
        src_ip=_SRC,
        dst_ip=_DST,
        src_port=54322,
        dst_port=21,
        protocol=Protocol.FTP,
        ftp_command="PASS",
        ftp_arg="[REDACTED]",
        payload_size=20,
    )


def _telnet_pkt(ts: float = _BASE_TS) -> PacketRecord:
    return PacketRecord(
        timestamp=ts,
        src_ip=_SRC,
        dst_ip=_DST,
        src_port=54323,
        dst_port=23,
        protocol=Protocol.TELNET,
        payload_size=50,
    )


class TestCleartextCredsDetector:
    def test_detects_http_basic_auth(self) -> None:
        alerts = CleartextCredsDetector().analyze([_http_auth_pkt()])
        assert len(alerts) == 1
        assert "HTTP" in alerts[0].title

    def test_detects_ftp_pass(self) -> None:
        alerts = CleartextCredsDetector().analyze([_ftp_pass_pkt()])
        assert len(alerts) == 1
        assert "FTP" in alerts[0].title

    def test_detects_telnet(self) -> None:
        alerts = CleartextCredsDetector().analyze([_telnet_pkt()])
        assert len(alerts) == 1
        assert "Telnet" in alerts[0].title

    def test_rule_id(self) -> None:
        assert CleartextCredsDetector().rule_id == "cleartext_creds"

    def test_mitre_technique(self) -> None:
        alerts = CleartextCredsDetector().analyze([_http_auth_pkt()])
        assert alerts[0].mitre_technique_id == "T1552.001"

    def test_no_auth_no_alert(self) -> None:
        pkt = PacketRecord(
            timestamp=_BASE_TS,
            src_ip=_SRC,
            dst_ip=_DST,
            dst_port=80,
            protocol=Protocol.HTTP,
            http_method="GET",
            http_url="/public",
            payload_size=100,
        )
        assert CleartextCredsDetector().analyze([pkt]) == []

    def test_ftp_user_no_alert(self) -> None:
        # FTP USER command is not a credential leak (PASS is)
        pkt = PacketRecord(
            timestamp=_BASE_TS,
            src_ip=_SRC,
            dst_ip=_DST,
            dst_port=21,
            protocol=Protocol.FTP,
            ftp_command="USER",
            ftp_arg="admin",
        )
        assert CleartextCredsDetector().analyze([pkt]) == []

    def test_telnet_empty_payload_no_alert(self) -> None:
        pkt = _telnet_pkt()
        pkt = pkt.model_copy(update={"payload_size": 0})
        assert CleartextCredsDetector().analyze([pkt]) == []

    def test_dedup_same_src_dst_port(self) -> None:
        # Two HTTP auth packets to same host → deduplicated to 1 alert
        alerts = CleartextCredsDetector().analyze([_http_auth_pkt(), _http_auth_pkt(_BASE_TS + 1)])
        assert len(alerts) == 1

    def test_different_dst_not_deduped(self) -> None:
        pkt1 = _http_auth_pkt()
        pkt2 = _http_auth_pkt(_BASE_TS + 1)
        pkt2 = pkt2.model_copy(update={"dst_ip": "10.0.0.200"})
        alerts = CleartextCredsDetector().analyze([pkt1, pkt2])
        assert len(alerts) == 2

    def test_empty_packets(self) -> None:
        assert CleartextCredsDetector().analyze([]) == []

    def test_evidence_contains_host(self) -> None:
        alerts = CleartextCredsDetector().analyze([_http_auth_pkt()])
        assert _DST in alerts[0].evidence
