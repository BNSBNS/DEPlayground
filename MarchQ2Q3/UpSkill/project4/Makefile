.PHONY: help install lint format typecheck test test-cov up down seed simulate api worker

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	pip install -e ".[dev]"

lint:  ## Run linter
	ruff check src/ tests/ simulation/

format:  ## Format code
	ruff format src/ tests/ simulation/

typecheck:  ## Run type checker
	mypy src/ --strict

test:  ## Run unit tests
	pytest tests/unit -v

test-cov:  ## Run tests with coverage
	pytest tests/unit -v --cov=src --cov-report=term-missing

up:  ## Start all services
	docker-compose up -d

down:  ## Stop all services
	docker-compose down -v

seed:  ## Seed reference data into Redis
	python -m simulation.seed

simulate:  ## Run event simulator
	python -m simulation.simulator --scenario normal --rate 50

api:  ## Run API server
	uvicorn src.api.main:app --port 8040 --reload

worker:  ## Run consumer workers
	python -m src.main
