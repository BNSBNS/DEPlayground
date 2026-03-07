"""Tests for cloud threat detectors."""

from __future__ import annotations

import datetime

from src.detection.cloud_detectors import (
    CloudTrailAssumeRoleDetector,
    CloudTrailIAMPrivescDetector,
    CloudTrailLoggingDisabledDetector,
    K8sPrivilegedContainerDetector,
    K8sRBACWildcardDetector,
)
from src.models import AlertSeverity, CloudEvent

_TS = datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)


def _ct(event_name: str, user: str = "attacker", error: str | None = None) -> CloudEvent:
    return CloudEvent(
        timestamp=_TS,
        event_source="cloudtrail",
        event_name=event_name,
        source_ip="1.2.3.4",
        user_identity=user,
        error_code=error,
    )


def _k8s(
    verb: str = "create",
    resource: str = "pods",
    privileged: bool = True,
    user: str = "attacker",
) -> CloudEvent:
    return CloudEvent(
        timestamp=_TS,
        event_source="k8s_audit",
        verb=verb,
        resource=resource,
        user_identity=user,
        source_ip="1.2.3.4",
        privileged=privileged,
    )


class TestK8sPrivilegedContainerDetector:
    def test_detects_privileged_create(self) -> None:
        events = [_k8s(verb="create", resource="pods", privileged=True)]
        alerts = K8sPrivilegedContainerDetector().analyze(events)
        assert len(alerts) == 1

    def test_rule_id(self) -> None:
        assert K8sPrivilegedContainerDetector().rule_id == "k8s_privileged_container"

    def test_severity_critical(self) -> None:
        events = [_k8s(privileged=True)]
        alerts = K8sPrivilegedContainerDetector().analyze(events)
        assert alerts[0].severity == AlertSeverity.CRITICAL

    def test_mitre_t1078(self) -> None:
        events = [_k8s(privileged=True)]
        alerts = K8sPrivilegedContainerDetector().analyze(events)
        assert alerts[0].mitre_technique_id == "T1078"

    def test_non_privileged_no_alert(self) -> None:
        events = [_k8s(privileged=False)]
        assert K8sPrivilegedContainerDetector().analyze(events) == []

    def test_non_k8s_event_ignored(self) -> None:
        events = [_ct("DescribeInstances")]
        assert K8sPrivilegedContainerDetector().analyze(events) == []

    def test_get_verb_no_alert(self) -> None:
        events = [_k8s(verb="get", privileged=True)]
        assert K8sPrivilegedContainerDetector().analyze(events) == []

    def test_empty_events(self) -> None:
        assert K8sPrivilegedContainerDetector().analyze([]) == []


class TestK8sRBACWildcardDetector:
    def test_detects_wildcard_clusterrole(self) -> None:
        events = [_k8s(verb="create", resource="clusterroles", privileged=True)]
        alerts = K8sRBACWildcardDetector().analyze(events)
        assert len(alerts) == 1

    def test_rule_id(self) -> None:
        assert K8sRBACWildcardDetector().rule_id == "k8s_rbac_wildcard"

    def test_non_wildcard_no_alert(self) -> None:
        events = [_k8s(verb="create", resource="clusterroles", privileged=False)]
        assert K8sRBACWildcardDetector().analyze(events) == []

    def test_non_rbac_resource_no_alert(self) -> None:
        events = [_k8s(verb="create", resource="pods", privileged=True)]
        assert K8sRBACWildcardDetector().analyze(events) == []

    def test_role_resource_also_detected(self) -> None:
        events = [_k8s(verb="create", resource="roles", privileged=True)]
        alerts = K8sRBACWildcardDetector().analyze(events)
        assert len(alerts) == 1


class TestCloudTrailIAMPrivescDetector:
    def test_detects_attach_user_policy(self) -> None:
        events = [_ct("AttachUserPolicy")]
        alerts = CloudTrailIAMPrivescDetector().analyze(events)
        assert len(alerts) == 1

    def test_rule_id(self) -> None:
        assert CloudTrailIAMPrivescDetector().rule_id == "cloudtrail_iam_privesc"

    def test_severity_high(self) -> None:
        events = [_ct("AttachUserPolicy")]
        alerts = CloudTrailIAMPrivescDetector().analyze(events)
        assert alerts[0].severity == AlertSeverity.HIGH

    def test_benign_event_no_alert(self) -> None:
        events = [_ct("DescribeInstances")]
        assert CloudTrailIAMPrivescDetector().analyze(events) == []

    def test_multiple_dangerous_events(self) -> None:
        events = [_ct("AttachUserPolicy"), _ct("CreateAccessKey"), _ct("PutRolePolicy")]
        alerts = CloudTrailIAMPrivescDetector().analyze(events)
        assert len(alerts) == 3

    def test_non_cloudtrail_ignored(self) -> None:
        events = [_k8s()]
        assert CloudTrailIAMPrivescDetector().analyze(events) == []


class TestCloudTrailLoggingDisabledDetector:
    def test_detects_stop_logging(self) -> None:
        events = [_ct("StopLogging")]
        alerts = CloudTrailLoggingDisabledDetector().analyze(events)
        assert len(alerts) == 1

    def test_detects_delete_trail(self) -> None:
        events = [_ct("DeleteTrail")]
        alerts = CloudTrailLoggingDisabledDetector().analyze(events)
        assert len(alerts) == 1

    def test_rule_id(self) -> None:
        assert CloudTrailLoggingDisabledDetector().rule_id == "cloudtrail_logging_disabled"

    def test_severity_critical(self) -> None:
        events = [_ct("StopLogging")]
        alerts = CloudTrailLoggingDisabledDetector().analyze(events)
        assert alerts[0].severity == AlertSeverity.CRITICAL

    def test_benign_event_no_alert(self) -> None:
        events = [_ct("DescribeTrails")]
        assert CloudTrailLoggingDisabledDetector().analyze(events) == []


class TestCloudTrailAssumeRoleDetector:
    def test_detects_root_assume_role(self) -> None:
        events = [_ct("AssumeRole", user="root")]
        alerts = CloudTrailAssumeRoleDetector().analyze(events)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL

    def test_detects_failed_assume_role(self) -> None:
        events = [_ct("AssumeRole", user="normal-user", error="AccessDenied")]
        alerts = CloudTrailAssumeRoleDetector().analyze(events)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.MEDIUM

    def test_normal_assume_role_no_alert(self) -> None:
        events = [_ct("AssumeRole", user="deploy-bot")]
        assert CloudTrailAssumeRoleDetector().analyze(events) == []

    def test_rule_id(self) -> None:
        assert CloudTrailAssumeRoleDetector().rule_id == "cloudtrail_assume_role"

    def test_non_assume_role_ignored(self) -> None:
        events = [_ct("DescribeInstances")]
        assert CloudTrailAssumeRoleDetector().analyze(events) == []
