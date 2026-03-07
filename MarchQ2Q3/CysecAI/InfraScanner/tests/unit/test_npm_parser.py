"""Tests for npm dependency parser."""

from __future__ import annotations

import json

from src.models import Ecosystem
from src.parsers.npm_parser import parse_package_json


class TestParsePackageJson:
    def test_exact_version(self) -> None:
        data = {"dependencies": {"lodash": "4.17.11"}}
        deps = parse_package_json(json.dumps(data))
        assert len(deps) == 1
        assert deps[0].name == "lodash"
        assert deps[0].version == "4.17.11"

    def test_caret_range(self) -> None:
        data = {"dependencies": {"express": "^4.17.1"}}
        deps = parse_package_json(json.dumps(data))
        assert deps[0].version is None
        assert deps[0].constraint == "^4.17.1"

    def test_tilde_range(self) -> None:
        data = {"dependencies": {"axios": "~0.18.0"}}
        deps = parse_package_json(json.dumps(data))
        assert deps[0].constraint == "~0.18.0"

    def test_dev_deps_excluded_by_default(self) -> None:
        data = {
            "dependencies": {"express": "4.17.1"},
            "devDependencies": {"jest": "27.0.0"},
        }
        deps = parse_package_json(json.dumps(data))
        names = {d.name for d in deps}
        assert "jest" not in names

    def test_dev_deps_included_when_flag_set(self) -> None:
        data = {
            "dependencies": {"express": "4.17.1"},
            "devDependencies": {"jest": "27.0.0"},
        }
        deps = parse_package_json(json.dumps(data), include_dev=True)
        names = {d.name for d in deps}
        assert "jest" in names

    def test_ecosystem_npm(self) -> None:
        data = {"dependencies": {"lodash": "4.17.11"}}
        deps = parse_package_json(json.dumps(data))
        assert deps[0].ecosystem == Ecosystem.NPM

    def test_empty_dependencies(self) -> None:
        data = {"name": "myapp", "version": "1.0.0"}
        assert parse_package_json(json.dumps(data)) == []

    def test_invalid_json(self) -> None:
        assert parse_package_json("not json {{") == []

    def test_latest_tag_no_version(self) -> None:
        data = {"dependencies": {"pkg": "latest"}}
        deps = parse_package_json(json.dumps(data))
        assert deps[0].version is None
        assert deps[0].constraint is None

    def test_multiple_deps(self) -> None:
        data = {
            "dependencies": {
                "react": "18.2.0",
                "react-dom": "18.2.0",
                "axios": "^1.4.0",
            }
        }
        deps = parse_package_json(json.dumps(data))
        assert len(deps) == 3
