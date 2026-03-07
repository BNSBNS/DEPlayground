"""Tests for pip dependency parser."""

from __future__ import annotations

from src.models import Ecosystem
from src.parsers.pip_parser import parse_pyproject, parse_requirements


class TestParseRequirements:
    def test_pinned_version(self) -> None:
        deps = parse_requirements("requests==2.28.0")
        assert len(deps) == 1
        assert deps[0].name == "requests"
        assert deps[0].version == "2.28.0"

    def test_constraint_only(self) -> None:
        deps = parse_requirements("flask>=2.0")
        assert len(deps) == 1
        assert deps[0].name == "flask"
        assert deps[0].version is None
        assert deps[0].constraint is not None

    def test_no_version(self) -> None:
        deps = parse_requirements("numpy")
        assert deps[0].name == "numpy"
        assert deps[0].version is None

    def test_comments_skipped(self) -> None:
        content = "# This is a comment\nrequests==2.28.0\n"
        deps = parse_requirements(content)
        assert len(deps) == 1

    def test_blank_lines_skipped(self) -> None:
        content = "\n\nflask==2.0\n\n"
        deps = parse_requirements(content)
        assert len(deps) == 1

    def test_options_skipped(self) -> None:
        content = "-r base.txt\n--index-url https://pypi.org\nrequests==2.28.0"
        deps = parse_requirements(content)
        assert len(deps) == 1

    def test_vcs_dep_skipped(self) -> None:
        content = "git+https://github.com/example/pkg.git\nrequests==2.28.0"
        deps = parse_requirements(content)
        assert all(d.name == "requests" for d in deps)

    def test_extras_stripped(self) -> None:
        deps = parse_requirements("uvicorn[standard]==0.30.0")
        assert deps[0].name == "uvicorn"
        assert deps[0].version == "0.30.0"

    def test_inline_comment_stripped(self) -> None:
        deps = parse_requirements("requests==2.28.0  # security fix")
        assert deps[0].version == "2.28.0"

    def test_ecosystem_pypi(self) -> None:
        deps = parse_requirements("flask==2.0")
        assert deps[0].ecosystem == Ecosystem.PYPI

    def test_multiple_deps(self) -> None:
        content = "requests==2.28.0\nflask>=2.0\nnumpy"
        deps = parse_requirements(content)
        assert len(deps) == 3

    def test_empty_string(self) -> None:
        assert parse_requirements("") == []

    def test_source_file_preserved(self) -> None:
        deps = parse_requirements("requests==2.28.0", source_file="my_reqs.txt")
        assert deps[0].source_file == "my_reqs.txt"

    def test_name_normalised(self) -> None:
        deps = parse_requirements("Pillow==9.0.0")
        assert deps[0].name == "pillow"

    def test_version_with_postrelease(self) -> None:
        deps = parse_requirements("numpy==1.24.0.post1")
        assert deps[0].name == "numpy"


class TestParsePyproject:
    def test_project_dependencies(self) -> None:
        content = '[project]\ndependencies = ["requests>=2.28.0", "flask==2.0"]'
        deps = parse_pyproject(content)
        names = {d.name for d in deps}
        assert "requests" in names
        assert "flask" in names

    def test_empty_dependencies(self) -> None:
        content = "[project]\nname = 'myapp'"
        deps = parse_pyproject(content)
        assert deps == []

    def test_invalid_toml(self) -> None:
        assert parse_pyproject("not valid {{{{ toml") == []

    def test_ecosystem_pypi(self) -> None:
        content = '[project]\ndependencies = ["pydantic>=2.0"]'
        deps = parse_pyproject(content)
        assert all(d.ecosystem == Ecosystem.PYPI for d in deps)

    def test_source_file_preserved(self) -> None:
        content = '[project]\ndependencies = ["flask==2.0"]'
        deps = parse_pyproject(content, source_file="pyproject.toml")
        assert deps[0].source_file == "pyproject.toml"
