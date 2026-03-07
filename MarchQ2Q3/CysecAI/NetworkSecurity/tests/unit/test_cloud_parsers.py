"""Tests for cloud log parsers."""

from __future__ import annotations

import datetime

from src.cloud.cloudtrail_parser import parse_cloudtrail
from src.cloud.k8s_audit_parser import parse_k8s_audit
from src.cloud.vpc_flow_parser import parse_vpc_flow_json, parse_vpc_flow_lines

_CT_RECORD = {
    "eventTime": "2026-01-01T00:00:00Z",
    "eventName": "AttachUserPolicy",
    "sourceIPAddress": "1.2.3.4",
    "userIdentity": {
        "type": "IAMUser",
        "userName": "attacker",
        "arn": "arn:aws:iam::123:user/attacker",
    },
    "eventSource": "iam.amazonaws.com",
    "awsRegion": "us-east-1",
}


class TestCloudTrailParser:
    def test_parses_event_name(self) -> None:
        events = parse_cloudtrail([_CT_RECORD])
        assert len(events) == 1
        assert events[0].event_name == "AttachUserPolicy"

    def test_parses_source_ip(self) -> None:
        events = parse_cloudtrail([_CT_RECORD])
        assert events[0].source_ip == "1.2.3.4"

    def test_parses_user_identity(self) -> None:
        events = parse_cloudtrail([_CT_RECORD])
        assert "attacker" in (events[0].user_identity or "")

    def test_parses_timestamp(self) -> None:
        events = parse_cloudtrail([_CT_RECORD])
        assert events[0].timestamp.year == 2026

    def test_event_source_is_cloudtrail(self) -> None:
        events = parse_cloudtrail([_CT_RECORD])
        assert events[0].event_source == "cloudtrail"

    def test_empty_list(self) -> None:
        assert parse_cloudtrail([]) == []

    def test_bad_timestamp_uses_now(self) -> None:
        record = {**_CT_RECORD, "eventTime": "not-a-date"}
        events = parse_cloudtrail([record])
        assert events[0].timestamp is not None

    def test_error_code_preserved(self) -> None:
        record = {**_CT_RECORD, "errorCode": "AccessDenied"}
        events = parse_cloudtrail([record])
        assert events[0].error_code == "AccessDenied"


class TestVPCFlowParser:
    def test_parse_json_format(self) -> None:
        data = [
            {
                "start": 1735689600,
                "srcaddr": "10.0.0.1",
                "dstaddr": "10.0.0.2",
                "srcport": 54321,
                "dstport": 443,
                "action": "ACCEPT",
                "bytes": 1024,
                "protocol": "6",
            }
        ]
        events = parse_vpc_flow_json(data)
        assert len(events) == 1
        assert events[0].src_addr == "10.0.0.1"
        assert events[0].action == "ACCEPT"
        assert events[0].bytes_transferred == 1024

    def test_parse_text_format(self) -> None:
        header = "version account-id interface-id srcaddr dstaddr srcport dstport protocol packets bytes start end action log-status"  # noqa: E501
        row = "2 123456789 eni-abc 10.0.0.1 10.0.0.2 54321 443 6 10 5000 1735689600 1735689610 ACCEPT OK"  # noqa: E501
        lines = [header, row]
        events = parse_vpc_flow_lines(lines)
        assert len(events) == 1
        assert events[0].event_source == "vpc_flow"

    def test_parse_reject_action(self) -> None:
        data = [
            {
                "start": 1735689600,
                "srcaddr": "1.2.3.4",
                "dstaddr": "10.0.0.1",
                "srcport": 9999,
                "dstport": 22,
                "action": "REJECT",
                "bytes": 0,
                "protocol": "6",
            }
        ]
        events = parse_vpc_flow_json(data)
        assert events[0].action == "REJECT"

    def test_empty_lines_skipped(self) -> None:
        header = "version account-id interface-id srcaddr dstaddr srcport dstport protocol packets bytes start end action log-status"  # noqa: E501
        events = parse_vpc_flow_lines(["", "   ", header])
        assert events == []


_PRIV_RECORD: dict[str, object] = {
    "requestReceivedTimestamp": "2026-01-01T00:00:00Z",
    "verb": "create",
    "user": {"username": "attacker"},
    "objectRef": {"resource": "pods", "namespace": "kube-system"},
    "responseStatus": {"code": 201},
    "sourceIPs": ["1.2.3.4"],
    "requestObject": {
        "spec": {"containers": [{"name": "c", "securityContext": {"privileged": True}}]}
    },
}


class TestK8sAuditParser:
    def test_parses_verb(self) -> None:
        events = parse_k8s_audit([_PRIV_RECORD])
        assert events[0].verb == "create"

    def test_parses_resource(self) -> None:
        events = parse_k8s_audit([_PRIV_RECORD])
        assert events[0].resource == "pods"

    def test_privileged_detected(self) -> None:
        events = parse_k8s_audit([_PRIV_RECORD])
        assert events[0].privileged is True

    def test_non_privileged_not_flagged(self) -> None:
        record = {
            **_PRIV_RECORD,
            "requestObject": {
                "spec": {"containers": [{"name": "c", "securityContext": {"privileged": False}}]}
            },
        }
        events = parse_k8s_audit([record])
        assert events[0].privileged is False

    def test_wildcard_rbac_detected(self) -> None:
        record = {
            **_PRIV_RECORD,
            "objectRef": {"resource": "clusterroles", "namespace": ""},
            "requestObject": {"rules": [{"verbs": ["*"], "resources": ["*"]}]},
        }
        events = parse_k8s_audit([record])
        assert events[0].privileged is True

    def test_user_identity_extracted(self) -> None:
        events = parse_k8s_audit([_PRIV_RECORD])
        assert events[0].user_identity == "attacker"

    def test_empty_list(self) -> None:
        assert parse_k8s_audit([]) == []

    def test_bad_timestamp_uses_now(self) -> None:
        record = {**_PRIV_RECORD, "requestReceivedTimestamp": "bad"}
        events = parse_k8s_audit([record])
        assert isinstance(events[0].timestamp, datetime.datetime)
