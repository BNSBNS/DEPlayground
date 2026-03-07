FROM python:3.13-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

FROM base AS api
EXPOSE 8040
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8040"]

FROM base AS worker
CMD ["python", "-m", "src.main"]
