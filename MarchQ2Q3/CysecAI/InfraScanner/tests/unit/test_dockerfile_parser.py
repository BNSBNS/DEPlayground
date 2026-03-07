"""Tests for Dockerfile parser."""

from __future__ import annotations

from src.models import Ecosystem
from src.parsers.dockerfile_parser import parse_dockerfile


class TestParseDockerfile:
    def test_from_with_tag(self) -> None:
        deps = parse_dockerfile("FROM ubuntu:22.04")
        assert len(deps) == 1
        assert deps[0].name == "ubuntu"
        assert deps[0].version == "22.04"
        assert deps[0].ecosystem == Ecosystem.DOCKER

    def test_from_latest(self) -> None:
        deps = parse_dockerfile("FROM nginx:latest")
        assert deps[0].version == "latest"

    def test_from_no_tag(self) -> None:
        deps = parse_dockerfile("FROM python")
        assert deps[0].name == "python"
        assert deps[0].version is None

    def test_from_with_as(self) -> None:
        deps = parse_dockerfile("FROM node:18 AS builder")
        assert deps[0].name == "node"
        assert deps[0].version == "18"

    def test_multistage_both_froms(self) -> None:
        content = "FROM python:3.11 AS build\nFROM nginx:latest"
        deps = parse_dockerfile(content)
        names = [d.name for d in deps if d.ecosystem == Ecosystem.DOCKER]
        assert "python" in names
        assert "nginx" in names

    def test_pip_install_parsed(self) -> None:
        content = "FROM python:3.11\nRUN pip install requests flask"
        deps = parse_dockerfile(content)
        pypi_names = [d.name for d in deps if d.ecosystem == Ecosystem.PYPI]
        assert "requests" in pypi_names
        assert "flask" in pypi_names

    def test_npm_install_parsed(self) -> None:
        content = "FROM node:18\nRUN npm install express"
        deps = parse_dockerfile(content)
        npm_names = [d.name for d in deps if d.ecosystem == Ecosystem.NPM]
        assert "express" in npm_names

    def test_comments_skipped(self) -> None:
        content = "# comment\nFROM ubuntu:22.04"
        deps = parse_dockerfile(content)
        assert len(deps) == 1

    def test_arg_substitution_skipped(self) -> None:
        deps = parse_dockerfile("FROM $BASE_IMAGE")
        # ARG-based FROM is skipped
        docker_deps = [d for d in deps if d.ecosystem == Ecosystem.DOCKER]
        assert len(docker_deps) == 0

    def test_empty_dockerfile(self) -> None:
        assert parse_dockerfile("") == []
