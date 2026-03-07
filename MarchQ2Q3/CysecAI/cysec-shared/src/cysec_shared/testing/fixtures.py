"""Shared test fixture factories for SecurityAlert.

Usage in project conftest.py:
    from cysec_shared.testing.fixtures import make_security_alert

    @pytest.fixture
    def sample_alert():
        return make_security_alert(source_project="fraud-detection")
"""

from __future__ import annotations

from typing import Any

from cysec_shared.models.alerts import SecurityAlert


def make_security_alert(**overrides: Any) -> SecurityAlert:
    """Create a SecurityAlert with sensible defaults for testing."""
    defaults: dict[str, Any] = {
        "source_project": "test-project",
        "rule_id": "TEST-001",
        "severity": "medium",
        "title": "Test alert",
        "description": "A test security alert for unit testing.",
        "affected_asset": "10.0.0.1",
        "mitre_technique_id": "T1110.001",
        "mitre_tactic": "Credential Access",
        "cia_impact": ["Confidentiality"],
        "evidence": {"test_key": "test_value"},
        "recommendations": ["Investigate immediately"],
    }
    defaults.update(overrides)
    return SecurityAlert(**defaults)
