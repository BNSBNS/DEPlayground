"""PDPA (Personal Data Protection Act — Singapore) compliance mapper."""

from __future__ import annotations

from src.models import ComplianceRequirement, ComplianceStatus, EncryptionStatus, TableInfo

_PDPA_REQUIREMENTS: list[dict[str, str]] = [
    {
        "id": "PDPA-1",
        "article": "Part III",
        "description": "Consent obligation — personal data collected with consent.",
    },
    {
        "id": "PDPA-2",
        "article": "Part IV",
        "description": "Purpose limitation — personal data used only for stated purposes.",
    },
    {
        "id": "PDPA-3",
        "article": "Part VI",
        "description": "Access and correction — data subjects can access their data.",
    },
    {
        "id": "PDPA-4",
        "article": "Part VII",
        "description": "Care obligation — protect personal data from unauthorised access.",
    },
    {
        "id": "PDPA-5",
        "article": "Art. 24",
        "description": "Data masking — mask PII in non-production environments.",
    },
    {
        "id": "PDPA-6",
        "article": "Art. 26",
        "description": "Retention limitation — do not retain data beyond its purpose.",
    },
    {
        "id": "PDPA-7",
        "article": "Art. 13",
        "description": "Transfer limitation — protect personal data transferred overseas.",
    },
]


def map_pdpa(
    tables: list[TableInfo],
    encryption: EncryptionStatus,
) -> list[ComplianceRequirement]:
    """Map scan findings to PDPA requirements."""
    pii_tables = [t for t in tables if t.has_pii]
    results: list[ComplianceRequirement] = []

    for req in _PDPA_REQUIREMENTS:
        req_id = req["id"]
        findings: list[str] = []
        remediation = ""
        status = ComplianceStatus.PASS

        if req_id == "PDPA-4":
            # Care obligation: check TLS + TDE
            if not encryption.tls_enabled:
                findings.append("Database connection is not encrypted (TLS disabled).")
                remediation = "Enable TLS/SSL on the database server."
                status = ComplianceStatus.FAIL
            if not encryption.tde_enabled:
                findings.append("Encryption-at-rest (TDE) is not enabled.")
                if remediation:
                    remediation += " Enable TDE or filesystem encryption."
                else:
                    remediation = "Enable TDE or filesystem-level encryption."
                status = ComplianceStatus.FAIL

        elif req_id == "PDPA-5":
            # Masking: check if PII columns are masked
            unmasked = [
                f"{t.table_name}.{c.column_name}" for t in pii_tables for c in t.pii_columns
            ]
            if unmasked:
                findings.extend(unmasked[:10])  # limit to 10
                remediation = "Apply masking strategies to all PII columns in non-prod."
                status = ComplianceStatus.FAIL

        elif req_id in {"PDPA-1", "PDPA-2", "PDPA-3", "PDPA-6", "PDPA-7"}:
            # These require policy review — mark as N/A (automated tool cannot assess)
            status = ComplianceStatus.NA
            findings.append("Requires manual policy review; cannot be automated.")

        results.append(
            ComplianceRequirement(
                requirement_id=req_id,
                framework="PDPA",
                article=req["article"],
                description=req["description"],
                status=status,
                findings=findings,
                remediation=remediation,
            )
        )

    return results
