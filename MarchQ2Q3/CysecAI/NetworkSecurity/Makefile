.PHONY: setup lint format type-check test test-cov

setup:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

type-check:
	mypy src/ --strict

test:
	pytest tests/ -q

test-cov:
	pytest tests/ -q --cov-report=html
