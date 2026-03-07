"""Tests for compliance mappers and report generator."""

from __future__ import annotations

from src.compliance.gdpr_mapper import map_gdpr
from src.compliance.pci_mapper import map_pci
from src.compliance.pdpa_mapper import map_pdpa
from src.compliance.report_generator import generate_report, render_html, render_json
from src.models import (
    ColumnInfo,
    ComplianceStatus,
    DataClassification,
    EncryptionStatus,
    PIIType,
    TableInfo,
)


def _pii_tables() -> list[TableInfo]:
    """Sample tables with PII columns."""
    return [
        TableInfo(
            table_name="users",
            columns=[
                ColumnInfo(
                    table_name="users",
                    column_name="email",
                    data_type="VARCHAR",
                    classification=DataClassification.PII,
                    pii_types=[PIIType.EMAIL],
                )
            ],
        )
    ]


def _pci_tables() -> list[TableInfo]:
    return [
        TableInfo(
            table_name="payments",
            columns=[
                ColumnInfo(
                    table_name="payments",
                    column_name="credit_card",
                    data_type="VARCHAR",
                    classification=DataClassification.PCI,
                    pii_types=[PIIType.CREDIT_CARD],
                )
            ],
        )
    ]


class TestPDPAMapper:
    def test_care_obligation_fails_when_no_tls(self) -> None:
        enc = EncryptionStatus(database_name="db", tde_enabled=False, tls_enabled=False)
        reqs = map_pdpa(_pii_tables(), enc)
        pdpa4 = next(r for r in reqs if r.requirement_id == "PDPA-4")
        assert pdpa4.status == ComplianceStatus.FAIL

    def test_care_obligation_passes_with_tls_and_tde(self) -> None:
        enc = EncryptionStatus(database_name="db", tde_enabled=True, tls_enabled=True)
        reqs = map_pdpa([], enc)
        pdpa4 = next(r for r in reqs if r.requirement_id == "PDPA-4")
        assert pdpa4.status == ComplianceStatus.PASS

    def test_masking_fails_when_pii_columns_present(self) -> None:
        enc = EncryptionStatus(database_name="db", tls_enabled=False)
        reqs = map_pdpa(_pii_tables(), enc)
        pdpa5 = next(r for r in reqs if r.requirement_id == "PDPA-5")
        assert pdpa5.status == ComplianceStatus.FAIL

    def test_masking_passes_when_no_pii(self) -> None:
        enc = EncryptionStatus(database_name="db", tls_enabled=True, tde_enabled=True)
        reqs = map_pdpa([], enc)
        pdpa5 = next(r for r in reqs if r.requirement_id == "PDPA-5")
        assert pdpa5.status == ComplianceStatus.PASS

    def test_policy_requirements_are_na(self) -> None:
        enc = EncryptionStatus(database_name="db")
        reqs = map_pdpa([], enc)
        na_reqs = [r for r in reqs if r.status == ComplianceStatus.NA]
        assert len(na_reqs) >= 3


class TestGDPRMapper:
    def test_article_32_fails_without_encryption(self) -> None:
        enc = EncryptionStatus(database_name="db", tde_enabled=False, tls_enabled=False)
        reqs = map_gdpr(_pii_tables(), enc)
        gdpr3 = next(r for r in reqs if r.requirement_id == "GDPR-3")
        assert gdpr3.status == ComplianceStatus.FAIL

    def test_article_32_passes_with_full_encryption(self) -> None:
        enc = EncryptionStatus(database_name="db", tde_enabled=True, tls_enabled=True)
        reqs = map_gdpr([], enc)
        gdpr3 = next(r for r in reqs if r.requirement_id == "GDPR-3")
        assert gdpr3.status == ComplianceStatus.PASS

    def test_article_25_fails_with_pii(self) -> None:
        enc = EncryptionStatus(database_name="db")
        reqs = map_gdpr(_pii_tables(), enc)
        gdpr2 = next(r for r in reqs if r.requirement_id == "GDPR-2")
        assert gdpr2.status == ComplianceStatus.FAIL

    def test_all_frameworks_returned(self) -> None:
        enc = EncryptionStatus(database_name="db")
        reqs = map_gdpr([], enc)
        ids = {r.requirement_id for r in reqs}
        assert "GDPR-1" in ids
        assert "GDPR-3" in ids


class TestPCIMapper:
    def test_req_34_fails_without_tde(self) -> None:
        enc = EncryptionStatus(database_name="db", tde_enabled=False)
        reqs = map_pci(_pci_tables(), enc)
        pci34 = next(r for r in reqs if r.requirement_id == "PCI-3.4")
        assert pci34.status == ComplianceStatus.FAIL

    def test_req_41_fails_without_tls(self) -> None:
        enc = EncryptionStatus(database_name="db", tls_enabled=False)
        reqs = map_pci([], enc)
        pci41 = next(r for r in reqs if r.requirement_id == "PCI-4.1")
        assert pci41.status == ComplianceStatus.FAIL

    def test_req_41_passes_with_tls(self) -> None:
        enc = EncryptionStatus(database_name="db", tls_enabled=True, tls_version="TLSv1.3")
        reqs = map_pci([], enc)
        pci41 = next(r for r in reqs if r.requirement_id == "PCI-4.1")
        assert pci41.status == ComplianceStatus.PASS

    def test_no_pci_tables_no_findings(self) -> None:
        enc = EncryptionStatus(database_name="db", tde_enabled=True)
        reqs = map_pci([], enc)
        pci34 = next(r for r in reqs if r.requirement_id == "PCI-3.4")
        assert pci34.status == ComplianceStatus.PASS


class TestReportGenerator:
    def test_generate_report_all_frameworks(self) -> None:
        enc = EncryptionStatus(database_name="testdb", tls_enabled=False)
        report = generate_report(_pii_tables(), enc)
        frameworks = {r.framework for r in report.requirements}
        assert "PDPA" in frameworks
        assert "GDPR" in frameworks
        assert "PCI-DSS" in frameworks

    def test_generate_report_single_framework(self) -> None:
        enc = EncryptionStatus(database_name="testdb")
        report = generate_report([], enc, frameworks=["PDPA"])
        assert all(r.framework == "PDPA" for r in report.requirements)

    def test_risk_score_computed(self) -> None:
        enc = EncryptionStatus(database_name="testdb", tls_enabled=False)
        report = generate_report(_pii_tables(), enc)
        assert report.risk_score > 0.0

    def test_pii_count_correct(self) -> None:
        enc = EncryptionStatus(database_name="testdb")
        report = generate_report(_pii_tables(), enc)
        assert report.pii_columns_found == 1

    def test_render_json(self) -> None:
        enc = EncryptionStatus(database_name="testdb")
        report = generate_report([], enc)
        json_str = render_json(report)
        assert '"database_name"' in json_str
        assert "testdb" in json_str

    def test_render_html(self) -> None:
        enc = EncryptionStatus(database_name="testdb")
        report = generate_report([], enc)
        html = render_html(report)
        assert "<html" in html
        assert "testdb" in html

    def test_empty_frameworks(self) -> None:
        enc = EncryptionStatus(database_name="testdb")
        report = generate_report([], enc, frameworks=[])
        assert report.requirements == []
