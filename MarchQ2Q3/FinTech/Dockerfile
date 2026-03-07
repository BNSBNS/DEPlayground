FROM python:3.13-slim-bookworm AS builder

WORKDIR /app
RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-editable ".[all]"

COPY . .
RUN pip install --no-cache-dir --no-deps .

FROM python:3.13-slim-bookworm

RUN useradd --create-home appuser
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

RUN mkdir -p data/embeddings data/processed && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
