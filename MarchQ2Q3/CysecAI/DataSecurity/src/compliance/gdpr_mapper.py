"""GDPR (General Data Protection Regulation — EU) compliance mapper."""

from __future__ import annotations

from src.models import ComplianceRequirement, ComplianceStatus, EncryptionStatus, TableInfo

_GDPR_REQUIREMENTS: list[dict[str, str]] = [
    {
        "id": "GDPR-1",
        "article": "Art. 5(1)(f)",
        "description": "Integrity and confidentiality — personal data protected against "
        "unauthorised processing, loss, or destruction.",
    },
    {
        "id": "GDPR-2",
        "article": "Art. 25",
        "description": "Data protection by design — pseudonymisation and minimisation.",
    },
    {
        "id": "GDPR-3",
        "article": "Art. 32",
        "description": "Security of processing — encryption and pseudonymisation of personal data.",
    },
    {
        "id": "GDPR-4",
        "article": "Art. 30",
        "description": "Records of processing activities maintained.",
    },
    {
        "id": "GDPR-5",
        "article": "Art. 17",
        "description": "Right to erasure ('right to be forgotten') — mechanism in place.",
    },
    {
        "id": "GDPR-6",
        "article": "Art. 33",
        "description": "Breach notification — data breach notified within 72 hours.",
    },
]


def map_gdpr(
    tables: list[TableInfo],
    encryption: EncryptionStatus,
) -> list[ComplianceRequirement]:
    """Map scan findings to GDPR requirements."""
    pii_tables = [t for t in tables if t.has_pii]
    results: list[ComplianceRequirement] = []

    for req in _GDPR_REQUIREMENTS:
        req_id = req["id"]
        findings: list[str] = []
        remediation = ""
        status = ComplianceStatus.PASS

        if req_id == "GDPR-1":
            if not encryption.tls_enabled:
                findings.append("Database connection lacks TLS encryption.")
                remediation = "Enable TLS on the database server."
                status = ComplianceStatus.FAIL
            if not encryption.tde_enabled and pii_tables:
                findings.append("PII tables are stored without encryption-at-rest.")
                remediation += " Enable TDE or filesystem encryption."
                status = ComplianceStatus.FAIL

        elif req_id == "GDPR-3":
            if not encryption.tde_enabled:
                findings.append("Encryption of personal data at rest is not confirmed.")
                remediation = "Enable TDE or use column-level encryption for PII fields."
                status = ComplianceStatus.FAIL
            if not encryption.tls_enabled:
                findings.append("Encryption in transit is not confirmed (no TLS).")
                if not remediation:
                    remediation = "Enable TLS and TDE."
                status = ComplianceStatus.FAIL

        elif req_id == "GDPR-2":
            # Check for pseudonymisation (masking)
            unmasked_pii_count = sum(len(t.pii_columns) for t in pii_tables)
            if unmasked_pii_count > 0:
                findings.append(
                    f"{unmasked_pii_count} PII column(s) identified without pseudonymisation."
                )
                remediation = "Apply masking or pseudonymisation to all personal data columns."
                status = ComplianceStatus.FAIL

        elif req_id in {"GDPR-4", "GDPR-5", "GDPR-6"}:
            status = ComplianceStatus.NA
            findings.append("Requires manual policy review; cannot be fully automated.")

        results.append(
            ComplianceRequirement(
                requirement_id=req_id,
                framework="GDPR",
                article=req["article"],
                description=req["description"],
                status=status,
                findings=findings,
                remediation=remediation,
            )
        )

    return results
