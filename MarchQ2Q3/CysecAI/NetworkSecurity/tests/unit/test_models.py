"""Tests for core data models."""

from __future__ import annotations

import datetime

from src.models import AlertSeverity, CloudEvent, NetworkAlert, PacketRecord, Protocol, TCPFlags


class TestPacketRecord:
    def test_minimal_creation(self) -> None:
        pkt = PacketRecord(timestamp=1000.0, src_ip="1.2.3.4", dst_ip="5.6.7.8")
        assert pkt.src_ip == "1.2.3.4"
        assert pkt.dst_ip == "5.6.7.8"
        assert pkt.protocol == Protocol.UNKNOWN
        assert pkt.payload_size == 0

    def test_tcp_syn(self) -> None:
        pkt = PacketRecord(
            timestamp=1000.0,
            src_ip="1.2.3.4",
            dst_ip="5.6.7.8",
            src_port=54321,
            dst_port=80,
            protocol=Protocol.TCP,
            tcp_flags=TCPFlags.SYN,
        )
        assert pkt.tcp_flags == TCPFlags.SYN
        assert pkt.dst_port == 80

    def test_dns_fields(self) -> None:
        pkt = PacketRecord(
            timestamp=1000.0,
            src_ip="1.2.3.4",
            dst_ip="8.8.8.8",
            src_port=12345,
            dst_port=53,
            protocol=Protocol.DNS,
            dns_query="secret.attacker.com",
        )
        assert pkt.dns_query == "secret.attacker.com"

    def test_http_fields(self) -> None:
        pkt = PacketRecord(
            timestamp=1000.0,
            src_ip="1.2.3.4",
            dst_ip="5.6.7.8",
            protocol=Protocol.HTTP,
            http_method="GET",
            http_url="/api/v1/data",
            http_auth_header="Basic admin:[REDACTED]",
        )
        assert pkt.http_method == "GET"
        assert "[REDACTED]" in (pkt.http_auth_header or "")

    def test_arp_fields(self) -> None:
        pkt = PacketRecord(
            timestamp=1000.0,
            src_ip="10.0.0.1",
            dst_ip="10.0.0.255",
            protocol=Protocol.ARP,
            arp_sender_mac="aa:bb:cc:dd:ee:ff",
            arp_sender_ip="10.0.0.1",
        )
        assert pkt.arp_sender_mac == "aa:bb:cc:dd:ee:ff"

    def test_json_roundtrip(self) -> None:
        pkt = PacketRecord(
            timestamp=1000.0,
            src_ip="1.2.3.4",
            dst_ip="5.6.7.8",
            protocol=Protocol.TCP,
        )
        data = pkt.model_dump()
        restored = PacketRecord.model_validate(data)
        assert restored.src_ip == pkt.src_ip


class TestCloudEvent:
    def test_cloudtrail_event(self) -> None:
        event = CloudEvent(
            timestamp=datetime.datetime.now(datetime.UTC),
            event_source="cloudtrail",
            event_name="AttachUserPolicy",
            source_ip="1.2.3.4",
            user_identity="attacker",
        )
        assert event.event_source == "cloudtrail"
        assert event.event_name == "AttachUserPolicy"

    def test_vpc_flow_event(self) -> None:
        event = CloudEvent(
            timestamp=datetime.datetime.now(datetime.UTC),
            event_source="vpc_flow",
            src_addr="10.0.0.1",
            dst_addr="10.0.0.2",
            action="REJECT",
            bytes_transferred=0,
        )
        assert event.action == "REJECT"

    def test_k8s_event_privileged(self) -> None:
        event = CloudEvent(
            timestamp=datetime.datetime.now(datetime.UTC),
            event_source="k8s_audit",
            verb="create",
            resource="pods",
            privileged=True,
        )
        assert event.privileged is True

    def test_defaults(self) -> None:
        event = CloudEvent(
            timestamp=datetime.datetime.now(datetime.UTC),
            event_source="cloudtrail",
        )
        assert event.bytes_transferred == 0
        assert event.privileged is False
        assert event.extra == {}


class TestNetworkAlert:
    def test_creation(self) -> None:
        alert = NetworkAlert(
            rule_id="port_scan",
            title="SYN Port Scan",
            severity=AlertSeverity.HIGH,
            mitre_technique_id="T1046",
            source_ip="1.2.3.4",
            evidence="100 ports in 60s",
        )
        assert alert.rule_id == "port_scan"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.alert_id != ""

    def test_alert_id_unique(self) -> None:
        a1 = NetworkAlert(
            rule_id="r",
            title="t",
            severity=AlertSeverity.LOW,
            mitre_technique_id="T1046",
            source_ip="1.2.3.4",
            evidence="e",
        )
        a2 = NetworkAlert(
            rule_id="r",
            title="t",
            severity=AlertSeverity.LOW,
            mitre_technique_id="T1046",
            source_ip="1.2.3.4",
            evidence="e",
        )
        assert a1.alert_id != a2.alert_id

    def test_severity_enum(self) -> None:
        for sev in AlertSeverity:
            alert = NetworkAlert(
                rule_id="r",
                title="t",
                severity=sev,
                mitre_technique_id="T1046",
                source_ip="1.2.3.4",
                evidence="e",
            )
            assert alert.severity == sev


class TestProtocolEnum:
    def test_all_protocols(self) -> None:
        protocols = [
            Protocol.TCP,
            Protocol.UDP,
            Protocol.ICMP,
            Protocol.ARP,
            Protocol.DNS,
            Protocol.HTTP,
            Protocol.FTP,
            Protocol.TELNET,
            Protocol.SSH,
            Protocol.UNKNOWN,
        ]
        assert len(protocols) == 10

    def test_str_comparison(self) -> None:
        assert Protocol.TCP == "TCP"
        assert Protocol.DNS == "DNS"


class TestTCPFlagsEnum:
    def test_all_flags(self) -> None:
        flags = [
            TCPFlags.SYN,
            TCPFlags.FIN,
            TCPFlags.RST,
            TCPFlags.ACK,
            TCPFlags.SYN_ACK,
            TCPFlags.PSH_ACK,
            TCPFlags.FIN_ACK,
            TCPFlags.XMAS,
        ]
        assert len(flags) == 8

    def test_xmas_flag(self) -> None:
        assert TCPFlags.XMAS == "XMAS"
