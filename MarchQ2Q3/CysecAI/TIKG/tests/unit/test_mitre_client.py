"""Tests for the MITRE ATT&CK client."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ingestion.mitre_client import MITREClient, _parse_technique
from src.models import AttackTechnique


def _make_attack_pattern(
    technique_id: str = "T1059",
    name: str = "Command and Scripting Interpreter",
    description: str = "Adversaries may abuse interpreters.",
    tactic: str = "execution",
    platforms: list[str] | None = None,
    revoked: bool = False,
    deprecated: bool = False,
    detection: str | None = "Monitor command execution.",
) -> dict[str, Any]:
    return {
        "type": "attack-pattern",
        "id": f"attack-pattern--{technique_id}",
        "name": name,
        "description": description,
        "revoked": revoked,
        "x_mitre_deprecated": deprecated,
        "x_mitre_platforms": platforms or ["Windows", "Linux", "macOS"],
        "detection": detection,
        "external_references": [{"source_name": "mitre-attack", "external_id": technique_id}],
        "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": tactic}],
        "x_mitre_is_subtechnique": "." in technique_id,
    }


def _make_bundle(objects: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "bundle", "id": "bundle--test", "objects": objects}


class TestParseTechnique:
    def test_valid_technique(self) -> None:
        obj = _make_attack_pattern()
        tech = _parse_technique(obj)
        assert tech is not None
        assert tech.technique_id == "T1059"
        assert tech.tactic == "execution"
        assert "Windows" in tech.platforms

    def test_revoked_returns_none(self) -> None:
        obj = _make_attack_pattern(revoked=True)
        assert _parse_technique(obj) is None

    def test_deprecated_returns_none(self) -> None:
        obj = _make_attack_pattern(deprecated=True)
        assert _parse_technique(obj) is None

    def test_no_mitre_id_returns_none(self) -> None:
        obj = _make_attack_pattern()
        obj["external_references"] = [{"source_name": "other", "external_id": "X999"}]
        assert _parse_technique(obj) is None

    def test_detection_preserved(self) -> None:
        obj = _make_attack_pattern(detection="Check process tree.")
        tech = _parse_technique(obj)
        assert tech is not None
        assert tech.detection == "Check process tree."

    def test_no_detection(self) -> None:
        obj = _make_attack_pattern(detection=None)
        tech = _parse_technique(obj)
        assert tech is not None
        assert tech.detection is None

    def test_no_kill_chain(self) -> None:
        obj = _make_attack_pattern()
        obj["kill_chain_phases"] = []
        tech = _parse_technique(obj)
        assert tech is not None
        assert tech.tactic == ""

    def test_subtechnique_id(self) -> None:
        obj = _make_attack_pattern(technique_id="T1059.001")
        tech = _parse_technique(obj)
        assert tech is not None
        assert tech.technique_id == "T1059.001"


class TestMITREClient:
    @pytest.mark.asyncio
    async def test_fetch_techniques_returns_list(self) -> None:
        objects = [
            _make_attack_pattern("T1059"),
            _make_attack_pattern("T1078"),
            {"type": "relationship"},  # non-attack-pattern, should be skipped
            _make_attack_pattern("T1190", revoked=True),  # revoked, should be skipped
        ]
        bundle = _make_bundle(objects)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=bundle)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            async with MITREClient() as client:
                techniques = await client.fetch_techniques()

        assert len(techniques) == 2
        assert all(isinstance(t, AttackTechnique) for t in techniques)
        ids = {t.technique_id for t in techniques}
        assert "T1059" in ids
        assert "T1078" in ids
        assert "T1190" not in ids

    @pytest.mark.asyncio
    async def test_fetch_techniques_empty_bundle(self) -> None:
        bundle = _make_bundle([])
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=bundle)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            async with MITREClient() as client:
                techniques = await client.fetch_techniques()

        assert techniques == []
