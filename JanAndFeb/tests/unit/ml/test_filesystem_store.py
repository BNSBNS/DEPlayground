"""Unit tests for FilesystemModelStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ml.store.filesystem import FilesystemModelStore


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    store = FilesystemModelStore(tmp_path)
    artifact = b"fake-model-bytes"
    metadata = {"hparams": {"lr": 0.001}, "notes": "unit-test"}

    uri = store.save("gru", "1.0.0", artifact, metadata)

    assert store.exists(uri)
    loaded_artifact, loaded_metadata = store.load(uri)
    assert loaded_artifact == artifact
    assert loaded_metadata == metadata


def test_exists_false_for_missing(tmp_path: Path) -> None:
    store = FilesystemModelStore(tmp_path)
    assert store.exists(str(tmp_path / "nope")) is False


def test_load_missing_raises(tmp_path: Path) -> None:
    store = FilesystemModelStore(tmp_path)
    with pytest.raises(FileNotFoundError):
        store.load(str(tmp_path / "does-not-exist"))


def test_save_creates_nested_directory(tmp_path: Path) -> None:
    store = FilesystemModelStore(tmp_path)
    uri = store.save("lightgbm", "2026.04.11", b"x", {})
    assert Path(uri).is_dir()
    assert (Path(uri) / "model.bin").is_file()
    assert (Path(uri) / "metadata.json").is_file()
