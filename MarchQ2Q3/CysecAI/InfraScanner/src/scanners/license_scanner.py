"""License risk scanner — categorize package licenses by compliance risk."""

from __future__ import annotations

from src.models import Dependency, LicenseFinding, LicenseRisk

# SPDX license identifiers mapped to risk category
_COPYLEFT_LICENSES: frozenset[str] = frozenset(
    {
        "GPL-2.0",
        "GPL-2.0-only",
        "GPL-2.0-or-later",
        "GPL-3.0",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
        "AGPL-3.0",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
        "LGPL-2.0",
        "LGPL-2.1",
        "LGPL-3.0",
        "EUPL-1.1",
        "EUPL-1.2",
        "CDDL-1.0",
        "MPL-2.0",
        "CC-BY-SA-4.0",
    }
)

_RESTRICTED_LICENSES: frozenset[str] = frozenset(
    {
        "SSPL-1.0",
        "BSL-1.1",
        "Commons-Clause",
        "BUSL-1.1",
        "Elastic-2.0",
        "CC-BY-NC-4.0",
        "CC-BY-NC-SA-4.0",
        "PROPRIETARY",
    }
)

_ALLOWED_LICENSES: frozenset[str] = frozenset(
    {
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "Unlicense",
        "0BSD",
        "CC0-1.0",
        "WTFPL",
        "Python-2.0",
        "PSF-2.0",
        "Artistic-2.0",
    }
)


def _normalise_license(raw: str) -> str:
    """Normalise common free-form license strings to SPDX identifiers."""
    mapping: dict[str, str] = {
        "mit": "MIT",
        "apache 2": "Apache-2.0",
        "apache-2": "Apache-2.0",
        "apache2": "Apache-2.0",
        "apache license 2.0": "Apache-2.0",
        "apache software license": "Apache-2.0",
        "bsd": "BSD-3-Clause",
        "bsd 2-clause": "BSD-2-Clause",
        "bsd 3-clause": "BSD-3-Clause",
        "bsd-2-clause": "BSD-2-Clause",
        "bsd-3-clause": "BSD-3-Clause",
        "isc": "ISC",
        "gpl": "GPL-3.0",
        "gpl2": "GPL-2.0",
        "gpl3": "GPL-3.0",
        "gpl-2": "GPL-2.0",
        "gpl-3": "GPL-3.0",
        "lgpl": "LGPL-3.0",
        "agpl": "AGPL-3.0",
        "mpl": "MPL-2.0",
        "cc0": "CC0-1.0",
        "public domain": "CC0-1.0",
        "unlicense": "Unlicense",
        "psf": "PSF-2.0",
    }
    lower = raw.strip().lower()
    return mapping.get(lower, raw.strip())


def categorise_license(license_id: str) -> LicenseRisk:
    """Categorise a license SPDX ID into a risk level."""
    normalised = _normalise_license(license_id)
    if normalised.upper() in {li.upper() for li in _COPYLEFT_LICENSES}:
        return LicenseRisk.COPYLEFT
    if normalised.upper() in {li.upper() for li in _RESTRICTED_LICENSES}:
        return LicenseRisk.RESTRICTED
    if normalised.upper() in {li.upper() for li in _ALLOWED_LICENSES}:
        return LicenseRisk.ALLOWED
    return LicenseRisk.UNKNOWN


def scan_licenses(
    packages: list[tuple[str, str]],  # (package_name, license_id)
) -> list[LicenseFinding]:
    """Categorise a list of (package, license) pairs.

    Returns only findings where risk is COPYLEFT, RESTRICTED, or UNKNOWN.
    """
    findings: list[LicenseFinding] = []
    for pkg, lic in packages:
        risk = categorise_license(lic)
        if risk != LicenseRisk.ALLOWED:
            findings.append(LicenseFinding(package=pkg, license_id=lic, risk=risk))
    return findings


def scan_dependencies_licenses(_deps: list[Dependency]) -> list[LicenseFinding]:
    """Scan dependencies that have license metadata attached.

    In practice, license info is obtained from package metadata (PyPI, npm).
    This function processes deps that have license info embedded.
    """
    # Default: no license info available in Dependency model
    # Real-world usage would enrich deps from PyPI/npm metadata first
    return []
