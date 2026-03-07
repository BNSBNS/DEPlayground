"""CI/CD output formats: JSON summary and SARIF 2.1.0."""

from __future__ import annotations

import json
from typing import Any

from src.models import ScanResult, Severity


def to_json(result: ScanResult) -> str:
    """Render scan result as formatted JSON string."""
    return json.dumps(result.to_dict(), indent=2)


def to_sarif(result: ScanResult) -> dict[str, Any]:
    """Render scan result as SARIF 2.1.0 format for GitHub Code Scanning."""
    runs: list[dict[str, Any]] = []

    rules: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    # Map severity to SARIF level
    sev_to_level: dict[Severity, str] = {
        Severity.CRITICAL: "error",
        Severity.HIGH: "error",
        Severity.MEDIUM: "warning",
        Severity.LOW: "note",
        Severity.NONE: "none",
        Severity.UNKNOWN: "note",
    }

    added_rules: set[str] = set()

    for finding in result.findings:
        for vuln in finding.vulnerabilities:
            rule_id = f"infrascanner/{vuln.vuln_id}"

            if rule_id not in added_rules:
                added_rules.add(rule_id)
                rules.append(
                    {
                        "id": rule_id,
                        "name": f"VulnerableDependency/{vuln.vuln_id}",
                        "shortDescription": {"text": vuln.description[:100] or vuln.vuln_id},
                        "fullDescription": {"text": vuln.description or vuln.vuln_id},
                        "defaultConfiguration": {
                            "level": sev_to_level.get(vuln.severity, "warning")
                        },
                        "helpUri": (vuln.reference_urls[0] if vuln.reference_urls else ""),
                        "properties": {
                            "tags": ["security", "dependency", str(vuln.severity).lower()],
                            "cvss": vuln.cvss_score,
                            "epss": vuln.epss_score,
                        },
                    }
                )

            results.append(
                {
                    "ruleId": rule_id,
                    "level": sev_to_level.get(vuln.severity, "warning"),
                    "message": {
                        "text": (
                            f"{finding.dependency.name}@{finding.dependency.version} "
                            f"is affected by {vuln.vuln_id}. "
                            f"CVSS: {vuln.cvss_score}. {vuln.description[:200]}"
                        )
                    },
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {
                                    "uri": finding.dependency.source_file or "unknown",
                                }
                            }
                        }
                    ],
                    "properties": {"is_kev": vuln.is_kev},
                }
            )

    # Add docker findings as SARIF results
    for df in result.docker_findings:
        rule_id = f"infrascanner/{df.check_id}"
        if rule_id not in added_rules:
            added_rules.add(rule_id)
            rules.append(
                {
                    "id": rule_id,
                    "name": f"DockerBenchmark/{df.check_id}",
                    "shortDescription": {"text": df.description[:100]},
                    "defaultConfiguration": {"level": sev_to_level.get(df.severity, "warning")},
                }
            )
        results.append(
            {
                "ruleId": rule_id,
                "level": sev_to_level.get(df.severity, "warning"),
                "message": {"text": f"{df.description}. {df.recommendation}"},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": "Dockerfile"},
                            "region": {"startLine": df.line_number or 1},
                        }
                    }
                ],
            }
        )

    runs.append(
        {
            "tool": {
                "driver": {
                    "name": "InfraScanner",
                    "version": "0.1.0",
                    "informationUri": "https://github.com/example/infrascanner",
                    "rules": rules,
                }
            },
            "results": results,
        }
    )

    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": runs,
    }
