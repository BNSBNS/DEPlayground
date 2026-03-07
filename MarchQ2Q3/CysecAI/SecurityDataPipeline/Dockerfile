FROM python:3.13-slim AS base

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY ../cysec-shared /cysec-shared

RUN uv pip install --system -e /cysec-shared && \
    uv pip install --system -e ".[dev]"

COPY src/ src/
COPY rules/ rules/
COPY tests/ tests/

# API
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Dashboard
FROM base AS dashboard
EXPOSE 8501
CMD ["streamlit", "run", "src/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
