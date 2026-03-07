"""Classify database columns into PII/PHI/PCI/PUBLIC categories."""

from __future__ import annotations

from src.models import DataClassification, MaskingStrategy, PIIType

# PHI-specific PII types (Protected Health Information)
_PHI_TYPES: frozenset[PIIType] = frozenset({PIIType.DATE_OF_BIRTH, PIIType.NAME, PIIType.ADDRESS})

# PHI column name keywords
_PHI_COLUMN_KEYWORDS: frozenset[str] = frozenset(
    {
        "diagnosis",
        "condition",
        "medication",
        "prescription",
        "icd",
        "health",
        "medical",
        "treatment",
        "procedure",
        "lab",
        "blood",
        "bmi",
        "weight",
        "height",
        "allergy",
        "patient",
    }
)

# PCI-specific PII types
_PCI_TYPES: frozenset[PIIType] = frozenset({PIIType.CREDIT_CARD})

# PCI column name keywords
_PCI_COLUMN_KEYWORDS: frozenset[str] = frozenset(
    {
        "credit_card",
        "card_number",
        "pan",
        "cvv",
        "expiry",
        "expiration",
        "card_type",
        "payment_method",
        "billing",
    }
)

# Default masking strategies per PII type
_MASKING_MAP: dict[PIIType, MaskingStrategy] = {
    PIIType.EMAIL: MaskingStrategy.EMAIL,
    PIIType.PHONE: MaskingStrategy.PHONE,
    PIIType.CREDIT_CARD: MaskingStrategy.CREDIT_CARD,
    PIIType.NAME: MaskingStrategy.NAME,
    PIIType.NRIC: MaskingStrategy.FULL_REDACT,
    PIIType.SSN: MaskingStrategy.FULL_REDACT,
    PIIType.ADDRESS: MaskingStrategy.FULL_REDACT,
    PIIType.IP_ADDRESS: MaskingStrategy.FULL_REDACT,
    PIIType.DATE_OF_BIRTH: MaskingStrategy.FULL_REDACT,
    PIIType.UNKNOWN: MaskingStrategy.FULL_REDACT,
}


def classify_column(
    column_name: str,
    pii_types: list[PIIType],
) -> tuple[DataClassification, MaskingStrategy]:
    """Classify a column and recommend a masking strategy.

    Returns (DataClassification, MaskingStrategy).
    """
    if not pii_types:
        return DataClassification.PUBLIC, MaskingStrategy.NONE

    col_lower = column_name.lower()

    # PCI check — payment card data takes priority
    if any(p in _PCI_TYPES for p in pii_types) or any(
        kw in col_lower for kw in _PCI_COLUMN_KEYWORDS
    ):
        masking = _MASKING_MAP.get(PIIType.CREDIT_CARD, MaskingStrategy.FULL_REDACT)
        if PIIType.CREDIT_CARD in pii_types:
            return DataClassification.PCI, masking
        # Column name suggests PCI but no regex match — still flag
        if any(kw in col_lower for kw in _PCI_COLUMN_KEYWORDS):
            return DataClassification.PCI, MaskingStrategy.CREDIT_CARD

    # PHI check — health-related columns
    if any(kw in col_lower for kw in _PHI_COLUMN_KEYWORDS):
        masking = MaskingStrategy.FULL_REDACT
        for pii_type in pii_types:
            if pii_type in _MASKING_MAP:
                masking = _MASKING_MAP[pii_type]
                break
        return DataClassification.PHI, masking

    # PII — general personal data
    best_pii = pii_types[0]
    masking = _MASKING_MAP.get(best_pii, MaskingStrategy.FULL_REDACT)
    return DataClassification.PII, masking


def get_masking_strategy(pii_type: PIIType) -> MaskingStrategy:
    """Return the default masking strategy for a given PII type."""
    return _MASKING_MAP.get(pii_type, MaskingStrategy.FULL_REDACT)
