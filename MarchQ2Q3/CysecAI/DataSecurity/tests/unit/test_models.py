"""Tests for DataSecurity models."""

from __future__ import annotations

from src.models import (
    AuditEvent,
    ColumnInfo,
    ComplianceReport,
    ComplianceRequirement,
    ComplianceStatus,
    DataClassification,
    EncryptionStatus,
    MaskingStrategy,
    PIIType,
    TableInfo,
)


class TestColumnInfo:
    def test_default_classification(self) -> None:
        col = ColumnInfo(table_name="t", column_name="col", data_type="VARCHAR")
        assert col.classification == DataClassification.PUBLIC

    def test_pii_column(self) -> None:
        col = ColumnInfo(
            table_name="users",
            column_name="email",
            data_type="VARCHAR",
            classification=DataClassification.PII,
            pii_types=[PIIType.EMAIL],
            masking_strategy=MaskingStrategy.EMAIL,
        )
        assert col.classification == DataClassification.PII
        assert PIIType.EMAIL in col.pii_types


class TestTableInfo:
    def test_has_pii_false_when_public(self) -> None:
        table = TableInfo(
            table_name="logs",
            columns=[ColumnInfo(table_name="logs", column_name="id", data_type="INTEGER")],
        )
        assert not table.has_pii

    def test_has_pii_true(self) -> None:
        table = TableInfo(
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
        assert table.has_pii
        assert len(table.pii_columns) == 1

    def test_pii_columns_filter(self) -> None:
        table = TableInfo(
            table_name="users",
            columns=[
                ColumnInfo(table_name="users", column_name="id", data_type="INTEGER"),
                ColumnInfo(
                    table_name="users",
                    column_name="email",
                    data_type="VARCHAR",
                    classification=DataClassification.PII,
                    pii_types=[PIIType.EMAIL],
                ),
            ],
        )
        assert len(table.pii_columns) == 1
        assert table.pii_columns[0].column_name == "email"


class TestEncryptionStatus:
    def test_defaults_off(self) -> None:
        status = EncryptionStatus(database_name="mydb")
        assert not status.tde_enabled
        assert not status.tls_enabled

    def test_tls_on(self) -> None:
        status = EncryptionStatus(database_name="mydb", tls_enabled=True, tls_version="TLSv1.3")
        assert status.tls_enabled
        assert "1.3" in status.tls_version


class TestAuditEvent:
    def test_default_not_suspicious(self) -> None:
        event = AuditEvent(db_user="admin", query_text="SELECT id FROM orders LIMIT 10")
        assert not event.is_suspicious
        assert event.suspicious_reasons == []

    def test_timestamp_utc(self) -> None:
        event = AuditEvent(db_user="u", query_text="SELECT 1")
        assert event.timestamp.tzinfo is not None


class TestComplianceReport:
    def test_pass_fail_counts(self) -> None:
        report = ComplianceReport(
            database_name="test",
            requirements=[
                ComplianceRequirement(
                    requirement_id="R1",
                    framework="PDPA",
                    article="Art 1",
                    description="desc",
                    status=ComplianceStatus.PASS,
                ),
                ComplianceRequirement(
                    requirement_id="R2",
                    framework="PDPA",
                    article="Art 2",
                    description="desc",
                    status=ComplianceStatus.FAIL,
                ),
                ComplianceRequirement(
                    requirement_id="R3",
                    framework="PDPA",
                    article="Art 3",
                    description="desc",
                    status=ComplianceStatus.NA,
                ),
            ],
        )
        assert report.pass_count == 1
        assert report.fail_count == 1

    def test_risk_score_all_pass(self) -> None:
        report = ComplianceReport(
            database_name="test",
            requirements=[
                ComplianceRequirement(
                    requirement_id="R1",
                    framework="PDPA",
                    article="Art 1",
                    description="d",
                    status=ComplianceStatus.PASS,
                )
            ],
        )
        assert report.risk_score == 0.0

    def test_risk_score_all_fail(self) -> None:
        report = ComplianceReport(
            database_name="test",
            requirements=[
                ComplianceRequirement(
                    requirement_id="R1",
                    framework="PDPA",
                    article="Art 1",
                    description="d",
                    status=ComplianceStatus.FAIL,
                )
            ],
        )
        assert report.risk_score == 1.0

    def test_risk_score_na_excluded(self) -> None:
        report = ComplianceReport(
            database_name="test",
            requirements=[
                ComplianceRequirement(
                    requirement_id="R1",
                    framework="PDPA",
                    article="Art 1",
                    description="d",
                    status=ComplianceStatus.NA,
                )
            ],
        )
        assert report.risk_score == 0.0

    def test_to_dict_structure(self) -> None:
        report = ComplianceReport(database_name="mydb", requirements=[])
        d = report.to_dict()
        assert "report_id" in d
        assert "summary" in d
        assert d["database_name"] == "mydb"
