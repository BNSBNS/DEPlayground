from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.logging import get_logger
from src.models.contracts import Contract, ContractStatus
from src.models.versions import ContractVersion

log = get_logger(__name__)


def load_contract(path: Path) -> tuple[Contract, ContractVersion]:
    """Parse a YAML contract file into Contract + ContractVersion models."""
    raw = path.read_text(encoding="utf-8")
    data: dict[str, Any] = yaml.safe_load(raw)

    metadata = data.get("metadata", {})
    contract = Contract(
        name=metadata["name"],
        dataset=metadata["dataset"],
        owner_team=metadata["owner_team"],
        owner_contact=metadata["owner_contact"],
        status=ContractStatus(metadata.get("status", "draft")),
    )

    version = ContractVersion(
        contract_id=contract.id,
        version=data.get("version", "1.0.0"),
        schema_spec=data.get("schema", {}),
        quality_spec=data.get("quality", {}),
        sla_spec=data.get("sla", {}),
        consumers=data.get("consumers", []),
        changelog=data.get("changelog", "Initial version"),
    )

    contract.current_version_id = version.id

    log.info(
        "contract_parsed",
        name=contract.name,
        dataset=contract.dataset,
        version=version.version,
    )
    return contract, version
