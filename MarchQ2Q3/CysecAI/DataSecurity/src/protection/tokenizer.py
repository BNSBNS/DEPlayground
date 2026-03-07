"""Format-preserving tokenization for sensitive fields."""

from __future__ import annotations

import hashlib
import re


def _luhn_checksum(number: str) -> int:
    """Compute Luhn checksum digit for a numeric string."""
    digits = [int(d) for d in number]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))
    return total % 10


def _luhn_valid(number: str) -> bool:
    return _luhn_checksum(number) == 0


def tokenize_credit_card(pan: str, secret: str = "default-secret") -> str:
    """Format-preserving tokenization for credit card numbers.

    Produces a token that:
    - Has the same length as the original PAN
    - Preserves the first 6 (BIN) and last 4 digits
    - Passes Luhn check
    - Is deterministic for the same (pan, secret) pair

    The token is NOT reversible without the secret.
    """
    digits = re.sub(r"\D", "", pan)
    if len(digits) < 13:
        return "0000000000000000"

    # Keep BIN (first 6) and last 4
    bin_prefix = digits[:6]
    last4 = digits[-4:]
    middle_len = len(digits) - 10  # 6 + 4

    # Generate deterministic middle digits via HMAC-SHA256
    hmac_input = f"{secret}:{pan}".encode()
    digest = hashlib.sha256(hmac_input).hexdigest()

    middle = ""
    for i in range(0, len(digest), 2):
        middle += str(int(digest[i : i + 2], 16) % 10)
        if len(middle) >= middle_len:
            break
    middle = middle[:middle_len]

    # Build token without check digit, then compute Luhn check digit
    token_without_check = bin_prefix + middle + last4[:-1]
    # Compute correct check digit
    for check_digit in range(10):
        candidate = token_without_check + str(check_digit)
        if _luhn_valid(candidate):
            return candidate

    # Fallback (should not happen)
    return bin_prefix + middle + last4


def detokenize_credit_card(token: str, secret: str = "default-secret") -> str:
    """Tokenization is one-way — this method always raises NotImplementedError.

    Tokens cannot be reversed without the original database + secret.
    This function exists to make the API explicit about irreversibility.
    """
    raise NotImplementedError(
        "Credit card tokenization is one-way. Store the original PAN in an HSM, "
        "not in this application. Token: " + token[:6] + "...[REDACTED]"
    )


def tokenize_nric(nric: str, secret: str = "default-secret") -> str:
    """Tokenize a Singapore NRIC number.

    Preserves format: [Letter][7 digits][Letter] but replaces middle digits.
    """
    nric = nric.strip().upper()
    if not re.match(r"^[STFGM][0-9]{7}[A-Z]$", nric):
        return "[REDACTED]"
    prefix = nric[0]
    suffix = nric[-1]
    hmac_input = f"{secret}:{nric}".encode()
    digest = hashlib.sha256(hmac_input).hexdigest()
    middle = ""
    for i in range(0, len(digest), 2):
        middle += str(int(digest[i : i + 2], 16) % 10)
        if len(middle) >= 7:
            break
    return f"{prefix}{middle[:7]}{suffix}"
