FROM python:3.13-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

FROM base AS api
EXPOSE 8060
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8060"]

FROM base AS batch-worker
CMD ["python", "-m", "src.compute.batch.scheduler"]

FROM base AS stream-worker
CMD ["python", "-m", "src.compute.stream.engine"]
