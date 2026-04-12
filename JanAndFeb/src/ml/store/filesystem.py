"""Filesystem-backed model store.

Implements the ``ModelStore`` Protocol. Each artifact is written as two files:

    {root}/{name}/{version}/model.bin      - raw bytes (joblib / torch state_dict)
    {root}/{name}/{version}/metadata.json  - JSON sidecar with hparams + metrics

This is the simplest possible implementation. The interface is intentionally
shaped like MLflow / S3 so switching to either is a one-file change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.common.logging_config import get_logger

logger = get_logger(__name__)


class FilesystemModelStore:
    """A directory-tree-based model store."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        logger.info("Filesystem model store initialized", root=str(self._root))

    # ------------------------------------------------------------------
    # ModelStore Protocol
    # ------------------------------------------------------------------
    def save(
        self,
        name: str,
        version: str,
        artifact: bytes,
        metadata: dict[str, Any],
    ) -> str:
        """Write the artifact and metadata, return the URI.

        The returned URI is the directory path (relative to CWD) — callers
        should treat it as opaque and pass it back to ``load`` unchanged.
        """
        target_dir = self._version_dir(name, version)
        target_dir.mkdir(parents=True, exist_ok=True)

        (target_dir / "model.bin").write_bytes(artifact)
        (target_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, default=str), encoding="utf-8"
        )

        uri = str(target_dir)
        logger.info(
            "Saved model artifact",
            name=name,
            version=version,
            uri=uri,
            artifact_bytes=len(artifact),
        )
        return uri

    def load(self, uri: str) -> tuple[bytes, dict[str, Any]]:
        """Read back an artifact previously saved at ``uri``."""
        path = Path(uri)
        if not path.is_dir():
            raise FileNotFoundError(f"Model artifact directory not found: {uri}")

        artifact = (path / "model.bin").read_bytes()
        metadata_raw = (path / "metadata.json").read_text(encoding="utf-8")
        metadata: dict[str, Any] = json.loads(metadata_raw)
        return artifact, metadata

    def exists(self, uri: str) -> bool:
        path = Path(uri)
        return (path / "model.bin").is_file() and (path / "metadata.json").is_file()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _version_dir(self, name: str, version: str) -> Path:
        return self._root / name / version
