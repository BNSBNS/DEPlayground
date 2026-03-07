"""Parse Kubernetes audit log records into CloudEvent models."""

from __future__ import annotations

import datetime
import json
import pathlib
from typing import Any

from src.models import CloudEvent


def _extract_privileged(obj: dict[str, Any]) -> bool:
    """Return True if the request creates/patches a privileged container."""
    req = obj.get("requestObject") or {}
    spec = req.get("spec") or {}
    # Pod spec
    containers = spec.get("containers") or []
    init_containers = spec.get("initContainers") or []
    for container in containers + init_containers:
        security = container.get("securityContext") or {}
        if security.get("privileged") is True:
            return True
    # ClusterRole / Role with wildcard verbs
    rules = req.get("rules") or []
    for rule in rules:
        if "*" in (rule.get("verbs") or []) or "*" in (rule.get("resources") or []):
            return True
    return False


def _parse_k8s_record(record: dict[str, Any]) -> CloudEvent:
    raw_time = record.get("requestReceivedTimestamp") or record.get("stageTimestamp", "")
    try:
        ts = datetime.datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        ts = datetime.datetime.now(datetime.UTC)
    user = record.get("user") or {}
    username = user.get("username", "unknown")
    response = record.get("responseStatus") or {}
    code = response.get("code")
    privileged = _extract_privileged(record)
    return CloudEvent(
        timestamp=ts,
        event_source="k8s_audit",
        event_name=record.get("verb"),
        source_ip=record.get("sourceIPs", [None])[0] if record.get("sourceIPs") else None,
        user_identity=username,
        verb=record.get("verb"),
        resource=record.get("objectRef", {}).get("resource"),
        namespace=record.get("objectRef", {}).get("namespace"),
        response_code=int(code) if code is not None else None,
        privileged=privileged,
        extra={
            "stage": record.get("stage", ""),
            "apiVersion": record.get("apiVersion", ""),
            "level": record.get("level", ""),
        },
    )


def parse_k8s_audit(data: list[dict[str, Any]]) -> list[CloudEvent]:
    """Parse a list of K8s audit log record dicts into CloudEvent objects."""
    return [_parse_k8s_record(r) for r in data]


def load_k8s_audit(path: str | pathlib.Path) -> list[CloudEvent]:
    """Load K8s audit log from a JSON file (list or single object)."""
    raw = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    items: list[dict[str, Any]] = raw if isinstance(raw, list) else [raw]
    return parse_k8s_audit(items)
