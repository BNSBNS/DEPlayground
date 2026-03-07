.PHONY: setup lint format type-check test test-cov

setup:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/

format:
	ruff format --check src/ tests/

type-check:
	mypy src/ --strict

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=src --cov-report=html
