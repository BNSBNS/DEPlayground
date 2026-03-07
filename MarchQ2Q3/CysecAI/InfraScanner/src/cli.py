"""InfraScanner CLI — scan a project directory for vulnerabilities."""

from __future__ import annotations

import asyncio
import json
import pathlib
from typing import Annotated

import typer

app = typer.Typer(name="infrascan", help="Supply chain & dependency security scanner.")


def _run(coro: object) -> object:
    """Run an async coroutine from sync context."""
    import asyncio as _asyncio

    return _asyncio.run(coro)  # type: ignore[arg-type]


@app.command()
def scan(
    path: Annotated[
        pathlib.Path, typer.Argument(help="Project directory or manifest file to scan")
    ],
    output_format: Annotated[
        str, typer.Option("--format", "-f", help="Output format: json|sarif|html")
    ] = "json",
    output: Annotated[
        pathlib.Path | None, typer.Option("--output", "-o", help="Write report to file")
    ] = None,
    typosquat_distance: Annotated[
        int, typer.Option("--typosquat-distance", help="Max Levenshtein distance for typosquatting")
    ] = 2,
) -> None:
    """Scan a project for dependency vulnerabilities, Docker misconfigs, and typosquatting."""
    if not path.exists():
        typer.echo(f"Error: path does not exist: {path}", err=True)
        raise typer.Exit(1)

    from src.reporting.ci_output import to_json, to_sarif
    from src.reporting.html_report import generate_html_report
    from src.scanners.dependency_scanner import scan_project

    typer.echo(f"Scanning {path} ...")
    result = asyncio.run(scan_project(path, typosquat_max_distance=typosquat_distance))

    typer.echo(
        f"Found {result.total_vulns} vulnerabilities "
        f"({result.critical_count} critical, {result.high_count} high) "
        f"across {len(result.dependencies)} dependencies."
    )

    if output_format == "sarif":
        content = json.dumps(to_sarif(result), indent=2)
    elif output_format == "html":
        content = generate_html_report(result)
    else:
        content = to_json(result)

    if output:
        output.write_text(content, encoding="utf-8")
        typer.echo(f"Report written to {output}")
    else:
        typer.echo(content)

    # Non-zero exit code if critical vulns found (useful for CI gates)
    if result.critical_count > 0:
        raise typer.Exit(2)


@app.command()
def self_scan() -> None:
    """Scan InfraScanner's own pyproject.toml (dogfooding)."""
    own_pyproject = pathlib.Path(__file__).parent.parent / "pyproject.toml"
    typer.echo(f"Self-scan: scanning {own_pyproject}")
    scan(path=own_pyproject, output_format="json")


if __name__ == "__main__":
    app()
