"""Tests for TIKG config settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config import Neo4jSettings, NVDSettings, TIKGSettings


class TestNeo4jSettings:
    def test_defaults(self) -> None:
        s = Neo4jSettings()
        assert s.uri == "bolt://localhost:7687"
        assert s.user == "neo4j"
        assert s.password == "password"
        assert s.database == "neo4j"

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NEO4J_URI", "bolt://remote:7687")
        monkeypatch.setenv("NEO4J_USER", "admin")
        monkeypatch.setenv("NEO4J_PASSWORD", "secret")
        s = Neo4jSettings()
        assert s.uri == "bolt://remote:7687"
        assert s.user == "admin"
        assert s.password == "secret"


class TestNVDSettings:
    def test_defaults(self) -> None:
        s = NVDSettings()
        assert s.api_key == ""
        assert "nvd.nist.gov" in s.base_url
        assert s.results_per_page == 2000
        assert s.rate_limit_delay == pytest.approx(6.0)

    def test_results_per_page_max(self) -> None:
        s = NVDSettings(results_per_page=2000)
        assert s.results_per_page == 2000

    def test_results_per_page_invalid(self) -> None:
        with pytest.raises(ValidationError):
            NVDSettings(results_per_page=2001)

    def test_results_per_page_zero_invalid(self) -> None:
        with pytest.raises(ValidationError):
            NVDSettings(results_per_page=0)

    def test_rate_limit_negative_invalid(self) -> None:
        with pytest.raises(ValidationError):
            NVDSettings(rate_limit_delay=-1.0)

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NVD_API_KEY", "test-key-abc123")
        monkeypatch.setenv("NVD_RESULTS_PER_PAGE", "500")
        s = NVDSettings()
        assert s.api_key == "test-key-abc123"
        assert s.results_per_page == 500


class TestTIKGSettings:
    def test_defaults(self) -> None:
        s = TIKGSettings()
        assert isinstance(s.neo4j, Neo4jSettings)
        assert isinstance(s.nvd, NVDSettings)
        assert s.log_level == "INFO"

    def test_nested_defaults(self) -> None:
        s = TIKGSettings()
        assert s.neo4j.uri == "bolt://localhost:7687"
        assert s.nvd.results_per_page == 2000
