"""Data masking strategies for PII fields."""

from __future__ import annotations

import re

from src.models import MaskingResult, MaskingStrategy


def mask_email(value: str) -> str:
    """Mask email: j***@example.com."""
    if "@" not in value:
        return "***"
    local, domain = value.split("@", 1)
    if len(local) <= 1:
        masked_local = "***"
    else:
        masked_local = local[0] + "***"
    return f"{masked_local}@{domain}"


def mask_phone(value: str) -> str:
    """Mask phone: keep last 4 digits only — ***-***-1234."""
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "***"
    last4 = digits[-4:]
    return f"***-***-{last4}"


def mask_credit_card(value: str) -> str:
    """Mask credit card: ****-****-****-1234."""
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "****-****-****-****"
    last4 = digits[-4:]
    return f"****-****-****-{last4}"


def mask_name(value: str) -> str:
    """Mask name: keep first letter — J***."""
    if not value.strip():
        return "***"
    first = value.strip()[0].upper()
    return f"{first}***"


def full_redact(_value: str) -> str:
    """Fully redact a value — returns static placeholder."""
    return "[REDACTED]"


def apply_masking(value: str, strategy: MaskingStrategy) -> MaskingResult:
    """Apply a masking strategy to a value.

    Returns a MaskingResult with the masked value and strategy used.
    Never raises — falls back to full redaction.
    """
    original_length = len(value)
    try:
        if strategy == MaskingStrategy.EMAIL:
            masked = mask_email(value)
        elif strategy == MaskingStrategy.PHONE:
            masked = mask_phone(value)
        elif strategy == MaskingStrategy.CREDIT_CARD:
            masked = mask_credit_card(value)
        elif strategy == MaskingStrategy.NAME:
            masked = mask_name(value)
        elif strategy == MaskingStrategy.FULL_REDACT:
            masked = full_redact(value)
        else:
            # NONE — return as-is
            masked = value
    except Exception:
        masked = "[REDACTED]"
        strategy = MaskingStrategy.FULL_REDACT

    return MaskingResult(
        original_length=original_length,
        masked_value=masked,
        strategy=strategy,
    )
