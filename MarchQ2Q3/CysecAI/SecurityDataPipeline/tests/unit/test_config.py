"""Tests for SIEM configuration."""

from __future__ import annotations

import pytest

from src.config import GeneratorSettings, SIEMSettings


class TestGeneratorSettings:
    """GeneratorSettings validation tests."""

    def test_defaults(self) -> None:
        settings = GeneratorSettings()
        assert settings.num_events == 10000
        assert settings.attack_rate == 0.05
        assert settings.num_users == 50
        assert settings.num_hosts == 20
        assert settings.seed == 42

    def test_custom_values(self) -> None:
        settings = GeneratorSettings(num_events=500, attack_rate=0.10, seed=99)
        assert settings.num_events == 500
        assert settings.attack_rate == 0.10
        assert settings.seed == 99

    def test_rejects_low_attack_rate(self) -> None:
        with pytest.raises(ValueError, match=r"greater than or equal to 0\.01"):
            GeneratorSettings(attack_rate=0.001)

    def test_rejects_high_attack_rate(self) -> None:
        with pytest.raises(ValueError, match=r"less than or equal to 0\.3"):
            GeneratorSettings(attack_rate=0.50)

    def test_rejects_too_few_events(self) -> None:
        with pytest.raises(ValueError, match="greater than or equal to 100"):
            GeneratorSettings(num_events=10)

    def test_rejects_too_few_users(self) -> None:
        with pytest.raises(ValueError, match="greater than or equal to 5"):
            GeneratorSettings(num_users=2)


class TestSIEMSettings:
    """SIEMSettings tests."""

    def test_defaults(self) -> None:
        settings = SIEMSettings()
        assert settings.sigma_rules_dir == "rules"
        assert settings.correlation_window_seconds == 600
        assert settings.log_level == "INFO"

    def test_nested_generator(self) -> None:
        settings = SIEMSettings()
        assert settings.generator.num_events == 10000
        assert settings.generator.seed == 42

    def test_inherits_base_settings(self) -> None:
        settings = SIEMSettings()
        assert settings.environment == "development"
        assert settings.is_production() is False
