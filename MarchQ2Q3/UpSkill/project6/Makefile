.PHONY: install lint format typecheck test test-cov up down seed simulate

install:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff check --fix src/ tests/
	ruff format src/ tests/

typecheck:
	mypy src/ --strict

test:
	pytest tests/unit -v

test-cov:
	pytest tests/unit -v --cov=src --cov-report=html

up:
	docker compose up -d

down:
	docker compose down -v

seed:
	python -m simulation.seed

simulate:
	python -m simulation.simulator
