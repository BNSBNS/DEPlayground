"""Tests for license risk scanner."""

from __future__ import annotations

from src.models import LicenseRisk
from src.scanners.license_scanner import categorise_license, scan_licenses


class TestCategoriseLicense:
    def test_mit_allowed(self) -> None:
        assert categorise_license("MIT") == LicenseRisk.ALLOWED

    def test_apache_allowed(self) -> None:
        assert categorise_license("Apache-2.0") == LicenseRisk.ALLOWED

    def test_bsd_allowed(self) -> None:
        assert categorise_license("BSD-3-Clause") == LicenseRisk.ALLOWED

    def test_gpl_copyleft(self) -> None:
        assert categorise_license("GPL-3.0") == LicenseRisk.COPYLEFT

    def test_agpl_copyleft(self) -> None:
        assert categorise_license("AGPL-3.0") == LicenseRisk.COPYLEFT

    def test_lgpl_copyleft(self) -> None:
        assert categorise_license("LGPL-3.0") == LicenseRisk.COPYLEFT

    def test_sspl_restricted(self) -> None:
        assert categorise_license("SSPL-1.0") == LicenseRisk.RESTRICTED

    def test_unknown_license(self) -> None:
        assert categorise_license("CUSTOM-LICENSE-1.0") == LicenseRisk.UNKNOWN

    def test_normalise_free_form(self) -> None:
        assert categorise_license("mit") == LicenseRisk.ALLOWED
        assert categorise_license("apache 2") == LicenseRisk.ALLOWED
        assert categorise_license("gpl3") == LicenseRisk.COPYLEFT


class TestScanLicenses:
    def test_filters_out_allowed(self) -> None:
        packages = [("requests", "MIT"), ("flask", "BSD-3-Clause")]
        findings = scan_licenses(packages)
        assert findings == []

    def test_returns_copyleft(self) -> None:
        packages = [("libgpl", "GPL-3.0"), ("libmit", "MIT")]
        findings = scan_licenses(packages)
        assert len(findings) == 1
        assert findings[0].package == "libgpl"
        assert findings[0].risk == LicenseRisk.COPYLEFT

    def test_returns_unknown(self) -> None:
        packages = [("custom-pkg", "CUSTOM-v1")]
        findings = scan_licenses(packages)
        assert findings[0].risk == LicenseRisk.UNKNOWN

    def test_empty_packages(self) -> None:
        assert scan_licenses([]) == []

    def test_restricted_license(self) -> None:
        packages = [("mongo-driver", "SSPL-1.0")]
        findings = scan_licenses(packages)
        assert findings[0].risk == LicenseRisk.RESTRICTED
