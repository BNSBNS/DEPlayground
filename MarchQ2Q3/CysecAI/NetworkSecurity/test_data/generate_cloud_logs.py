"""Generate synthetic cloud log fixtures (CloudTrail, VPC flow, K8s audit)."""

from __future__ import annotations

import json
import pathlib

_OUT = pathlib.Path(__file__).parent
_BASE_TIME = "2026-01-01T00:00:00Z"


def generate_cloudtrail(malicious: bool = True) -> list[dict[str, object]]:
    records: list[dict[str, object]] = [
        # Normal events
        {
            "eventTime": "2026-01-01T00:01:00Z",
            "eventName": "DescribeInstances",
            "sourceIPAddress": "10.0.0.50",
            "userIdentity": {"type": "IAMUser", "userName": "deploy-bot", "arn": "arn:aws:iam::123:user/deploy-bot"},
            "eventSource": "ec2.amazonaws.com",
            "awsRegion": "us-east-1",
        },
        {
            "eventTime": "2026-01-01T00:02:00Z",
            "eventName": "GetObject",
            "sourceIPAddress": "10.0.0.50",
            "userIdentity": {"type": "IAMUser", "userName": "deploy-bot", "arn": "arn:aws:iam::123:user/deploy-bot"},
            "eventSource": "s3.amazonaws.com",
            "awsRegion": "us-east-1",
        },
    ]
    if malicious:
        records.extend([
            # Privilege escalation
            {
                "eventTime": "2026-01-01T01:00:00Z",
                "eventName": "AttachUserPolicy",
                "sourceIPAddress": "203.0.113.99",
                "userIdentity": {"type": "IAMUser", "userName": "attacker", "arn": "arn:aws:iam::123:user/attacker"},
                "eventSource": "iam.amazonaws.com",
                "awsRegion": "us-east-1",
                "requestParameters": {"userName": "victim", "policyArn": "arn:aws:iam::aws:policy/AdministratorAccess"},
            },
            # Logging disabled
            {
                "eventTime": "2026-01-01T01:05:00Z",
                "eventName": "StopLogging",
                "sourceIPAddress": "203.0.113.99",
                "userIdentity": {"type": "Root", "userName": "root", "arn": "arn:aws:iam::123:root"},
                "eventSource": "cloudtrail.amazonaws.com",
                "awsRegion": "us-east-1",
            },
            # Root AssumeRole
            {
                "eventTime": "2026-01-01T01:10:00Z",
                "eventName": "AssumeRole",
                "sourceIPAddress": "203.0.113.99",
                "userIdentity": {"type": "Root", "userName": "root", "arn": "arn:aws:iam::123:root"},
                "eventSource": "sts.amazonaws.com",
                "awsRegion": "us-east-1",
            },
        ])
    return records


def generate_vpc_flow(malicious: bool = True) -> list[dict[str, object]]:
    records: list[dict[str, object]] = [
        {"start": 1735689600, "srcaddr": "10.0.0.1", "dstaddr": "10.0.0.2", "srcport": 54321, "dstport": 443, "action": "ACCEPT", "bytes": 5000, "protocol": "6"},
        {"start": 1735689610, "srcaddr": "10.0.0.3", "dstaddr": "10.0.0.4", "srcport": 54322, "dstport": 80, "action": "ACCEPT", "bytes": 1200, "protocol": "6"},
    ]
    if malicious:
        records.extend([
            {"start": 1735689620, "srcaddr": "203.0.113.1", "dstaddr": "10.0.0.100", "srcport": 12345, "dstport": 22, "action": "REJECT", "bytes": 0, "protocol": "6"},
            {"start": 1735689630, "srcaddr": "203.0.113.1", "dstaddr": "10.0.0.100", "srcport": 12346, "dstport": 22, "action": "REJECT", "bytes": 0, "protocol": "6"},
        ])
    return records


def generate_k8s_audit(malicious: bool = True) -> list[dict[str, object]]:
    records: list[dict[str, object]] = [
        # Normal
        {
            "requestReceivedTimestamp": "2026-01-01T00:01:00Z",
            "verb": "get",
            "user": {"username": "system:serviceaccount:default:webapp"},
            "objectRef": {"resource": "pods", "namespace": "default"},
            "responseStatus": {"code": 200},
            "sourceIPs": ["10.0.0.10"],
            "requestObject": {},
        },
    ]
    if malicious:
        records.extend([
            # Privileged container creation
            {
                "requestReceivedTimestamp": "2026-01-01T01:00:00Z",
                "verb": "create",
                "user": {"username": "attacker"},
                "objectRef": {"resource": "pods", "namespace": "kube-system"},
                "responseStatus": {"code": 201},
                "sourceIPs": ["203.0.113.5"],
                "requestObject": {
                    "spec": {
                        "containers": [
                            {
                                "name": "evil-container",
                                "image": "attacker/shell:latest",
                                "securityContext": {"privileged": True},
                            }
                        ]
                    }
                },
            },
            # Wildcard RBAC role
            {
                "requestReceivedTimestamp": "2026-01-01T01:05:00Z",
                "verb": "create",
                "user": {"username": "attacker"},
                "objectRef": {"resource": "clusterroles", "namespace": ""},
                "responseStatus": {"code": 201},
                "sourceIPs": ["203.0.113.5"],
                "requestObject": {
                    "rules": [{"verbs": ["*"], "resources": ["*"], "apiGroups": ["*"]}]
                },
            },
        ])
    return records


def main() -> None:
    fixtures: dict[str, object] = {
        "cloudtrail_events.json": generate_cloudtrail(),
        "vpc_flow_logs.json": generate_vpc_flow(),
        "k8s_audit.json": generate_k8s_audit(),
    }
    for filename, data in fixtures.items():
        out = _OUT / filename
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        assert isinstance(data, list)
        print(f"Written {len(data)} records → {out}")


if __name__ == "__main__":
    main()
