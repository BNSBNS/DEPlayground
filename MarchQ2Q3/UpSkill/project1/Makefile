.PHONY: setup lint format type-check test test-int test-cov migrate docker-up docker-down seed simulate

setup:
	pip install -e ".[dev]"

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

migrate:
	alembic upgrade head

docker-up:
	docker compose up -d

docker-down:
	docker compose down -v

seed:
	python -m simulation.seed

simulate:
	python -m simulation.simulator
