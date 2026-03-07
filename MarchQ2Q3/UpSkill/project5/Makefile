.PHONY: install lint format typecheck test test-cov run seed simulate

install:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

typecheck:
	mypy src/ --strict

test:
	pytest tests/unit -v

test-cov:
	pytest tests/unit -v --cov=src --cov-report=html

test-integration:
	pytest tests/integration -v

run:
	uvicorn src.api.main:app --host 0.0.0.0 --port 8050 --reload

seed:
	python -m simulation.seed

simulate:
	python -m simulation.simulator
