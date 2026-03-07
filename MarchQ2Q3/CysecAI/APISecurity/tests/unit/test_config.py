"""Tests for APISecurity config settings."""

from __future__ import annotations

import pytest  # noqa: TC002

from src.config import ScannerSettings, VulnerableAppSettings


class TestScannerSettings:
    def test_defaults(self) -> None:
        s = ScannerSettings()
        assert s.target_url == "http://localhost:8001"
        assert s.request_timeout == 10.0
        assert s.max_concurrent == 5
        assert s.destructive is False

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SCANNER_TARGET_URL", "http://target.example.com")
        monkeypatch.setenv("SCANNER_DESTRUCTIVE", "true")
        s = ScannerSettings()
        assert s.target_url == "http://target.example.com"
        assert s.destructive is True

    def test_timeout_as_float(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SCANNER_REQUEST_TIMEOUT", "30.5")
        s = ScannerSettings()
        assert s.request_timeout == 30.5


class TestVulnerableAppSettings:
    def test_defaults(self) -> None:
        s = VulnerableAppSettings()
        assert s.host == "0.0.0.0"
        assert s.port == 8001
        assert s.debug is True

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VULN_APP_PORT", "9000")
        s = VulnerableAppSettings()
        assert s.port == 9000
