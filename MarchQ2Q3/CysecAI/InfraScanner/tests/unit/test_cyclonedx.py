"""Tests for CycloneDX SBOM generator."""

from __future__ import annotations

from src.models import Dependency, Ecosystem
from src.sbom.cyclonedx_generator import (
    deps_to_components,
    generate_sbom,
    generate_sbom_from_deps,
)


class TestDepsToComponents:
    def test_purl_pypi(self) -> None:
        dep = Dependency(name="requests", version="2.28.0", ecosystem=Ecosystem.PYPI)
        components = deps_to_components([dep])
        assert components[0].purl == "pkg:pypi/requests@2.28.0"

    def test_purl_npm(self) -> None:
        dep = Dependency(name="lodash", version="4.17.11", ecosystem=Ecosystem.NPM)
        components = deps_to_components([dep])
        assert components[0].purl == "pkg:npm/lodash@4.17.11"

    def test_purl_go(self) -> None:
        dep = Dependency(name="github.com/gin-gonic/gin", version="1.9.0", ecosystem=Ecosystem.GO)
        components = deps_to_components([dep])
        assert "golang" in components[0].purl

    def test_no_version_no_at(self) -> None:
        dep = Dependency(name="flask", ecosystem=Ecosystem.PYPI)
        components = deps_to_components([dep])
        assert "@" not in components[0].purl

    def test_unique_bom_refs(self) -> None:
        deps = [
            Dependency(name="a", version="1.0", ecosystem=Ecosystem.PYPI),
            Dependency(name="b", version="2.0", ecosystem=Ecosystem.PYPI),
        ]
        components = deps_to_components(deps)
        refs = [c.bom_ref for c in components]
        assert len(set(refs)) == 2


class TestGenerateSBOM:
    def test_bom_format(self) -> None:
        sbom = generate_sbom([])
        assert sbom["bomFormat"] == "CycloneDX"
        assert sbom["specVersion"] == "1.4"

    def test_serial_number_urn(self) -> None:
        sbom = generate_sbom([])
        assert sbom["serialNumber"].startswith("urn:uuid:")

    def test_metadata_timestamp(self) -> None:
        sbom = generate_sbom([])
        assert "timestamp" in sbom["metadata"]

    def test_components_count(self) -> None:
        deps = [
            Dependency(name="requests", version="2.28.0", ecosystem=Ecosystem.PYPI),
            Dependency(name="flask", version="2.0", ecosystem=Ecosystem.PYPI),
        ]
        sbom = generate_sbom_from_deps(deps)
        assert len(sbom["components"]) == 2

    def test_component_fields(self) -> None:
        deps = [Dependency(name="requests", version="2.28.0", ecosystem=Ecosystem.PYPI)]
        sbom = generate_sbom_from_deps(deps)
        comp = sbom["components"][0]
        assert comp["name"] == "requests"
        assert comp["version"] == "2.28.0"
        assert comp["purl"] == "pkg:pypi/requests@2.28.0"

    def test_metadata_custom(self) -> None:
        sbom = generate_sbom([], metadata={"name": "myapp", "version": "1.0"})
        assert sbom["metadata"]["component"]["name"] == "myapp"
