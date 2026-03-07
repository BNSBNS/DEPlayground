"""Shared test fixtures for AIMMLSecurity."""

from __future__ import annotations

import mlflow
import pytest

from src.classifier.dataset import LabeledSample, build_dataset
from src.classifier.taxonomy import AttackType


@pytest.fixture(autouse=True, scope="session")
def configure_mlflow(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Point MLflow at a temp dir for the test session."""
    mlruns = tmp_path_factory.mktemp("mlruns")
    mlflow.set_tracking_uri(f"file:///{mlruns}")


@pytest.fixture()
def dataset() -> list[LabeledSample]:
    """Full 500-sample dataset."""
    return build_dataset()


@pytest.fixture()
def attack_samples(dataset: list[LabeledSample]) -> list[LabeledSample]:
    """Attack samples only (no benign)."""
    return [s for s in dataset if s.label != AttackType.BENIGN]


@pytest.fixture()
def benign_samples(dataset: list[LabeledSample]) -> list[LabeledSample]:
    """Benign samples only."""
    return [s for s in dataset if s.label == AttackType.BENIGN]
