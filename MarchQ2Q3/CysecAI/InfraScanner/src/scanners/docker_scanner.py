"""CIS Docker Benchmark — Dockerfile security checks."""

from __future__ import annotations

import re

from src.models import DockerFinding, Severity

# CIS Docker Benchmark check IDs we implement
_CHECK_ROOT_USER = "DKR-001"
_CHECK_LATEST_TAG = "DKR-002"
_CHECK_PRIVILEGED_PORT = "DKR-003"
_CHECK_ADD_REMOTE = "DKR-004"
_CHECK_NO_HEALTHCHECK = "DKR-005"
_CHECK_SECRET_ENV = "DKR-006"
_CHECK_SUDO = "DKR-007"

_SECRET_PATTERN = re.compile(
    r"(password|passwd|secret|api_key|apikey|token|credential)",
    re.IGNORECASE,
)


def scan_dockerfile(content: str) -> list[DockerFinding]:
    """Run CIS Docker Benchmark checks against Dockerfile content."""
    findings: list[DockerFinding] = []
    lines = content.splitlines()

    has_healthcheck = False
    has_user_non_root = False
    has_any_from = False

    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        upper = line.upper()

        # DKR-002: FROM with :latest tag
        if upper.startswith("FROM ") and ":LATEST" in upper:
            findings.append(
                DockerFinding(
                    check_id=_CHECK_LATEST_TAG,
                    description=f"Base image uses :latest tag: {line}",
                    severity=Severity.MEDIUM,
                    line_number=lineno,
                    recommendation="Pin base image to a specific digest or version tag.",
                )
            )
        if upper.startswith("FROM "):
            has_any_from = True

        # DKR-001: USER root (or no USER directive at all)
        if upper.startswith("USER "):
            user = line.split(None, 1)[1].strip().lower()
            if user in ("root", "0", "0:0"):
                findings.append(
                    DockerFinding(
                        check_id=_CHECK_ROOT_USER,
                        description="Container runs as root user",
                        severity=Severity.HIGH,
                        line_number=lineno,
                        recommendation="Add a non-root USER directive before CMD/ENTRYPOINT.",
                    )
                )
            else:
                has_user_non_root = True

        # DKR-003: EXPOSE privileged port (<1024)
        if upper.startswith("EXPOSE "):
            port_str = line.split(None, 1)[1].strip().split("/")[0]
            try:
                port = int(port_str)
                if port < 1024:
                    findings.append(
                        DockerFinding(
                            check_id=_CHECK_PRIVILEGED_PORT,
                            description=f"Exposing privileged port {port}",
                            severity=Severity.LOW,
                            line_number=lineno,
                            recommendation="Use unprivileged ports (>1023) in containers.",
                        )
                    )
            except ValueError:
                pass

        # DKR-004: ADD with remote URL (prefer COPY + explicit download)
        if upper.startswith("ADD "):
            args = line.split(None, 2)
            if len(args) >= 2 and ("http://" in args[1] or "https://" in args[1]):
                findings.append(
                    DockerFinding(
                        check_id=_CHECK_ADD_REMOTE,
                        description=f"ADD fetches remote URL: {args[1]}",
                        severity=Severity.MEDIUM,
                        line_number=lineno,
                        recommendation="Use RUN curl/wget with explicit hash verification.",
                    )
                )

        # DKR-006: ENV with secret-sounding name
        if upper.startswith("ENV "):
            rest = line[4:].strip()
            if _SECRET_PATTERN.search(rest):
                findings.append(
                    DockerFinding(
                        check_id=_CHECK_SECRET_ENV,
                        description=f"ENV may expose a secret: {rest[:60]}",
                        severity=Severity.HIGH,
                        line_number=lineno,
                        recommendation="Use Docker secrets or runtime env injection instead.",
                    )
                )

        # DKR-007: sudo in RUN commands
        if upper.startswith("RUN ") and "SUDO" in upper:
            findings.append(
                DockerFinding(
                    check_id=_CHECK_SUDO,
                    description="RUN command uses sudo — image may run as root",
                    severity=Severity.MEDIUM,
                    line_number=lineno,
                    recommendation="Avoid sudo; run as non-root user with appropriate permissions.",
                )
            )

        if upper.startswith("HEALTHCHECK "):
            has_healthcheck = True

    # DKR-005: No HEALTHCHECK at all
    if has_any_from and not has_healthcheck:
        findings.append(
            DockerFinding(
                check_id=_CHECK_NO_HEALTHCHECK,
                description="No HEALTHCHECK instruction defined",
                severity=Severity.LOW,
                recommendation="Add HEALTHCHECK to enable orchestrator health monitoring.",
            )
        )

    # DKR-001: No USER directive means container runs as root
    if (
        has_any_from
        and not has_user_non_root
        and not any(f.check_id == _CHECK_ROOT_USER for f in findings)
    ):
        findings.append(
            DockerFinding(
                check_id=_CHECK_ROOT_USER,
                description="No USER directive — container will run as root",
                severity=Severity.HIGH,
                recommendation="Add a non-root USER directive before CMD/ENTRYPOINT.",
            )
        )

    return findings
