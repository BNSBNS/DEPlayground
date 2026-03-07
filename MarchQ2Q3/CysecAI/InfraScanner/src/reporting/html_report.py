"""HTML report generator using Jinja2."""

from __future__ import annotations

from jinja2 import Environment, Template

from src.models import ScanResult

_TEMPLATE_SRC = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>InfraScanner Report — {{ result.target_path }}</title>
<style>
  body { font-family: sans-serif; margin: 2rem; background: #f5f5f5; }
  h1 { color: #1a1a2e; }
  .metric { display: inline-block; padding: .5rem 1.5rem; margin: .5rem;
            border-radius: 4px; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.2); }
  .critical { border-left: 4px solid #c0392b; }
  .high     { border-left: 4px solid #e67e22; }
  .medium   { border-left: 4px solid #f1c40f; }
  table { width: 100%; border-collapse: collapse; background: #fff;
          margin-top: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,.2); }
  th { background: #2c3e50; color: #fff; padding: .5rem 1rem; text-align: left; }
  td { padding: .4rem 1rem; border-bottom: 1px solid #eee; font-size: .9rem; }
  .sev-CRITICAL { color: #c0392b; font-weight: bold; }
  .sev-HIGH     { color: #e67e22; font-weight: bold; }
  .sev-MEDIUM   { color: #d4ac0d; }
  .sev-LOW      { color: #27ae60; }
  .sev-UNKNOWN  { color: #888; }
</style>
</head>
<body>
<h1>InfraScanner Report</h1>
<p><strong>Target:</strong> {{ result.target_path }}</p>
<p><strong>Scanned:</strong> {{ result.timestamp.strftime('%Y-%m-%d %H:%M UTC') }}</p>

<div>
  <div class="metric"><strong>{{ result.dependencies|length }}</strong><br>Dependencies</div>
  <div class="metric critical"><strong>{{ result.critical_count }}</strong><br>Critical</div>
  <div class="metric high"><strong>{{ result.high_count }}</strong><br>High</div>
  <div class="metric"><strong>{{ result.total_vulns }}</strong><br>Total Vulns</div>
  <div class="metric"><strong>{{ result.docker_findings|length }}</strong><br>Docker Issues</div>
  <div class="metric"><strong>{{ result.typosquat_findings|length }}</strong><br>Typosquats</div>
</div>

{% if result.findings %}
<h2>Vulnerability Findings</h2>
<table>
  <tr><th>Package</th><th>Version</th><th>Ecosystem</th>
      <th>CVE</th><th>Severity</th><th>CVSS</th><th>Risk Score</th></tr>
  {% for f in result.findings %}
    {% for v in f.vulnerabilities %}
    <tr>
      <td>{{ f.dependency.name }}</td>
      <td>{{ f.dependency.version or '?' }}</td>
      <td>{{ f.dependency.ecosystem }}</td>
      <td>{{ v.vuln_id }}</td>
      <td class="sev-{{ v.severity }}">{{ v.severity }}</td>
      <td>{{ v.cvss_score or '—' }}</td>
      <td>{{ '%.4f'|format(f.risk_score) }}</td>
    </tr>
    {% endfor %}
  {% endfor %}
</table>
{% endif %}

{% if result.docker_findings %}
<h2>Docker Security Findings</h2>
<table>
  <tr><th>Check</th><th>Severity</th><th>Line</th><th>Description</th><th>Recommendation</th></tr>
  {% for d in result.docker_findings %}
  <tr>
    <td>{{ d.check_id }}</td>
    <td class="sev-{{ d.severity }}">{{ d.severity }}</td>
    <td>{{ d.line_number or '—' }}</td>
    <td>{{ d.description }}</td>
    <td>{{ d.recommendation }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}

{% if result.typosquat_findings %}
<h2>Potential Typosquatting</h2>
<table>
  <tr><th>Package</th><th>Similar To</th><th>Distance</th><th>Ecosystem</th></tr>
  {% for t in result.typosquat_findings %}
  <tr>
    <td>{{ t.package }}</td>
    <td>{{ t.similar_to }}</td>
    <td>{{ t.distance }}</td>
    <td>{{ t.ecosystem }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}

{% if result.license_findings %}
<h2>License Risk</h2>
<table>
  <tr><th>Package</th><th>License</th><th>Risk</th></tr>
  {% for lf in result.license_findings %}
  <tr>
    <td>{{ lf.package }}</td>
    <td>{{ lf.license_id }}</td>
    <td>{{ lf.risk }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}

</body>
</html>
"""


def generate_html_report(result: ScanResult) -> str:
    """Render a ScanResult as an HTML report string."""
    env = Environment(autoescape=True)
    template: Template = env.from_string(_TEMPLATE_SRC)
    return template.render(result=result)
