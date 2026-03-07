"""Tests for CIS Docker Benchmark scanner."""

from __future__ import annotations

from src.models import Severity
from src.scanners.docker_scanner import scan_dockerfile

_GOOD_DOCKERFILE = """
FROM python:3.11-slim

RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser

HEALTHCHECK --interval=30s CMD curl -f http://localhost:8000/health || exit 1

COPY --chown=appuser:appuser . /app
WORKDIR /app
CMD ["python", "app.py"]
"""

_VULNERABLE_DOCKERFILE = """
FROM ubuntu:latest

ENV DB_PASSWORD=secret123
ENV API_KEY=mykey

RUN apt-get update && sudo apt-get install -y openssh-server

EXPOSE 22

ADD http://example.com/setup.sh /tmp/setup.sh

CMD ["bash"]
"""


class TestDockerScanner:
    def test_no_findings_for_good_dockerfile(self) -> None:
        findings = scan_dockerfile(_GOOD_DOCKERFILE)
        check_ids = [f.check_id for f in findings]
        # DKR-001 (root user) should NOT fire — we have USER appuser
        assert "DKR-001" not in check_ids

    def test_latest_tag_detected(self) -> None:
        findings = scan_dockerfile(_VULNERABLE_DOCKERFILE)
        assert any(f.check_id == "DKR-002" for f in findings)

    def test_root_user_detected_when_no_user(self) -> None:
        findings = scan_dockerfile("FROM ubuntu:22.04\nCMD bash")
        assert any(f.check_id == "DKR-001" for f in findings)

    def test_explicit_root_user(self) -> None:
        findings = scan_dockerfile("FROM ubuntu:22.04\nUSER root\nCMD bash")
        assert any(f.check_id == "DKR-001" for f in findings)

    def test_no_healthcheck(self) -> None:
        findings = scan_dockerfile("FROM ubuntu:22.04\nCMD bash")
        assert any(f.check_id == "DKR-005" for f in findings)

    def test_privileged_port(self) -> None:
        findings = scan_dockerfile("FROM ubuntu:22.04\nEXPOSE 22")
        assert any(f.check_id == "DKR-003" for f in findings)

    def test_add_remote_url(self) -> None:
        findings = scan_dockerfile("FROM ubuntu:22.04\nADD http://example.com/file.sh /tmp/")
        assert any(f.check_id == "DKR-004" for f in findings)

    def test_secret_env(self) -> None:
        findings = scan_dockerfile("FROM ubuntu:22.04\nENV DB_PASSWORD=secret")
        assert any(f.check_id == "DKR-006" for f in findings)

    def test_sudo_in_run(self) -> None:
        findings = scan_dockerfile("FROM ubuntu:22.04\nRUN sudo apt-get update")
        assert any(f.check_id == "DKR-007" for f in findings)

    def test_severity_high_for_root(self) -> None:
        findings = scan_dockerfile("FROM ubuntu:22.04\nCMD bash")
        root_finding = next(f for f in findings if f.check_id == "DKR-001")
        assert root_finding.severity == Severity.HIGH

    def test_empty_dockerfile(self) -> None:
        assert scan_dockerfile("") == []

    def test_multiple_findings_from_vulnerable(self) -> None:
        findings = scan_dockerfile(_VULNERABLE_DOCKERFILE)
        assert len(findings) >= 3

    def test_line_numbers_populated(self) -> None:
        findings = scan_dockerfile("FROM ubuntu:latest\nEXPOSE 22")
        for f in findings:
            if f.line_number is not None:
                assert f.line_number > 0

    def test_recommendation_present(self) -> None:
        findings = scan_dockerfile("FROM ubuntu:22.04\nCMD bash")
        for f in findings:
            assert f.recommendation != ""
