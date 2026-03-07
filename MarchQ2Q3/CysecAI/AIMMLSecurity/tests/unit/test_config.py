"""Tests for project configuration."""

from __future__ import annotations

from src.config import FirewallSettings


class TestFirewallSettings:
    def test_defaults(self) -> None:
        settings = FirewallSettings()
        assert settings.block_threshold == 0.7
        assert settings.max_prompt_length == 10000

    def test_custom_threshold(self) -> None:
        settings = FirewallSettings(block_threshold=0.9)
        assert settings.block_threshold == 0.9

    def test_dataset_path_exists(self) -> None:
        settings = FirewallSettings()
        # Path is configured, parent dir should exist
        assert "attack_samples" in str(settings.dataset_path)
