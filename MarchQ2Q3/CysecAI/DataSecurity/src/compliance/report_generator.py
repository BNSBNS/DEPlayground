"""Compliance report generator — aggregates PDPA, GDPR, and PCI-DSS findings."""

from __future__ import annotations

import json

from jinja2 import Template

from src.compliance.gdpr_mapper import map_gdpr
from src.compliance.pci_mapper import map_pci
from src.compliance.pdpa_mapper import map_pdpa
from src.models import ComplianceReport, ComplianceStatus, EncryptionStatus, TableInfo

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Compliance Report — {{ report.database_name }}</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 40px; color: #333; }
    h1 { color: #b71c1c; }
    .summary { display: flex; gap: 20px; margin: 20px 0; }
    .card { background: #f5f5f5; border-radius: 8px; padding: 16px 24px; min-width: 100px; }
    .card .value { font-size: 2em; font-weight: bold; }
    .card .label { font-size: 0.9em; color: #666; }
    .PASS { color: #2e7d32; font-weight: bold; }
    .FAIL { color: #b71c1c; font-weight: bold; }
    .NA { color: #757575; font-weight: bold; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; }
    th { background: #b71c1c; color: white; padding: 10px; text-align: left; }
    td { padding: 8px 10px; border-bottom: 1px solid #e0e0e0; }
    tr:hover { background: #fafafa; }
    .findings { font-size: 0.85em; color: #555; }
    .remediation { font-size: 0.85em; color: #1565c0; }
  </style>
</head>
<body>
  <h1>Database Compliance Report</h1>
  <p><strong>Database:</strong> {{ report.database_name }}</p>
  <p><strong>Scan Time:</strong> {{ report.timestamp.strftime('%Y-%m-%d %H:%M UTC') }}</p>
  <p><strong>Risk Score:</strong> {{ "%.0f" | format(report.risk_score * 100) }}%</p>

  <div class="summary">
    <div class="card"><div class="value">{{ report.tables_scanned | length }}</div>
      <div class="label">Tables Scanned</div></div>
    <div class="card"><div class="value">{{ report.pii_columns_found }}</div>
      <div class="label">PII Columns</div></div>
    <div class="card"><div class="value {{ 'PASS' if report.tde_enabled else 'FAIL' }}">
      {{ 'ON' if report.tde_enabled else 'OFF' }}</div>
      <div class="label">TDE</div></div>
    <div class="card"><div class="value {{ 'PASS' if report.tls_enabled else 'FAIL' }}">
      {{ 'ON' if report.tls_enabled else 'OFF' }}</div>
      <div class="label">TLS</div></div>
    <div class="card"><div class="value PASS">{{ report.pass_count }}</div>
      <div class="label">PASS</div></div>
    <div class="card"><div class="value FAIL">{{ report.fail_count }}</div>
      <div class="label">FAIL</div></div>
  </div>

  <table>
    <tr><th>ID</th><th>Framework</th><th>Article</th><th>Description</th>
        <th>Status</th><th>Findings & Remediation</th></tr>
    {% for r in report.requirements %}
    <tr>
      <td>{{ r.requirement_id }}</td>
      <td>{{ r.framework }}</td>
      <td>{{ r.article }}</td>
      <td>{{ r.description }}</td>
      <td class="{{ r.status }}">{{ r.status }}</td>
      <td>
        {% if r.findings %}
          <div class="findings">{{ r.findings | join('<br>') }}</div>
        {% endif %}
        {% if r.remediation %}
          <div class="remediation">Fix: {{ r.remediation }}</div>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </table>
</body>
</html>"""


def generate_report(
    tables: list[TableInfo],
    encryption: EncryptionStatus,
    frameworks: list[str] | None = None,
) -> ComplianceReport:
    """Generate a ComplianceReport from scan results.

    Args:
        tables: TableInfo list from schema scan.
        encryption: EncryptionStatus from TDE/TLS checks.
        frameworks: Which frameworks to include ("PDPA", "GDPR", "PCI-DSS").
                    Defaults to all three.
    """
    if frameworks is None:
        frameworks = ["PDPA", "GDPR", "PCI-DSS"]

    requirements = []
    if "PDPA" in frameworks:
        requirements.extend(map_pdpa(tables, encryption))
    if "GDPR" in frameworks:
        requirements.extend(map_gdpr(tables, encryption))
    if "PCI-DSS" in frameworks:
        requirements.extend(map_pci(tables, encryption))

    pii_count = sum(len(t.pii_columns) for t in tables)

    return ComplianceReport(
        database_name=encryption.database_name,
        tables_scanned=[t.table_name for t in tables],
        pii_columns_found=pii_count,
        tde_enabled=encryption.tde_enabled,
        tls_enabled=encryption.tls_enabled,
        requirements=requirements,
    )


def render_html(report: ComplianceReport) -> str:
    """Render the compliance report as an HTML string."""
    template = Template(_HTML_TEMPLATE)
    return template.render(report=report, ComplianceStatus=ComplianceStatus)


def render_json(report: ComplianceReport) -> str:
    """Render the compliance report as a JSON string."""
    return json.dumps(report.to_dict(), indent=2)
