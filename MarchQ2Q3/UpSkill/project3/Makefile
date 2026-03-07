.PHONY: install lint format typecheck test test-cov integration run docker-up docker-down

install:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/ --strict

test:
	pytest tests/unit -v

test-cov:
	pytest tests/unit -v --cov=src --cov-report=html

integration:
	pytest tests/integration -v

run:
	uvicorn src.api.main:app --port 8030 --reload

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down
