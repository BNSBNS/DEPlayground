.PHONY: setup lint format type-check test test-cov docker-up docker-down

setup:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/

format:
	ruff format --check src/ tests/

type-check:
	mypy --strict src/

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=src --cov-report=html

docker-up:
	docker compose up -d

docker-down:
	docker compose down -v
