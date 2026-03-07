"""Tests for shared configuration patterns."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cysec_shared.config import BaseProjectSettings, KafkaSettings

if TYPE_CHECKING:
    import pytest


class TestKafkaSettings:
    """KafkaSettings tests."""

    def test_defaults(self) -> None:
        settings = KafkaSettings()
        assert settings.bootstrap_servers == "localhost:9092"
        assert settings.alerts_topic == "cysec.alerts"
        assert settings.group_id == "cysec-default"

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "broker:29092")
        monkeypatch.setenv("KAFKA_ALERTS_TOPIC", "custom.alerts")
        settings = KafkaSettings()
        assert settings.bootstrap_servers == "broker:29092"
        assert settings.alerts_topic == "custom.alerts"


class TestBaseProjectSettings:
    """BaseProjectSettings tests."""

    def test_defaults(self) -> None:
        settings = BaseProjectSettings()
        assert settings.log_level == "INFO"
        assert settings.log_json_format is False
        assert settings.environment == "development"
        assert settings.debug is False
        assert settings.is_production() is False

    def test_production_check(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENVIRONMENT", "production")
        settings = BaseProjectSettings()
        assert settings.is_production() is True

    def test_nested_kafka_settings(self) -> None:
        settings = BaseProjectSettings()
        assert settings.kafka.bootstrap_servers == "localhost:9092"
        assert settings.kafka.alerts_topic == "cysec.alerts"
