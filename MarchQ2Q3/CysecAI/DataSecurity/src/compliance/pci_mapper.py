"""PCI-DSS (Payment Card Industry Data Security Standard) compliance mapper."""

from __future__ import annotations

from src.models import (
    ComplianceRequirement,
    ComplianceStatus,
    DataClassification,
    EncryptionStatus,
    TableInfo,
)

_PCI_REQUIREMENTS: list[dict[str, str]] = [
    {
        "id": "PCI-3.4",
        "article": "Req 3.4",
        "description": "Primary Account Numbers (PAN) rendered unreadable anywhere stored.",
    },
    {
        "id": "PCI-3.5",
        "article": "Req 3.5",
        "description": "Protect encryption keys against disclosure and misuse.",
    },
    {
        "id": "PCI-4.1",
        "article": "Req 4.1",
        "description": "Strong cryptography during transmission over open networks.",
    },
    {
        "id": "PCI-6.3",
        "article": "Req 6.3",
        "description": "Protect all system components from known vulnerabilities.",
    },
    {
        "id": "PCI-7.1",
        "article": "Req 7.1",
        "description": "Limit access to cardholder data to business need-to-know.",
    },
    {
        "id": "PCI-10.2",
        "article": "Req 10.2",
        "description": (
            "Implement audit trails to reconstruct all individual user access to cardholder data."
        ),
    },
]


def map_pci(
    tables: list[TableInfo],
    encryption: EncryptionStatus,
) -> list[ComplianceRequirement]:
    """Map scan findings to PCI-DSS requirements."""
    pci_tables = [
        t for t in tables if any(c.classification == DataClassification.PCI for c in t.columns)
    ]
    results: list[ComplianceRequirement] = []

    for req in _PCI_REQUIREMENTS:
        req_id = req["id"]
        findings: list[str] = []
        remediation = ""
        status = ComplianceStatus.PASS

        if req_id == "PCI-3.4":
            # Check if PAN columns are unencrypted
            unprotected = [
                f"{t.table_name}.{c.column_name}"
                for t in pci_tables
                for c in t.columns
                if c.classification == DataClassification.PCI
            ]
            if unprotected and not encryption.tde_enabled:
                findings.extend(unprotected[:5])
                remediation = (
                    "Encrypt or tokenize all PAN fields. Never store full PANs in plaintext."
                )
                status = ComplianceStatus.FAIL
            elif unprotected:
                findings.append(
                    f"{len(unprotected)} PAN column(s) detected — verify encryption is applied."
                )
                status = ComplianceStatus.FAIL
                remediation = "Verify column-level encryption is applied to all PAN fields."

        elif req_id == "PCI-4.1":
            if not encryption.tls_enabled:
                findings.append("Database connection is not encrypted (TLS disabled).")
                remediation = "Enable TLS 1.2 or higher on all database connections."
                status = ComplianceStatus.FAIL
            elif encryption.tls_version and "1.0" in encryption.tls_version:
                findings.append(f"TLS version {encryption.tls_version!r} is insecure.")
                remediation = "Upgrade to TLS 1.2 or higher."
                status = ComplianceStatus.FAIL

        elif req_id in {"PCI-3.5", "PCI-6.3", "PCI-7.1", "PCI-10.2"}:
            status = ComplianceStatus.NA
            findings.append("Requires manual policy review; cannot be fully automated.")

        results.append(
            ComplianceRequirement(
                requirement_id=req_id,
                framework="PCI-DSS",
                article=req["article"],
                description=req["description"],
                status=status,
                findings=findings,
                remediation=remediation,
            )
        )

    return results
