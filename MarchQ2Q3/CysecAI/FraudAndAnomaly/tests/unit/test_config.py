"""Tests for FraudAndAnomaly configuration."""

from __future__ import annotations

import pytest

from src.config import FraudSettings, GeneratorSettings


class TestGeneratorSettings:
    """GeneratorSettings validation tests."""

    def test_defaults(self) -> None:
        settings = GeneratorSettings()
        assert settings.num_transactions == 100_000
        assert settings.fraud_rate == 0.03
        assert settings.num_users == 5000
        assert settings.num_merchants == 200
        assert settings.seed == 42

    def test_custom_values(self) -> None:
        settings = GeneratorSettings(num_transactions=5000, fraud_rate=0.05, seed=99)
        assert settings.num_transactions == 5000
        assert settings.fraud_rate == 0.05
        assert settings.seed == 99

    def test_rejects_fraud_rate_too_high(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            GeneratorSettings(fraud_rate=0.25)

    def test_rejects_fraud_rate_too_low(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            GeneratorSettings(fraud_rate=0.005)

    def test_rejects_too_few_transactions(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            GeneratorSettings(num_transactions=500)

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GENERATOR_FRAUD_RATE", "0.10")
        monkeypatch.setenv("GENERATOR_SEED", "123")
        settings = GeneratorSettings()
        assert settings.fraud_rate == 0.10
        assert settings.seed == 123


class TestFraudSettings:
    """FraudSettings tests."""

    def test_defaults(self) -> None:
        settings = FraudSettings()
        assert settings.api_port == 8101
        assert settings.api_key == "changeme"
        assert settings.generator.num_transactions == 100_000

    def test_inherits_base_settings(self) -> None:
        settings = FraudSettings()
        assert settings.log_level == "INFO"
        assert settings.kafka.alerts_topic == "cysec.alerts"
        assert settings.is_production() is False
