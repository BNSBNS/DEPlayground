# Data Observability & Root Cause Intelligence

AI-powered data quality monitoring with automated root cause analysis and remediation.

## Setup

```bash
conda activate upskill
pip install -e ".[dev]"
```

## Usage

```bash
make lint          # ruff check
make type-check    # mypy strict
make test          # unit tests
make docker-up     # start services
make seed          # populate sample data
make simulate      # continuous simulation
```
