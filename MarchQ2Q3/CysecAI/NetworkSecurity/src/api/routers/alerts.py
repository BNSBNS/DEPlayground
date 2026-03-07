"""Alerts router — submit packet data and retrieve security alerts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.alerts.alert_manager import AlertManager
from src.cloud.cloudtrail_parser import parse_cloudtrail
from src.cloud.k8s_audit_parser import parse_k8s_audit
from src.cloud.vpc_flow_parser import parse_vpc_flow_json
from src.detection.arp_spoof import ARPSpoofDetector
from src.detection.beaconing import BeaconingDetector
from src.detection.brute_force import BruteForceDetector
from src.detection.cleartext_creds import CleartextCredsDetector
from src.detection.cloud_detectors import (
    CloudTrailAssumeRoleDetector,
    CloudTrailIAMPrivescDetector,
    CloudTrailLoggingDisabledDetector,
    K8sPrivilegedContainerDetector,
    K8sRBACWildcardDetector,
)
from src.detection.dns_exfil import DNSExfilDetector
from src.detection.port_scan import PortScanDetector
from src.models import AlertSeverity, NetworkAlert
from src.parser.json_loader import load_packets_from_list

router = APIRouter(prefix="/api/v1", tags=["alerts"])

# Module-level manager — replaced per-request in tests via dependency injection
_manager: AlertManager | None = None

_PACKET_DETECTORS = [
    PortScanDetector(),
    BruteForceDetector(),
    ARPSpoofDetector(),
    DNSExfilDetector(),
    BeaconingDetector(),
    CleartextCredsDetector(),
]

_CLOUD_DETECTORS = [
    K8sPrivilegedContainerDetector(),
    K8sRBACWildcardDetector(),
    CloudTrailIAMPrivescDetector(),
    CloudTrailLoggingDisabledDetector(),
    CloudTrailAssumeRoleDetector(),
]


def get_manager() -> AlertManager:
    global _manager  # noqa: PLW0603
    if _manager is None:
        _manager = AlertManager()
    return _manager


class AnalyzePacketsRequest(BaseModel):
    packets: list[dict[str, Any]]


class AnalyzeCloudRequest(BaseModel):
    source: str  # "cloudtrail" | "vpc_flow" | "k8s_audit"
    events: list[dict[str, Any]]


@router.post("/analyze/packets", status_code=202)
async def analyze_packets(body: AnalyzePacketsRequest) -> dict[str, Any]:
    """Analyze packet records and store any detected alerts."""
    packets = load_packets_from_list(body.packets)
    manager = get_manager()
    all_alerts: list[NetworkAlert] = []
    for detector in _PACKET_DETECTORS:
        all_alerts.extend(detector.analyze(packets))
    added = await manager.add_alerts(all_alerts)
    return {"packets_analyzed": len(packets), "alerts_generated": len(all_alerts), "new": added}


@router.post("/analyze/cloud", status_code=202)
async def analyze_cloud(body: AnalyzeCloudRequest) -> dict[str, Any]:
    """Analyze cloud log events and store any detected alerts."""
    source = body.source
    if source == "cloudtrail":
        events = parse_cloudtrail(body.events)
    elif source == "vpc_flow":
        events = parse_vpc_flow_json(body.events)
    elif source == "k8s_audit":
        events = parse_k8s_audit(body.events)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source!r}")
    manager = get_manager()
    all_alerts: list[NetworkAlert] = []
    for detector in _CLOUD_DETECTORS:
        all_alerts.extend(detector.analyze(events))
    added = await manager.add_alerts(all_alerts)
    return {"events_analyzed": len(events), "alerts_generated": len(all_alerts), "new": added}


@router.get("/alerts")
async def list_alerts(severity: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """List stored alerts, optionally filtered by severity."""
    manager = get_manager()
    sev: AlertSeverity | None = None
    if severity is not None:
        try:
            sev = AlertSeverity(severity.upper())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}") from exc
    alerts = await manager.get_alerts(severity=sev, limit=limit)
    return [
        {
            "alert_id": a.alert_id,
            "rule_id": a.rule_id,
            "title": a.title,
            "severity": str(a.severity),
            "mitre_technique_id": a.mitre_technique_id,
            "source_ip": a.source_ip,
            "dest_ip": a.dest_ip,
            "timestamp": a.timestamp.isoformat(),
            "evidence": a.evidence,
            "packet_count": a.packet_count,
        }
        for a in alerts
    ]


@router.get("/alerts/stats")
async def alert_stats() -> dict[str, Any]:
    """Return alert count statistics."""
    manager = get_manager()
    return await manager.get_stats()
