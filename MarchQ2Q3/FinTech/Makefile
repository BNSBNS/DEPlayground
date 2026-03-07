.PHONY: setup lint format type-check test test-cov test-all seed-mock build-embeddings docker-up docker-down clean

setup:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff check --fix src/ tests/
	ruff format src/ tests/

type-check:
	mypy src/ --strict

test:
	pytest tests/unit -v

test-cov:
	pytest tests/unit -v --cov=src --cov-report=html

test-all:
	pytest tests/ -v

seed-mock:
	python -m scripts.seed_mock_data

build-embeddings:
	python -m scripts.build_embeddings

docker-up:
	docker compose up -d

docker-down:
	docker compose down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name .coverage -delete 2>/dev/null || true
	rm -rf dist/ build/ *.egg-info/
