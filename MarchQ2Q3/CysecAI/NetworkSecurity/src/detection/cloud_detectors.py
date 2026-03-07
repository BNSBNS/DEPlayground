"""Cloud security detectors — K8s RBAC abuse and AWS CloudTrail anomalies."""

from __future__ import annotations

from src.detection.base import BaseCloudDetector
from src.models import AlertSeverity, CloudEvent, NetworkAlert

# ── CloudTrail event names that indicate privilege escalation / tampering ────

_DANGEROUS_IAM_EVENTS = frozenset(
    {
        "AttachUserPolicy",
        "AttachRolePolicy",
        "PutUserPolicy",
        "PutRolePolicy",
        "CreatePolicyVersion",
        "SetDefaultPolicyVersion",
        "AddUserToGroup",
        "CreateAccessKey",
    }
)

_LOGGING_DISABLE_EVENTS = frozenset(
    {
        "DeleteTrail",
        "StopLogging",
        "UpdateTrail",
        "PutEventSelectors",
    }
)


class K8sPrivilegedContainerDetector(BaseCloudDetector):
    """Detects privileged container creation in K8s audit logs."""

    @property
    def rule_id(self) -> str:
        return "k8s_privileged_container"

    def analyze(self, events: list[CloudEvent]) -> list[NetworkAlert]:
        alerts: list[NetworkAlert] = []
        for event in events:
            if event.event_source != "k8s_audit":
                continue
            if not event.privileged:
                continue
            if event.verb not in {"create", "patch", "update"}:
                continue
            alerts.append(
                NetworkAlert(
                    rule_id=self.rule_id,
                    title="K8s Privileged Container Created",
                    severity=AlertSeverity.CRITICAL,
                    mitre_technique_id="T1078",
                    source_ip=event.source_ip or "unknown",
                    timestamp=event.timestamp,
                    evidence=(
                        f"User '{event.user_identity}' {event.verb}d privileged "
                        f"{event.resource or 'resource'} in namespace '{event.namespace}'"
                    ),
                )
            )
        return alerts


class K8sRBACWildcardDetector(BaseCloudDetector):
    """Detects RBAC roles/clusterroles with wildcard verbs or resources."""

    @property
    def rule_id(self) -> str:
        return "k8s_rbac_wildcard"

    def analyze(self, events: list[CloudEvent]) -> list[NetworkAlert]:
        alerts: list[NetworkAlert] = []
        for event in events:
            if event.event_source != "k8s_audit":
                continue
            if event.resource not in {"roles", "clusterroles"}:
                continue
            # privileged=True is reused to flag wildcard RBAC
            if not event.privileged:
                continue
            if event.verb not in {"create", "update", "patch"}:
                continue
            alerts.append(
                NetworkAlert(
                    rule_id=self.rule_id,
                    title="K8s RBAC Wildcard Role Detected",
                    severity=AlertSeverity.HIGH,
                    mitre_technique_id="T1078",
                    source_ip=event.source_ip or "unknown",
                    timestamp=event.timestamp,
                    evidence=(
                        f"User '{event.user_identity}' created/modified "
                        f"{event.resource} with wildcard permissions "
                        f"in namespace '{event.namespace}'"
                    ),
                )
            )
        return alerts


class CloudTrailIAMPrivescDetector(BaseCloudDetector):
    """Detects unusual IAM privilege escalation events in CloudTrail."""

    @property
    def rule_id(self) -> str:
        return "cloudtrail_iam_privesc"

    def analyze(self, events: list[CloudEvent]) -> list[NetworkAlert]:
        alerts: list[NetworkAlert] = []
        for event in events:
            if event.event_source != "cloudtrail":
                continue
            if event.event_name not in _DANGEROUS_IAM_EVENTS:
                continue
            alerts.append(
                NetworkAlert(
                    rule_id=self.rule_id,
                    title=f"IAM Privilege Escalation: {event.event_name}",
                    severity=AlertSeverity.HIGH,
                    mitre_technique_id="T1098",
                    source_ip=event.source_ip or "unknown",
                    timestamp=event.timestamp,
                    evidence=(
                        f"User '{event.user_identity}' called {event.event_name}"
                        + (f" (error: {event.error_code})" if event.error_code else "")
                    ),
                )
            )
        return alerts


class CloudTrailLoggingDisabledDetector(BaseCloudDetector):
    """Detects CloudTrail logging being disabled or deleted."""

    @property
    def rule_id(self) -> str:
        return "cloudtrail_logging_disabled"

    def analyze(self, events: list[CloudEvent]) -> list[NetworkAlert]:
        alerts: list[NetworkAlert] = []
        for event in events:
            if event.event_source != "cloudtrail":
                continue
            if event.event_name not in _LOGGING_DISABLE_EVENTS:
                continue
            alerts.append(
                NetworkAlert(
                    rule_id=self.rule_id,
                    title=f"CloudTrail Logging Tampered: {event.event_name}",
                    severity=AlertSeverity.CRITICAL,
                    mitre_technique_id="T1562.008",
                    source_ip=event.source_ip or "unknown",
                    timestamp=event.timestamp,
                    evidence=f"User '{event.user_identity}' called {event.event_name}",
                )
            )
        return alerts


class CloudTrailAssumeRoleDetector(BaseCloudDetector):
    """Detects unusual AssumeRole calls (potential lateral movement)."""

    @property
    def rule_id(self) -> str:
        return "cloudtrail_assume_role"

    def analyze(self, events: list[CloudEvent]) -> list[NetworkAlert]:
        alerts: list[NetworkAlert] = []
        for event in events:
            if event.event_source != "cloudtrail":
                continue
            if event.event_name != "AssumeRole":
                continue
            # Flag if the caller is a root account or if there's an error
            user = event.user_identity or ""
            is_root = "root" in user.lower()
            has_error = event.error_code is not None
            if not is_root and not has_error:
                continue
            severity = AlertSeverity.CRITICAL if is_root else AlertSeverity.MEDIUM
            alerts.append(
                NetworkAlert(
                    rule_id=self.rule_id,
                    title="Suspicious AssumeRole Call",
                    severity=severity,
                    mitre_technique_id="T1548",
                    source_ip=event.source_ip or "unknown",
                    timestamp=event.timestamp,
                    evidence=(
                        f"AssumeRole by '{user}'"
                        + (" (root account)" if is_root else "")
                        + (f" (error: {event.error_code})" if event.error_code else "")
                    ),
                )
            )
        return alerts
