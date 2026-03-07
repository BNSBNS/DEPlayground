"""Tests for configuration."""

from src.config import DetectorSettings, PostgresSettings, Settings


class TestPostgresSettings:
    def test_get_dsn_from_components(self) -> None:
        settings = PostgresSettings(
            user="test", password="pass", host="localhost", port=5432, db="testdb"
        )
        assert settings.get_dsn() == "postgresql://test:pass@localhost:5432/testdb"

    def test_get_dsn_explicit(self) -> None:
        settings = PostgresSettings(dsn="postgresql://custom@host/db")
        assert settings.get_dsn() == "postgresql://custom@host/db"


class TestDetectorSettings:
    def test_defaults(self) -> None:
        settings = DetectorSettings()
        assert settings.freshness_warning_minutes == 60
        assert settings.freshness_critical_minutes == 120
        assert settings.volume_lookback_days == 14
        assert settings.volume_warning_zscore == 2.0


class TestSettings:
    def test_defaults(self) -> None:
        settings = Settings()
        assert settings.log_level == "INFO"
        assert settings.environment == "development"
        assert not settings.is_production()
