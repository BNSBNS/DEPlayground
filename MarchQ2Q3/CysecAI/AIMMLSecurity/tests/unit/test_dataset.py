"""Tests for the attack dataset."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from src.classifier.dataset import (
    BENIGN_SAMPLES,
    DATA_EXFILTRATION_SAMPLES,
    INDIRECT_INJECTION_SAMPLES,
    JAILBREAK_SAMPLES,
    PII_EXTRACTION_SAMPLES,
    PROMPT_INJECTION_SAMPLES,
    ROLE_HIJACKING_SAMPLES,
    LabeledSample,
    build_dataset,
    load_dataset,
    save_dataset,
)
from src.classifier.taxonomy import AttackType


class TestDatasetSize:
    def test_total_samples(self, dataset: list[LabeledSample]) -> None:
        assert len(dataset) == 500

    def test_prompt_injection_count(self) -> None:
        assert len(PROMPT_INJECTION_SAMPLES) == 50

    def test_jailbreak_count(self) -> None:
        assert len(JAILBREAK_SAMPLES) == 50

    def test_data_exfiltration_count(self) -> None:
        assert len(DATA_EXFILTRATION_SAMPLES) == 50

    def test_pii_extraction_count(self) -> None:
        assert len(PII_EXTRACTION_SAMPLES) == 50

    def test_role_hijacking_count(self) -> None:
        assert len(ROLE_HIJACKING_SAMPLES) == 50

    def test_indirect_injection_count(self) -> None:
        assert len(INDIRECT_INJECTION_SAMPLES) == 50

    def test_benign_count(self) -> None:
        assert len(BENIGN_SAMPLES) == 200


class TestDatasetLabels:
    def test_all_attack_types_present(self, dataset: list[LabeledSample]) -> None:
        labels = {s.label for s in dataset}
        for attack_type in AttackType:
            assert attack_type.value in labels

    def test_attack_samples_labeled_correctly(self, attack_samples: list[LabeledSample]) -> None:
        assert len(attack_samples) == 300
        for sample in attack_samples:
            assert sample.label != AttackType.BENIGN

    def test_benign_samples_labeled_correctly(self, benign_samples: list[LabeledSample]) -> None:
        assert len(benign_samples) == 200
        for sample in benign_samples:
            assert sample.label == AttackType.BENIGN


class TestDatasetQuality:
    def test_all_samples_non_empty(self, dataset: list[LabeledSample]) -> None:
        for sample in dataset:
            assert len(sample.text.strip()) > 0

    def test_no_duplicate_texts(self, dataset: list[LabeledSample]) -> None:
        texts = [s.text for s in dataset]
        assert len(texts) == len(set(texts)), "Dataset contains duplicate texts"

    def test_minimum_text_length(self, dataset: list[LabeledSample]) -> None:
        for sample in dataset:
            assert len(sample.text) >= 10, f"Sample too short: {sample.text!r}"


class TestDatasetIO:
    def test_save_and_load(self, tmp_path: Path) -> None:
        path = tmp_path / "test_dataset.json"
        count = save_dataset(path)
        assert count == 500
        assert path.exists()

        loaded = load_dataset(path)
        assert len(loaded) == 500
        assert all(isinstance(s, LabeledSample) for s in loaded)

    def test_roundtrip_preserves_labels(self, tmp_path: Path) -> None:
        path = tmp_path / "test_dataset.json"
        save_dataset(path)
        loaded = load_dataset(path)

        original = build_dataset()
        for orig, loaded_sample in zip(original, loaded, strict=True):
            assert orig.text == loaded_sample.text
            assert orig.label == loaded_sample.label
