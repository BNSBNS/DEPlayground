"""DataSecurity CLI — scan databases for PII, encryption issues, and compliance gaps."""

from __future__ import annotations

from typing import Annotated

import typer

app = typer.Typer(name="datasec", help="Database & Data Security Toolkit.")


@app.command()
def scan(
    db_url: Annotated[str, typer.Argument(help="SQLAlchemy database URL.")],
    frameworks: Annotated[
        str,
        typer.Option("--frameworks", "-f", help="Comma-separated: PDPA,GDPR,PCI-DSS"),
    ] = "PDPA,GDPR,PCI-DSS",
    output_format: Annotated[
        str, typer.Option("--format", help="Output format: json or html")
    ] = "json",
    output_file: Annotated[str, typer.Option("--output", "-o", help="Write report to file.")] = "",
) -> None:
    """Scan a database and generate a compliance report."""
    from src.audit.tde_checker import check_tde
    from src.compliance.report_generator import generate_report, render_html, render_json
    from src.db.adapter import AbstractDBAdapter
    from src.discovery.schema_scanner import scan_schema

    def _get_adapter(url: str) -> AbstractDBAdapter:
        if url.startswith("sqlite"):
            from src.db.sqlite_adapter import SQLiteAdapter

            return SQLiteAdapter(url)
        if url.startswith("postgresql"):
            from src.db.postgres_adapter import PostgreSQLAdapter

            return PostgreSQLAdapter(url)
        if url.startswith("mysql"):
            from src.db.mysql_adapter import MySQLAdapter

            return MySQLAdapter(url)
        raise typer.BadParameter(f"Unsupported database URL scheme: {url}")

    fw_list = [fw.strip() for fw in frameworks.split(",") if fw.strip()]
    adapter = _get_adapter(db_url)

    typer.echo(f"Scanning database: {adapter.database_name()}")
    tables = scan_schema(adapter)
    encryption = check_tde(adapter)
    report = generate_report(tables, encryption, frameworks=fw_list)

    typer.echo(
        f"Scanned {len(tables)} tables, found {report.pii_columns_found} PII columns. "
        f"Risk score: {report.risk_score:.0%}"
    )
    typer.echo(f"PASS: {report.pass_count}  FAIL: {report.fail_count}")

    if output_format == "html":
        content = render_html(report)
    else:
        content = render_json(report)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        typer.echo(f"Report written to {output_file}")
    else:
        typer.echo(content)


@app.command()
def pii_scan(
    db_url: Annotated[str, typer.Argument(help="SQLAlchemy database URL.")],
) -> None:
    """Scan schema for PII columns only."""
    from src.db.sqlite_adapter import SQLiteAdapter
    from src.discovery.schema_scanner import scan_schema

    adapter = SQLiteAdapter(db_url) if db_url.startswith("sqlite") else None
    if adapter is None:
        typer.echo("Only SQLite supported in pii-scan command. Use 'scan' for PostgreSQL/MySQL.")
        raise typer.Exit(1)

    tables = scan_schema(adapter)
    pii_tables = [t for t in tables if t.has_pii]

    for table in pii_tables:
        for col in table.pii_columns:
            typer.echo(
                f"{table.table_name}.{col.column_name}  "
                f"[{col.classification}]  "
                f"types={[str(p) for p in col.pii_types]}"
            )

    if not pii_tables:
        typer.echo("No PII columns detected.")
