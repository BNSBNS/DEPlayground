.PHONY: setup lint format type-check test test-int test-cov docker-up docker-down

setup:
	pip install -e "../cysec-shared[dev]" && pip install -e ".[dev]"

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

type-check:
	mypy src/ --strict

test:
	pytest tests/unit -v

test-int:
	pytest tests/integration -v

test-cov:
	pytest tests/unit -v --cov=src --cov-report=html

docker-up:
	docker compose up -d

docker-down:
	docker compose down -v
